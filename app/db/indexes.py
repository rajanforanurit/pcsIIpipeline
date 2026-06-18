from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, TEXT, IndexModel
from app.core.logging import get_logger
from app.db.mongodb import (
    COLLECTION_INGESTION_JOBS,
    COLLECTION_PENDING_REVIEWS,
    COLLECTION_BOOK_QUESTIONS,
    COLLECTION_PCS_QUESTIONS,
)

logger = get_logger(__name__)

_PCS_INDEXES = [
    IndexModel([('year', ASCENDING)]),
    IndexModel([('exam', ASCENDING)]),
    IndexModel([('status', ASCENDING)]),
    IndexModel([('job_id', ASCENDING)]),
    IndexModel([('year', ASCENDING), ('exam', ASCENDING)]),
    IndexModel([('question_no', ASCENDING), ('job_id', ASCENDING)]),
    IndexModel([('english.question', TEXT)], name='pcs_question_text_search'),
]


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    jobs_col = db[COLLECTION_INGESTION_JOBS]
    await jobs_col.create_indexes([
        IndexModel([('status', ASCENDING)]),
        IndexModel([('created_at', DESCENDING)]),
        IndexModel([('job_type', ASCENDING), ('status', ASCENDING)]),
    ])
    logger.info('indexes.created', collection=COLLECTION_INGESTION_JOBS)

    pcs_col = db[COLLECTION_PCS_QUESTIONS]
    await pcs_col.create_indexes(_PCS_INDEXES)
    logger.info('indexes.created', collection=COLLECTION_PCS_QUESTIONS)

    book_col = db[COLLECTION_BOOK_QUESTIONS]
    await book_col.create_indexes([
        IndexModel([('book_title', ASCENDING)]),
        IndexModel([('status', ASCENDING)]),
        IndexModel([('job_id', ASCENDING)]),
        IndexModel([('created_at', DESCENDING)]),
        IndexModel([('question', TEXT)], name='book_question_text_search'),
    ])
    logger.info('indexes.created', collection=COLLECTION_BOOK_QUESTIONS)

    reviews_col = db[COLLECTION_PENDING_REVIEWS]
    await reviews_col.create_indexes([
        IndexModel([('status', ASCENDING)]),
        IndexModel([('job_id', ASCENDING)]),
        IndexModel([('blob_name', ASCENDING)]),
        IndexModel([('created_at', DESCENDING)]),
    ])
    logger.info('indexes.created', collection=COLLECTION_PENDING_REVIEWS)

    logger.info('indexes.all_created')
