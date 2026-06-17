from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, TEXT, IndexModel
from app.core.logging import get_logger
from app.db.mongodb import (
    COLLECTION_BOOK_QUESTIONS,
    COLLECTION_ENGLISH_QUESTIONS,
    COLLECTION_HINDI_QUESTIONS,
    COLLECTION_INGESTION_JOBS,
)
from app.repositories.drive_repository import (
    COL_DRIVE_FILES,
    COL_DRIVE_JOBS,
    COL_PENDING_REVIEWS,
    COL_WATCHER_STATE,
)

logger = get_logger(__name__)

_QUESTION_INDEXES = [
    IndexModel([("year", ASCENDING)]),
    IndexModel([("exam", ASCENDING)]),
    IndexModel([("status", ASCENDING)]),
    IndexModel([("job_id", ASCENDING)]),
    IndexModel([("year", ASCENDING), ("exam", ASCENDING)]),
    IndexModel([("question_no", ASCENDING), ("job_id", ASCENDING)]),
    IndexModel([("question", TEXT)], name="question_text_search"),
]


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    # --- existing collections ---
    jobs_col = db[COLLECTION_INGESTION_JOBS]
    await jobs_col.create_indexes([
        IndexModel([("status", ASCENDING)]),
        IndexModel([("created_at", DESCENDING)]),
        IndexModel([("job_type", ASCENDING), ("status", ASCENDING)]),
    ])
    logger.info("indexes.created", collection=COLLECTION_INGESTION_JOBS)

    eng_col = db[COLLECTION_ENGLISH_QUESTIONS]
    await eng_col.create_indexes(_QUESTION_INDEXES)
    logger.info("indexes.created", collection=COLLECTION_ENGLISH_QUESTIONS)

    hin_col = db[COLLECTION_HINDI_QUESTIONS]
    await hin_col.create_indexes(_QUESTION_INDEXES)
    logger.info("indexes.created", collection=COLLECTION_HINDI_QUESTIONS)

    book_col = db[COLLECTION_BOOK_QUESTIONS]
    await book_col.create_indexes([
        IndexModel([("book_title", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("job_id", ASCENDING)]),
        IndexModel([("created_at", DESCENDING)]),
        IndexModel([("question", TEXT)], name="book_question_text_search"),
    ])
    logger.info("indexes.created", collection=COLLECTION_BOOK_QUESTIONS)

    # --- new Drive pipeline collections ---
    drive_files_col = db[COL_DRIVE_FILES]
    await drive_files_col.create_indexes([
        IndexModel([("drive_file_id", ASCENDING)], unique=True),
        IndexModel([("processed", ASCENDING)]),
        IndexModel([("processing_status", ASCENDING)]),
        IndexModel([("created_at", DESCENDING)]),
    ])
    logger.info("indexes.created", collection=COL_DRIVE_FILES)

    drive_jobs_col = db[COL_DRIVE_JOBS]
    await drive_jobs_col.create_indexes([
        IndexModel([("drive_file_id", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("created_at", DESCENDING)]),
    ])
    logger.info("indexes.created", collection=COL_DRIVE_JOBS)

    reviews_col = db[COL_PENDING_REVIEWS]
    await reviews_col.create_indexes([
        IndexModel([("status", ASCENDING)]),
        IndexModel([("drive_job_id", ASCENDING)]),
        IndexModel([("drive_file_id", ASCENDING)]),
        IndexModel([("created_at", DESCENDING)]),
    ])
    logger.info("indexes.created", collection=COL_PENDING_REVIEWS)

    logger.info("indexes.all_created")
