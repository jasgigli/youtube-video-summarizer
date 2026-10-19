from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict

class JobLogEntry(BaseModel):
    timestamp: str
    level: str
    message: str

class JobRead(BaseModel):
    id: int
    job_uuid: str
    job_type: str
    target_identifier: Optional[str] = None
    status: str
    total_items: int
    processed_items: int
    failed_items: int
    current_step: str
    error_message: Optional[str] = None
    logs: List[Dict[str, Any]] = []
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class JobTriggerRequest(BaseModel):
    job_type: str  # "SYNC_ALL", "SYNC_CHANNEL", "SUMMARIZE_VIDEO", "RETRY_FAILED"
    target_identifier: Optional[str] = None
