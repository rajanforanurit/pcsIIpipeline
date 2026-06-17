import math
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.dependencies import get_current_admin
from app.core.logging import get_logger
from app.db.mongodb import get_db
from app.models.job import JobDetailResponse, JobResponse
from app.models.question import PaginatedResponse
from app.repositories.job_repository import JobRepository
router = APIRouter(prefix="/jobs", tags=["Jobs"])
logger = get_logger(__name__)
def _job_doc_to_response(doc: dict) -> dict:
    doc["job_id"] = str(doc.pop("_id"))
    return doc
@router.get("", response_model=PaginatedResponse)
async def list_jobs(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    job_type: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PaginatedResponse:
    repo = JobRepository(db)
    skip = (page - 1) * page_size
    total = await repo.count_jobs(status=status_filter, job_type=job_type)
    docs = await repo.list_jobs(status=status_filter, job_type=job_type, skip=skip, limit=page_size)
    items = []
    for doc in docs:
        job_id = str(doc.get("_id", ""))
        items.append(JobResponse(
            job_id=job_id,
            job_type=doc.get("job_type", ""),
            status=doc.get("status", ""),
            progress_percent=doc.get("progress_percent", 0.0),
            total_pages=doc.get("total_pages", 0),
            total_questions_found=doc.get("total_questions_found", 0),
            total_questions_saved=doc.get("total_questions_saved", 0),
            original_filename=doc.get("original_filename", ""),
            started_at=doc.get("started_at"),
            finished_at=doc.get("finished_at"),
            errors=doc.get("errors", []),
        ))
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=math.ceil(total / page_size) if total > 0 else 1)
@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: str,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> JobDetailResponse:
    repo = JobRepository(db)
    doc = await repo.get_by_id(job_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found")
    return JobDetailResponse(
        job_id=str(doc["_id"]),
        job_type=doc.get("job_type", ""),
        status=doc.get("status", ""),
        progress_percent=doc.get("progress_percent", 0.0),
        total_pages=doc.get("total_pages", 0),
        total_questions_found=doc.get("total_questions_found", 0),
        total_questions_saved=doc.get("total_questions_saved", 0),
        original_filename=doc.get("original_filename", ""),
        started_at=doc.get("started_at"),
        finished_at=doc.get("finished_at"),
        errors=doc.get("errors", []),
        logs=doc.get("logs", []),
        pdf_type=doc.get("pdf_type"),
        year=doc.get("year"),
        exam=doc.get("exam"),
        paper=doc.get("paper"),
        book_title=doc.get("book_title"),
        subject=doc.get("subject"),
    )
