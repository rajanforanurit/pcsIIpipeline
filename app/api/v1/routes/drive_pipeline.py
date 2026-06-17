"""
Drive Pipeline management routes.
- List drive ingestion jobs
- Trigger manual pipeline run for a specific Drive file
- Pipeline status / health
"""
import math
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.core.config import settings
from app.core.dependencies import get_current_admin
from app.core.logging import get_logger
from app.db.mongodb import get_db
from app.models.common import SuccessResponse
from app.models.question import PaginatedResponse
from app.repositories.drive_repository import DriveRepository
from app.workers.drive_pipeline import run_drive_pipeline

router = APIRouter(prefix="/drive-pipeline", tags=["Drive Pipeline"])
logger = get_logger(__name__)


class TriggerPipelineRequest(BaseModel):
    drive_file_id: str
    file_name: str


@router.get("/jobs", response_model=PaginatedResponse)
async def list_drive_jobs(
    job_status: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PaginatedResponse:
    repo = DriveRepository(db)
    skip = (page - 1) * page_size
    total = await repo.count_drive_jobs(status=job_status)
    docs = await repo.list_drive_jobs(status=job_status, skip=skip, limit=page_size)

    items = []
    for doc in docs:
        items.append({
            "id": str(doc.get("_id", "")),
            "drive_file_id": doc.get("drive_file_id"),
            "file_name": doc.get("file_name"),
            "status": doc.get("status"),
            "document_type": doc.get("document_type"),
            "language": doc.get("language"),
            "question_count": doc.get("question_count", 0),
            "processing_time_seconds": doc.get("processing_time_seconds"),
            "created_at": doc.get("created_at"),
            "finished_at": doc.get("finished_at"),
            "errors": doc.get("errors", []),
        })

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/jobs/{job_id}")
async def get_drive_job(
    job_id: str,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = DriveRepository(db)
    doc = await repo.get_drive_job(job_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Drive job {job_id} not found")
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.post("/trigger", response_model=SuccessResponse)
async def trigger_pipeline(
    payload: TriggerPipelineRequest,
    background_tasks: BackgroundTasks,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SuccessResponse:
    """Manually trigger the ETL pipeline for a specific Drive file."""
    if not settings.google_drive_configured:
        raise HTTPException(status_code=503, detail="Google Drive is not configured")

    background_tasks.add_task(
        run_drive_pipeline,
        payload.drive_file_id,
        payload.file_name,
        db,
    )
    return SuccessResponse(
        message=f"Pipeline triggered for {payload.file_name}",
        data={"drive_file_id": payload.drive_file_id},
    )


@router.get("/status")
async def pipeline_status(
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return Drive pipeline configuration status."""
    repo = DriveRepository(db)
    state = await repo.get_watcher_state()

    return {
        "configured": settings.google_drive_configured,
        "pipeline_mode": settings.PIPELINE_MODE,
        "check_interval_seconds": settings.CHECK_INTERVAL_SECONDS,
        "max_concurrent_workers": settings.MAX_CONCURRENT_WORKERS,
        "duplicate_check_enabled": settings.ENABLE_DUPLICATE_CHECK,
        "watcher_page_token": state.get("page_token") if state else None,
        "watcher_updated_at": str(state.get("updated_at")) if state else None,
        "folders": {
            "unprocessed": settings.GOOGLE_DRIVE_UNPROCESSED_FOLDER_ID,
            "pending_json": settings.GOOGLE_DRIVE_PENDING_JSON_FOLDER_ID,
            "processed_json": settings.GOOGLE_DRIVE_PROCESSED_JSON_FOLDER_ID,
            "processed_pdf": settings.GOOGLE_DRIVE_PROCESSED_PDF_FOLDER_ID,
            "log": settings.GOOGLE_DRIVE_PROCESSED_LOG_FOLDER_ID,
            "failed": settings.GOOGLE_DRIVE_FAILED_FOLDER_ID,
        },
    }
