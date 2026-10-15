from typing import Optional, Dict, Any
from pydantic import BaseModel

class AppSettingsPayload(BaseModel):
    youtube_api_key: Optional[str] = None
    default_provider: Optional[str] = "gemini"
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = "http://localhost:11434"
    default_model: Optional[str] = None
    max_videos_per_channel: Optional[int] = 10
    sync_interval_hours: Optional[int] = 6
    custom_system_prompt: Optional[str] = None
    whatsapp_phone: Optional[str] = None
    callmebot_api_key: Optional[str] = None
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_whatsapp_number: Optional[str] = None

class AppSettingsResponse(BaseModel):
    youtube_api_key_set: bool
    default_provider: str
    gemini_api_key_set: bool
    openai_api_key_set: bool
    anthropic_api_key_set: bool
    ollama_base_url: str
    default_model: str
    max_videos_per_channel: int
    sync_interval_hours: int
    custom_system_prompt: Optional[str] = None
    whatsapp_phone: str = "923155619203"
    callmebot_api_key_set: bool = False
    twilio_configured: bool = False
    is_scheduler_running: bool = False
