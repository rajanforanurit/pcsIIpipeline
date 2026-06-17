from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.logging import get_logger
from app.db.mongodb import (
    COLLECTION_BOOK_QUESTIONS,
    COLLECTION_ENGLISH_QUESTIONS,
    COLLECTION_HINDI_QUESTIONS,
)
from app.models.common import QuestionStatus
from app.models.question import BookQuestion, PCSQuestion

logger = get_logger(__name__)
class _BaseQuestionRepository:

    _collection_name: str = ""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db[self._collection_name]

    async def insert_many(self, questions: List[PCSQuestion]) -> List[str]:
        if not questions:
            return []
        docs = [q.model_dump(by_alias=True, exclude_none=True) for q in questions]
        for doc in docs:
            doc.pop("_id", None)
        result = await self._col.insert_many(docs)
        ids = [str(oid) for oid in result.inserted_ids]
        logger.info(f"{self._collection_name}.inserted", count=len(ids))
        return ids

    async def insert_one(self, question: PCSQuestion) -> str:
        doc = question.model_dump(by_alias=True, exclude_none=True)
        doc.pop("_id", None)
        result = await self._col.insert_one(doc)
        return str(result.inserted_id)

    async def get_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        if not ObjectId.is_valid(question_id):
            return None
        return await self._col.find_one({"_id": ObjectId(question_id)})

    async def list_questions(
        self,
        job_id: Optional[str] = None,
        status: Optional[str] = None,
        exam: Optional[str] = None,
        year: Optional[int] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        query = self._build_query(job_id, status, exam, year, search)
        cursor = self._col.find(query).sort("question_no", 1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_questions(
        self,
        job_id: Optional[str] = None,
        status: Optional[str] = None,
        exam: Optional[str] = None,
        year: Optional[int] = None,
        search: Optional[str] = None,
    ) -> int:
        query = self._build_query(job_id, status, exam, year, search)
        return await self._col.count_documents(query)

    def _build_query(
        self,
        job_id: Optional[str],
        status: Optional[str],
        exam: Optional[str],
        year: Optional[int],
        search: Optional[str],
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {}
        if job_id:
            query["job_id"] = job_id
        if status:
            query["status"] = status
        if exam:
            query["exam"] = {"$regex": exam, "$options": "i"}
        if year:
            query["year"] = year
        if search:
            query["$text"] = {"$search": search}
        return query

    async def update_question(
        self, question_id: str, update_data: Dict[str, Any], updated_by: str = "admin"
    ) -> bool:
        update_data["updated_at"] = datetime.now(timezone.utc)
        update_data["updated_by"] = updated_by
        result = await self._col.update_one(
            {"_id": ObjectId(question_id)},
            {"$set": update_data, "$inc": {"revision_number": 1}},
        )
        return result.modified_count > 0

    async def approve_question(self, question_id: str, updated_by: str = "admin") -> bool:
        return await self.update_question(
            question_id, {"status": QuestionStatus.APPROVED.value}, updated_by
        )

    async def bulk_approve(self, question_ids: List[str], updated_by: str = "admin") -> int:
        object_ids = [ObjectId(qid) for qid in question_ids if ObjectId.is_valid(qid)]
        if not object_ids:
            return 0
        result = await self._col.update_many(
            {"_id": {"$in": object_ids}},
            {
                "$set": {
                    "status": QuestionStatus.APPROVED.value,
                    "updated_at": datetime.now(timezone.utc),
                    "updated_by": updated_by,
                },
                "$inc": {"revision_number": 1},
            },
        )
        logger.info(f"{self._collection_name}.bulk_approved", count=result.modified_count)
        return result.modified_count

    async def delete_question(self, question_id: str) -> bool:
        result = await self._col.delete_one({"_id": ObjectId(question_id)})
        return result.deleted_count > 0

    async def count_by_status(self) -> Dict[str, int]:
        pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
        results = await self._col.aggregate(pipeline).to_list(length=None)
        return {r["_id"]: r["count"] for r in results}


class EnglishQuestionRepository(_BaseQuestionRepository):
    _collection_name = COLLECTION_ENGLISH_QUESTIONS


class HindiQuestionRepository(_BaseQuestionRepository):
    _collection_name = COLLECTION_HINDI_QUESTIONS

class PCSQuestionRepository(EnglishQuestionRepository):
    pass


class BookQuestionRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db[COLLECTION_BOOK_QUESTIONS]

    async def insert_many(self, questions: List[BookQuestion]) -> List[str]:
        if not questions:
            return []
        docs = [q.model_dump(by_alias=True, exclude_none=True) for q in questions]
        for doc in docs:
            doc.pop("_id", None)
        result = await self._col.insert_many(docs)
        ids = [str(oid) for oid in result.inserted_ids]
        logger.info("book_questions.inserted", count=len(ids))
        return ids

    async def insert_one(self, question: BookQuestion) -> str:
        doc = question.model_dump(by_alias=True, exclude_none=True)
        doc.pop("_id", None)
        result = await self._col.insert_one(doc)
        return str(result.inserted_id)

    async def get_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        if not ObjectId.is_valid(question_id):
            return None
        return await self._col.find_one({"_id": ObjectId(question_id)})

    async def list_questions(
        self,
        job_id: Optional[str] = None,
        book_title: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        query = self._build_query(job_id, book_title, status, search)
        cursor = self._col.find(query).sort("chunk_index", 1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_questions(
        self,
        job_id: Optional[str] = None,
        book_title: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> int:
        query = self._build_query(job_id, book_title, status, search)
        return await self._col.count_documents(query)

    def _build_query(
        self,
        job_id: Optional[str],
        book_title: Optional[str],
        status: Optional[str],
        search: Optional[str],
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {}
        if job_id:
            query["job_id"] = job_id
        if book_title:
            query["book_title"] = {"$regex": book_title, "$options": "i"}
        if status:
            query["status"] = status
        if search:
            query["$text"] = {"$search": search}
        return query

    async def update_question(
        self, question_id: str, update_data: Dict[str, Any], updated_by: str = "admin"
    ) -> bool:
        update_data["updated_at"] = datetime.now(timezone.utc)
        update_data["updated_by"] = updated_by
        result = await self._col.update_one(
            {"_id": ObjectId(question_id)},
            {"$set": update_data, "$inc": {"revision_number": 1}},
        )
        return result.modified_count > 0

    async def approve_question(self, question_id: str, updated_by: str = "admin") -> bool:
        return await self.update_question(
            question_id, {"status": QuestionStatus.APPROVED.value}, updated_by
        )

    async def bulk_approve(self, question_ids: List[str], updated_by: str = "admin") -> int:
        object_ids = [ObjectId(qid) for qid in question_ids if ObjectId.is_valid(qid)]
        if not object_ids:
            return 0
        result = await self._col.update_many(
            {"_id": {"$in": object_ids}},
            {
                "$set": {
                    "status": QuestionStatus.APPROVED.value,
                    "updated_at": datetime.now(timezone.utc),
                    "updated_by": updated_by,
                },
                "$inc": {"revision_number": 1},
            },
        )
        logger.info("book_questions.bulk_approved", count=result.modified_count)
        return result.modified_count

    async def delete_question(self, question_id: str) -> bool:
        result = await self._col.delete_one({"_id": ObjectId(question_id)})
        return result.deleted_count > 0

    async def count_by_status(self) -> Dict[str, int]:
        pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
        results = await self._col.aggregate(pipeline).to_list(length=None)
        return {r["_id"]: r["count"] for r in results}

    async def export_approved(self, job_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"status": QuestionStatus.APPROVED.value}
        if job_id:
            query["job_id"] = job_id
        cursor = self._col.find(query).sort("chunk_index", 1)
        return await cursor.to_list(length=None)
