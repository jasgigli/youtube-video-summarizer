import json
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import Column, Integer, String, Text, DateTime
from backend.app.database import Base

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_uuid = Column(String(64), unique=True, index=True, nullable=False)
    job_type = Column(String(32), nullable=False)  # SYNC_ALL, SYNC_CHANNEL, SUMMARIZE_VIDEO
    target_identifier = Column(String(128), nullable=True)  # channel_id or video_id
    
    # Status: QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
    status = Column(String(32), default="QUEUED", index=True)
    
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    
    current_step = Column(String(256), default="Initialized")
    error_message = Column(Text, nullable=True)
    logs_json = Column(Text, default="[]")

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    @property
    def logs(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.logs_json) if self.logs_json else []
        except Exception:
            return []

    def append_log(self, message: str, level: str = "INFO"):
        current_logs = self.logs
        current_logs.append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "message": message
        })
        self.logs_json = json.dumps(current_logs, ensure_ascii=False)

    def __repr__(self) -> str:
        return f"<ProcessingJob(id={self.id}, uuid='{self.job_uuid}', type='{self.job_type}', status='{self.status}')>"
