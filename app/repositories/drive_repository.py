"""Repository for Drive pipeline data: file records, watcher state, pending reviews, drive jobs."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import get_logger
from app.models.common import JobStatus
from app.models.pipeline import DriveIngestionJob, DriveFileRecord, PendingReviewDocument

logger = get_logger(__name__)

COL_DRIVE_FILES = "drive_file_records"
COL_DRIVE_JOBS = "drive_ingestion_jobs"
COL_PENDING_REVIEWS = "pending_reviews"
COL_WATCHER_STATE = "drive_watcher_state"


class DriveRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._files = db[COL_DRIVE_FILES]
        self._jobs = db[COL_DRIVE_JOBS]
        self._reviews = db[COL_PENDING_REVIEWS]
        self._watcher = db[COL_WATCHER_STATE]

    # ------------------------------------------------------------------ #
    # Watcher state
    # ------------------------------------------------------------------ #

    async def get_watcher_state(self) -> Optional[Dict[str, Any]]:
        return await self._watcher.find_one({"_id": "singleton"})

    async def save_watcher_state(self, page_token: str) -> None:
        await self._watcher.update_one(
            {"_id": "singleton"},
            {"$set": {"page_token": page_token, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    # ------------------------------------------------------------------ #
    # Drive file records (duplicate detection)
    # ------------------------------------------------------------------ #

    async def file_already_processed(self, drive_file_id: str) -> bool:
        doc = await self._files.find_one({"drive_file_id": drive_file_id})
        if doc and doc.get("processed"):
            return True
        return False

    async def file_exists(self, drive_file_id: str) -> bool:
        doc = await self._files.find_one({"drive_file_id": drive_file_id})
        return doc is not None

    async def create_file_record(self, record: DriveFileRecord) -> str:
        doc = record.model_dump(by_alias=True, exclude_none=True)
        doc.pop("_id", None)
        result = await self._files.insert_one(doc)
        return str(result.inserted_id)

    async def mark_drive_file_processed(
        self,
        drive_file_id: str,
        job_id: Optional[str],
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        update: Dict[str, Any] = {
            "processed": status not in ("new", "processing"),
            "processing_status": status,
            "drive_job_id": job_id,
            "updated_at": datetime.now(timezone.utc),
        }
        if error_message:
            update["error_message"] = error_message
        await self._files.update_one(
            {"drive_file_id": drive_file_id},
            {"$set": update},
            upsert=True,
        )

    # ------------------------------------------------------------------ #
    # Drive ingestion jobs
    # ------------------------------------------------------------------ #

    async def create_drive_job(self, job: DriveIngestionJob) -> str:
        doc = job.model_dump(by_alias=True, exclude_none=True)
        doc.pop("_id", None)
        result = await self._jobs.insert_one(doc)
        return str(result.inserted_id)

    async def get_drive_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        if not ObjectId.is_valid(job_id):
            return None
        return await self._jobs.find_one({"_id": ObjectId(job_id)})

    async def update_job_status(self, job_id: str, status: JobStatus) -> None:
        await self._jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"status": status.value, "updated_at": datetime.now(timezone.utc)}},
        )

    async def update_job_field(self, job_id: str, field: str, value: Any) -> None:
        await self._jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {field: value, "updated_at": datetime.now(timezone.utc)}},
        )

    async def update_drive_job_finished(
        self,
        job_id: str,
        status: JobStatus,
        pending_json_drive_id: Optional[str],
        question_count: int,
        ocr_duration: float,
        ai_duration: float,
        processing_time: float,
        warnings: List[str],
        errors: Optional[List[str]] = None,
    ) -> None:
        update: Dict[str, Any] = {
            "status": status.value,
            "question_count": question_count,
            "ocr_duration_seconds": round(ocr_duration, 2),
            "ai_duration_seconds": round(ai_duration, 2),
            "processing_time_seconds": round(processing_time, 2),
            "warnings": warnings,
            "finished_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        if pending_json_drive_id:
            update["pending_json_drive_id"] = pending_json_drive_id
        if errors:
            update["errors"] = errors
        await self._jobs.update_one({"_id": ObjectId(job_id)}, {"$set": update})

    async def list_drive_jobs(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status
        cursor = self._jobs.find(query).sort("created_at", -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_drive_jobs(self, status: Optional[str] = None) -> int:
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status
        return await self._jobs.count_documents(query)

    # ------------------------------------------------------------------ #
    # Pending reviews
    # ------------------------------------------------------------------ #

    async def create_pending_review(self, doc: PendingReviewDocument) -> str:
        data = doc.model_dump(by_alias=True, exclude_none=True)
        data.pop("_id", None)
        result = await self._reviews.insert_one(data)
        return str(result.inserted_id)

    async def get_pending_review(self, review_id: str) -> Optional[Dict[str, Any]]:
        if not ObjectId.is_valid(review_id):
            return None
        return await self._reviews.find_one({"_id": ObjectId(review_id)})

    async def get_pending_review_by_job(self, drive_job_id: str) -> Optional[Dict[str, Any]]:
        return await self._reviews.find_one({"drive_job_id": drive_job_id})

    async def list_pending_reviews(
        self,
        status: str = "pending",
        skip: int = 0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        cursor = (
            self._reviews.find({"status": status})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def count_pending_reviews(self, status: str = "pending") -> int:
        return await self._reviews.count_documents({"status": status})

    async def update_pending_review_questions(
        self, review_id: str, questions: List[Dict[str, Any]]
    ) -> bool:
        result = await self._reviews.update_one(
            {"_id": ObjectId(review_id)},
            {
                "$set": {
                    "questions": questions,
                    "question_count": len(questions),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.modified_count > 0

    async def set_pending_review_status(self, review_id: str, status: str) -> bool:
        result = await self._reviews.update_one(
            {"_id": ObjectId(review_id)},
            {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0
