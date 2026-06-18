import math
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from app.core.config import settings
from app.core.dependencies import get_current_admin
from app.core.logging import get_logger
from app.db.mongodb import get_db
from app.models.common import SuccessResponse
from app.models.question import PaginatedResponse
from app.repositories.job_repository import JobRepository
from app.workers.drive_pipeline import run_blob_pipeline

router = APIRouter(prefix='/blob-pipeline', tags=['Blob Pipeline'])
logger = get_logger(__name__)


class TriggerPipelineRequest(BaseModel):
    blob_name: str
    file_name: str


@router.get('/jobs', response_model=PaginatedResponse)
async def list_jobs(
    job_status: Optional[str] = Query(default=None, alias='status'),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PaginatedResponse:
    repo = JobRepository(db)
    skip = (page - 1) * page_size
    total = await repo.count_jobs(status=job_status, job_type='Blob')
    docs = await repo.list_jobs(status=job_status, job_type='Blob', skip=skip, limit=page_size)
    items = []
    for doc in docs:
        items.append({
            'id': str(doc.get('_id', '')),
            'file_name': doc.get('original_filename'),
            'blob_name': doc.get('file_path'),
            'status': doc.get('status'),
            'total_pages': doc.get('total_pages', 0),
            'total_questions_saved': doc.get('total_questions_saved', 0),
            'created_at': doc.get('created_at'),
            'finished_at': doc.get('finished_at'),
        })
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get('/jobs/{job_id}')
async def get_job(
    job_id: str,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = JobRepository(db)
    doc = await repo.get_by_id(job_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f'Job {job_id} not found')
    doc['id'] = str(doc.pop('_id'))
    return doc


@router.post('/trigger', response_model=SuccessResponse)
async def trigger_pipeline(
    payload: TriggerPipelineRequest,
    background_tasks: BackgroundTasks,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SuccessResponse:
    if not settings.blob_configured:
        raise HTTPException(status_code=503, detail='Azure Blob Storage is not configured')
    background_tasks.add_task(run_blob_pipeline, payload.blob_name, payload.file_name, db)
    return SuccessResponse(
        message=f'Pipeline triggered for {payload.file_name}',
        data={'blob_name': payload.blob_name},
    )


@router.get('/status')
async def pipeline_status(
    current_admin: str = Depends(get_current_admin),
) -> dict:
    return {
        'configured': settings.blob_configured,
        'pipeline_mode': settings.PIPELINE_MODE,
        'check_interval_seconds': settings.CHECK_INTERVAL_SECONDS,
        'max_concurrent_workers': settings.MAX_CONCURRENT_WORKERS,
        'duplicate_check_enabled': settings.ENABLE_DUPLICATE_CHECK,
        'container': settings.AZURE_BLOB_CONTAINER_NAME,
        'folders': {
            'unprocessed': 'unprocessed',
            'processed_pdf': 'processed_pdf',
            'processed_json': 'processed_json',
            'processed_log': 'processed_log',
            'failed': 'failed',
        },
    }
