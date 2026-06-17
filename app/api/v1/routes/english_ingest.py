import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, Form, UploadFile, File
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
from app.core.dependencies import get_current_admin
from app.core.logging import get_logger
from app.db.mongodb import get_db
from app.models.common import JobType, SuccessResponse
from app.models.job import IngestionJob, JobResponse
from app.repositories.job_repository import JobRepository
from app.services.file_service import save_upload
from app.services.ingestion.english_ingestion import run_english_ingestion
router = APIRouter(prefix='/ingest/english', tags=['English Ingestion'])
logger = get_logger(__name__)
@router.post('', response_model=JobResponse, status_code=202)
async def ingest_english(background_tasks: BackgroundTasks, file: UploadFile=File(...), year: int=Form(..., ge=1900, le=2100), exam: str=Form(..., min_length=1, max_length=100), paper: str=Form(..., min_length=1, max_length=50), set_name: Optional[str]=Form(default=None, max_length=10), current_admin: str=Depends(get_current_admin), db: AsyncIOMotorDatabase=Depends(get_db)) -> JobResponse:
    file_path = await save_upload(file)
    logger.info('ingest.english.upload', filename=file.filename, year=year, exam=exam, paper=paper, admin=current_admin)
    job = IngestionJob(job_type=JobType.ENGLISH, original_filename=file.filename or 'upload.pdf', file_path=file_path, year=year, exam=exam, paper=paper, set_name=set_name, created_by=current_admin, updated_by=current_admin)
    repo = JobRepository(db)
    job_id = await repo.create(job)
    background_tasks.add_task(run_english_ingestion, job_id, db)
    return JobResponse(job_id=job_id, job_type=JobType.ENGLISH, status=job.status, progress_percent=0.0, total_pages=0, total_questions_found=0, total_questions_saved=0, original_filename=job.original_filename)
