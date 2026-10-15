import re
from typing import List, Dict, Any

def clean_transcript_text(raw_text: str) -> str:
    """
    Cleans raw transcript text by removing extraneous caption noise,
    bracketed tags (e.g. [Music], [Applause]), normalizes whitespace.
    """
    if not raw_text:
        return ""
    
    # Remove bracketed tags like [Music], (Applause), [Laughter], etc.
    text = re.sub(r"\[[\w\s\.\-]+\]", " ", raw_text)
    text = re.sub(r"\([\w\s\.\-]+\)", " ", text)
    
    # Remove excessive repeated symbols and spaces
    text = re.sub(r"\s+", " ", text).strip()
    
    # Format into natural paragraphs roughly every 4-6 sentences for readability
    sentences = re.split(r"(?<=[.?!])\s+", text)
    paragraphs = []
    chunk = []
    for i, s in enumerate(sentences):
        chunk.append(s)
        if len(chunk) >= 5 or i == len(sentences) - 1:
            paragraphs.append(" ".join(chunk))
            chunk = []
            
    return "\n\n".join(paragraphs) if paragraphs else text

def format_transcript_with_timestamps(snippets: List[Dict[str, Any]]) -> str:
    """
    Combines raw snippets [{start, duration, text}] into formatted text
    with timestamp markers every 1-2 minutes for easy context citation.
    """
    if not snippets:
        return ""

    formatted_lines = []
    last_timestamp_marker = -120  # Mark roughly every 90-120 seconds

    for entry in snippets:
        start_sec = entry.get("start", 0)
        text = entry.get("text", "").strip()
        if not text:
            continue

        if start_sec - last_timestamp_marker >= 90:
            minutes = int(start_sec // 60)
            seconds = int(start_sec % 60)
            time_str = f"[{minutes:02d}:{seconds:02d}]"
            formatted_lines.append(f"\n{time_str} {text}")
            last_timestamp_marker = start_sec
        else:
            formatted_lines.append(f" {text}")

    full_text = "".join(formatted_lines).strip()
    return clean_transcript_text(full_text)

def estimate_tokens(text: str) -> int:
    """Rough estimation of token count (~4 characters per token)."""
    return max(1, len(text) // 4)
