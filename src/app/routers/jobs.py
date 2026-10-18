from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from src.app.database import get_db
from src.app.models.job import ProcessingJob
from src.app.schemas.job import JobRead, JobTriggerRequest
from src.app.services.job_service import JobService, ws_manager

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.get("", response_model=List[JobRead])
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Retrieve history of background execution jobs."""
    jobs = db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(limit).all()
    return jobs

@router.get("/{job_uuid}", response_model=JobRead)
def get_job_detail(
    job_uuid: str,
    db: Session = Depends(get_db)
):
    """Retrieve full logs and status for a specific background job."""
    job = db.query(ProcessingJob).filter(ProcessingJob.job_uuid == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.post("/trigger")
async def trigger_job(
    payload: JobTriggerRequest
):
    """Trigger an asynchronous sync or summarization pipeline job."""
    job_uuid = await JobService.create_and_run_job(
        job_type=payload.job_type,
        target_identifier=payload.target_identifier
    )
    return {
        "message": f"Job {payload.job_type} started successfully",
        "job_uuid": job_uuid
    }

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection for real-time pipeline status and log streaming."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive heartbeat receiver
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
