from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.logging import get_logger
from app.db.mongodb import COLLECTION_PENDING_REVIEWS
from app.models.pipeline import PendingReviewDocument

logger = get_logger(__name__)


class PendingReviewRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db[COLLECTION_PENDING_REVIEWS]

    async def create(self, doc: PendingReviewDocument) -> str:
        data = doc.model_dump(by_alias=True, exclude_none=True)
        data.pop('_id', None)
        result = await self._col.insert_one(data)
        return str(result.inserted_id)

    async def get_by_id(self, review_id: str) -> Optional[Dict[str, Any]]:
        if not ObjectId.is_valid(review_id):
            return None
        return await self._col.find_one({'_id': ObjectId(review_id)})

    async def list_reviews(
        self, status: str = 'pending', skip: int = 0, limit: int = 20
    ) -> List[Dict[str, Any]]:
        cursor = self._col.find({'status': status}).sort('created_at', -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_reviews(self, status: str = 'pending') -> int:
        return await self._col.count_documents({'status': status})

    async def update_questions(
        self, review_id: str, questions: List[Dict[str, Any]]
    ) -> bool:
        result = await self._col.update_one(
            {'_id': ObjectId(review_id)},
            {
                '$set': {
                    'questions': questions,
                    'question_count': len(questions),
                    'updated_at': datetime.now(timezone.utc),
                }
            },
        )
        return result.modified_count > 0

    async def set_status(self, review_id: str, status: str) -> bool:
        result = await self._col.update_one(
            {'_id': ObjectId(review_id)},
            {'$set': {'status': status, 'updated_at': datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0
