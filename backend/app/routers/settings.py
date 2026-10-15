from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.setting import Setting
from backend.app.schemas.settings import AppSettingsPayload, AppSettingsResponse
from backend.app.config import settings
from backend.app.services.scheduler_service import scheduler_service
from backend.app.services.llm_service import LLMService

router = APIRouter(prefix="/settings", tags=["Settings"])

def _get_setting_val(db: Session, key: str, default: str = "") -> str:
    item = db.query(Setting).filter(Setting.key == key).first()
    return item.value if item else default

def _set_setting_val(db: Session, key: str, value: str):
    item = db.query(Setting).filter(Setting.key == key).first()
    if item:
        item.value = value
    else:
        item = Setting(key=key, value=value)
        db.add(item)
    db.commit()

@router.get("", response_model=AppSettingsResponse)
def get_app_settings(db: Session = Depends(get_db)):
    """Retrieve application configuration with masked secrets for UI display."""
    yt_key = _get_setting_val(db, "youtube_api_key", settings.YOUTUBE_API_KEY)
    provider = _get_setting_val(db, "default_provider", settings.DEFAULT_PROVIDER)
    gemini_key = _get_setting_val(db, "gemini_api_key", settings.GEMINI_API_KEY)
    openai_key = _get_setting_val(db, "openai_api_key", settings.OPENAI_API_KEY)
    anthropic_key = _get_setting_val(db, "anthropic_api_key", settings.ANTHROPIC_API_KEY)
    ollama_url = _get_setting_val(db, "ollama_base_url", settings.OLLAMA_BASE_URL)
    default_model = _get_setting_val(db, "default_model", settings.DEFAULT_MODEL_GEMINI)
    max_videos = int(_get_setting_val(db, "max_videos_per_channel", str(settings.MAX_VIDEOS_PER_CHANNEL_SYNC)))
    interval = int(_get_setting_val(db, "sync_interval_hours", str(settings.SYNC_INTERVAL_HOURS)))
    prompt = _get_setting_val(db, "custom_system_prompt", "")
    whatsapp_phone = _get_setting_val(db, "whatsapp_phone", settings.WHATSAPP_PHONE_NUMBER)
    callmebot_key = _get_setting_val(db, "callmebot_api_key", settings.CALLMEBOT_API_KEY)
    twilio_sid = _get_setting_val(db, "twilio_account_sid", settings.TWILIO_ACCOUNT_SID)
    twilio_token = _get_setting_val(db, "twilio_auth_token", settings.TWILIO_AUTH_TOKEN)

    return AppSettingsResponse(
        youtube_api_key_set=bool(yt_key and yt_key.strip()),
        default_provider=provider,
        gemini_api_key_set=bool(gemini_key and gemini_key.strip()),
        openai_api_key_set=bool(openai_key and openai_key.strip()),
        anthropic_api_key_set=bool(anthropic_key and anthropic_key.strip()),
        ollama_base_url=ollama_url,
        default_model=default_model,
        max_videos_per_channel=max_videos,
        sync_interval_hours=interval,
        custom_system_prompt=prompt,
        whatsapp_phone=whatsapp_phone,
        callmebot_api_key_set=bool(callmebot_key and callmebot_key.strip()),
        twilio_configured=bool(twilio_sid and twilio_token),
        is_scheduler_running=scheduler_service.scheduler.running
    )

@router.post("", response_model=AppSettingsResponse)
def update_app_settings(
    payload: AppSettingsPayload,
    db: Session = Depends(get_db)
):
    """Update application API keys and preferences."""
    if payload.youtube_api_key is not None:
        _set_setting_val(db, "youtube_api_key", payload.youtube_api_key.strip())
    if payload.default_provider is not None:
        _set_setting_val(db, "default_provider", payload.default_provider.strip().lower())
    if payload.gemini_api_key is not None:
        _set_setting_val(db, "gemini_api_key", payload.gemini_api_key.strip())
    if payload.openai_api_key is not None:
        _set_setting_val(db, "openai_api_key", payload.openai_api_key.strip())
    if payload.anthropic_api_key is not None:
        _set_setting_val(db, "anthropic_api_key", payload.anthropic_api_key.strip())
    if payload.ollama_base_url is not None:
        _set_setting_val(db, "ollama_base_url", payload.ollama_base_url.strip())
    if payload.default_model is not None:
        _set_setting_val(db, "default_model", payload.default_model.strip())
    if payload.max_videos_per_channel is not None:
        _set_setting_val(db, "max_videos_per_channel", str(payload.max_videos_per_channel))
    if payload.sync_interval_hours is not None:
        _set_setting_val(db, "sync_interval_hours", str(payload.sync_interval_hours))
        scheduler_service.update_interval(payload.sync_interval_hours)
    if payload.custom_system_prompt is not None:
        _set_setting_val(db, "custom_system_prompt", payload.custom_system_prompt)
    if payload.whatsapp_phone is not None:
        _set_setting_val(db, "whatsapp_phone", payload.whatsapp_phone.strip())
    if payload.callmebot_api_key is not None:
        _set_setting_val(db, "callmebot_api_key", payload.callmebot_api_key.strip())
    if payload.twilio_account_sid is not None:
        _set_setting_val(db, "twilio_account_sid", payload.twilio_account_sid.strip())
    if payload.twilio_auth_token is not None:
        _set_setting_val(db, "twilio_auth_token", payload.twilio_auth_token.strip())
    if payload.twilio_whatsapp_number is not None:
        _set_setting_val(db, "twilio_whatsapp_number", payload.twilio_whatsapp_number.strip())

    return get_app_settings(db)

@router.post("/test-connection")
async def test_llm_connection(
    provider: str,
    api_key: str,
    db: Session = Depends(get_db)
):
    """Validates whether the provided API key is functional."""
    llm = LLMService(provider=provider, api_key=api_key)
    try:
        res = await llm.summarize_video(
            title="Connection Test",
            channel_name="System",
            transcript="This is a quick connectivity verification probe to check API credentials and response formatting."
        )
        return {"status": "SUCCESS", "message": f"Successfully connected to {provider.upper()}!", "sample": res.get("one_sentence_takeaway")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection test failed for {provider}: {str(e)}")
