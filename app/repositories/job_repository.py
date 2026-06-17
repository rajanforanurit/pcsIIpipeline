from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.logging import get_logger
from app.db.mongodb import COLLECTION_INGESTION_JOBS
from app.models.common import JobStatus
from app.models.job import IngestionJob, JobError, JobLog
logger = get_logger(__name__)
class JobRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db[COLLECTION_INGESTION_JOBS]
    async def create(self, job: IngestionJob) -> str:
        doc = job.model_dump(by_alias=True, exclude_none=True)
        doc.pop('_id', None)
        result = await self._col.insert_one(doc)
        job_id = str(result.inserted_id)
        logger.info('job.created', job_id=job_id, job_type=job.job_type)
        return job_id
    async def get_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        if not ObjectId.is_valid(job_id):
            return None
        return await self._col.find_one({'_id': ObjectId(job_id)})
    async def list_jobs(self, status: Optional[str]=None, job_type: Optional[str]=None, skip: int=0, limit: int=20) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if status:
            query['status'] = status
        if job_type:
            query['job_type'] = job_type
        cursor = self._col.find(query).sort('created_at', -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)
    async def count_jobs(self, status: Optional[str]=None, job_type: Optional[str]=None) -> int:
        query: Dict[str, Any] = {}
        if status:
            query['status'] = status
        if job_type:
            query['job_type'] = job_type
        return await self._col.count_documents(query)
    async def update_status(self, job_id: str, status: JobStatus, progress_percent: Optional[float]=None, extra_fields: Optional[Dict[str, Any]]=None) -> None:
        set_doc: Dict[str, Any] = {'status': status.value, 'updated_at': datetime.now(timezone.utc)}
        if progress_percent is not None:
            set_doc['progress_percent'] = round(progress_percent, 2)
        if extra_fields:
            set_doc.update(extra_fields)
        await self._col.update_one({'_id': ObjectId(job_id)}, {'$set': set_doc})
        logger.debug('job.status_updated', job_id=job_id, status=status.value)
    async def mark_started(self, job_id: str) -> None:
        await self._col.update_one({'_id': ObjectId(job_id)}, {'$set': {'status': JobStatus.RUNNING.value, 'started_at': datetime.now(timezone.utc), 'updated_at': datetime.now(timezone.utc)}})
    async def mark_finished(self, job_id: str, status: JobStatus, total_questions_found: int=0, total_questions_saved: int=0) -> None:
        set_doc: Dict[str, Any] = {'status': status.value, 'finished_at': datetime.now(timezone.utc), 'updated_at': datetime.now(timezone.utc), 'total_questions_found': total_questions_found, 'total_questions_saved': total_questions_saved}
        if status == JobStatus.DRAFT_READY:
            set_doc['progress_percent'] = 100.0
        await self._col.update_one({'_id': ObjectId(job_id)}, {'$set': set_doc})
    async def update_pdf_info(self, job_id: str, pdf_type: str, total_pages: int) -> None:
        await self._col.update_one({'_id': ObjectId(job_id)}, {'$set': {'pdf_type': pdf_type, 'total_pages': total_pages, 'updated_at': datetime.now(timezone.utc)}})
    async def append_log(self, job_id: str, log_entry: JobLog) -> None:
        await self._col.update_one({'_id': ObjectId(job_id)}, {'$push': {'logs': log_entry.model_dump()}, '$set': {'updated_at': datetime.now(timezone.utc)}})
    async def append_error(self, job_id: str, error: JobError) -> None:
        await self._col.update_one({'_id': ObjectId(job_id)}, {'$push': {'errors': error.model_dump()}, '$set': {'updated_at': datetime.now(timezone.utc)}})
    async def count_by_status(self) -> Dict[str, int]:
        pipeline = [{'$group': {'_id': '$status', 'count': {'$sum': 1}}}]
        results = await self._col.aggregate(pipeline).to_list(length=None)
        return {r['_id']: r['count'] for r in results}
