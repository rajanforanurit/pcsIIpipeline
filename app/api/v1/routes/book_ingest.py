from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, File, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
from app.core.config import settings
from app.core.dependencies import get_current_admin
from app.core.logging import get_logger
from app.db.mongodb import get_db
from app.models.common import JobType
from app.models.job import IngestionJob, JobResponse
from app.repositories.job_repository import JobRepository
from app.services.file_service import save_upload
from app.services.ingestion.book_ingestion import run_book_ingestion
router = APIRouter(prefix='/ingest/book', tags=['Book Ingestion'])
logger = get_logger(__name__)
@router.post('', response_model=JobResponse, status_code=202)
async def ingest_book(background_tasks: BackgroundTasks, file: UploadFile=File(...), book_title: str=Form(..., min_length=1, max_length=200), book_author: Optional[str]=Form(default=None, max_length=100), subject: Optional[str]=Form(default=None, max_length=100), current_admin: str=Depends(get_current_admin), db: AsyncIOMotorDatabase=Depends(get_db)) -> JobResponse:
    if not settings.ai_configured:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='AI provider not configured. Set PSC2 and PCS2_API environment variables.')
    file_path = await save_upload(file)
    logger.info('ingest.book.upload', filename=file.filename, book_title=book_title, admin=current_admin)
    job = IngestionJob(job_type=JobType.BOOK, original_filename=file.filename or 'upload.pdf', file_path=file_path, book_title=book_title, book_author=book_author, subject=subject, created_by=current_admin, updated_by=current_admin)
    repo = JobRepository(db)
    job_id = await repo.create(job)
    background_tasks.add_task(run_book_ingestion, job_id, db)
    return JobResponse(job_id=job_id, job_type=JobType.BOOK, status=job.status, progress_percent=0.0, total_pages=0, total_questions_found=0, total_questions_saved=0, original_filename=job.original_filename)
