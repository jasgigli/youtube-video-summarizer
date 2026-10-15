from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.video import Video
from backend.app.models.summary import Summary
from backend.app.models.setting import Setting
from backend.app.schemas.summary import SummaryRead, SummaryRegenerateRequest
from backend.app.services.llm_service import LLMService
from backend.app.services.transcript_service import TranscriptService

router = APIRouter(prefix="/summaries", tags=["Summaries"])

@router.post("/{video_id}/regenerate", response_model=SummaryRead)
async def regenerate_summary(
    video_id: int,
    payload: SummaryRegenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Regenerates a summary on-demand with optional custom instructions,
    model override, or specific provider.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    content_to_summarize = video.transcript_text
    if not content_to_summarize:
        t_res = await TranscriptService.fetch_transcript(video.video_id)
        video.transcript_status = t_res["status"]
        video.transcript_language = t_res.get("language")
        video.transcript_error = t_res.get("error")
        if t_res["status"] == "SUCCESS" and t_res.get("text"):
            video.transcript_text = t_res["text"]
            content_to_summarize = t_res["text"]
        else:
            # Fallback to synthesizing from title and creator description via yt-dlp metadata
            if not video.description or len(video.description.strip()) < 15:
                meta = TranscriptService.fetch_video_metadata(video.video_id)
                if meta.get("description"):
                    video.description = meta["description"]
            
            channel_name = video.channel.title if video.channel else "YouTube Creator"
            content_to_summarize = (
                f"Video Title: {video.title}\n"
                f"Channel: {channel_name}\n\n"
                f"Detailed Creator Description & Overview:\n"
                f"{video.description or video.title}\n\n"
                f"(Note: Synthesize the executive summary and key insights based on the video title and creator description.)"
            )
        db.commit()

    # Determine provider and keys
    provider = payload.provider
    if not provider:
        p_setting = db.query(Setting).filter(Setting.key == "default_provider").first()
        provider = p_setting.value if p_setting else "gemini"

    key_setting = db.query(Setting).filter(Setting.key == f"{provider}_api_key").first()
    api_key = key_setting.value if key_setting else None

    llm = LLMService(provider=provider, model_name=payload.model_name, api_key=api_key)

    try:
        channel_name = video.channel.title if video.channel else "YouTube Creator"
        summary_data = await llm.summarize_video(
            title=video.title,
            channel_name=channel_name,
            transcript=content_to_summarize,
            custom_instructions=payload.custom_instruction
        )

        existing = db.query(Summary).filter(Summary.video_id == video.id).first()
        if existing:
            existing.provider = summary_data["provider"]
            existing.model_name = summary_data["model_name"]
            existing.one_sentence_takeaway = summary_data["one_sentence_takeaway"]
            existing.key_takeaways = summary_data["key_takeaways"]
            existing.detailed_breakdown = summary_data["detailed_breakdown"]
            existing.action_items = summary_data["action_items"]
            existing.notable_quotes = summary_data["notable_quotes"]
            existing.topics = summary_data["topics"]
            existing.sentiment = summary_data.get("sentiment", "informative")
            existing.tokens_used = summary_data.get("tokens_used", 0)
            existing.processing_time_sec = summary_data.get("processing_time_sec", 0.0)
            existing.custom_prompt_used = payload.custom_instruction
            summary_obj = existing
        else:
            summary_obj = Summary(
                video_id=video.id,
                provider=summary_data["provider"],
                model_name=summary_data["model_name"],
                one_sentence_takeaway=summary_data["one_sentence_takeaway"],
                detailed_breakdown=summary_data["detailed_breakdown"],
                sentiment=summary_data.get("sentiment", "informative"),
                tokens_used=summary_data.get("tokens_used", 0),
                processing_time_sec=summary_data.get("processing_time_sec", 0.0),
                custom_prompt_used=payload.custom_instruction
            )
            summary_obj.key_takeaways = summary_data["key_takeaways"]
            summary_obj.action_items = summary_data["action_items"]
            summary_obj.notable_quotes = summary_data["notable_quotes"]
            summary_obj.topics = summary_data["topics"]
            db.add(summary_obj)

        video.summary_status = "COMPLETED"
        video.summary_error = None
        db.commit()
        db.refresh(summary_obj)

        return SummaryRead.model_validate(summary_obj)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to regenerate summary: {str(e)}")

@router.get("/{video_id}/export/markdown")
def export_summary_markdown(
    video_id: int,
    db: Session = Depends(get_db)
):
    """Generates a downloadable, beautifully formatted Markdown file of the summary."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video or not video.summary:
        raise HTTPException(status_code=404, detail="Summary not found for this video")

    s = video.summary
    channel_title = video.channel.title if video.channel else "YouTube Creator"

    lines = [
        f"# {video.title}",
        f"**Channel:** {channel_title}  ",
        f"**Source URL:** {video.video_url}  ",
        f"**Synthesized With:** {s.provider} ({s.model_name})  ",
        f"**Date:** {video.published_at.strftime('%Y-%m-%d')}  ",
        "",
        "---",
        "",
        "## Executive Takeaway",
        f"> {s.one_sentence_takeaway}",
        "",
        "## Key Takeaways",
    ]
    for kt in s.key_takeaways:
        lines.append(f"- {kt}")

    lines.extend([
        "",
        "## Detailed Analysis",
        s.detailed_breakdown,
        "",
        "## Action Items & Recommendations"
    ])
    for item in s.action_items:
        lines.append(f"- [ ] {item}")

    if s.notable_quotes:
        lines.extend(["", "## Notable Quotes"])
        for q in s.notable_quotes:
            quote_str = q.get("quote", "")
            ctx = q.get("context_or_timestamp", "")
            lines.append(f"> \"{quote_str}\" — *{ctx}*")

    md_content = "\n".join(lines)
    filename = f"summary_{video.video_id}.md"

    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
