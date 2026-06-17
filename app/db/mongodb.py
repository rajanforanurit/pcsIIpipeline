from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from app.core.config import settings
from app.core.logging import get_logger
logger = get_logger(__name__)
COLLECTION_INGESTION_JOBS: str = "ingestion_jobs"
COLLECTION_ENGLISH_QUESTIONS: str = "englishquestions" 
COLLECTION_HINDI_QUESTIONS: str = "hindiquestions"        
COLLECTION_BOOK_QUESTIONS: str = "bookquestions"
COLLECTION_ADMIN_USERS: str = "admin_users"
class MongoDB:
    _client: Optional[AsyncIOMotorClient] = None
    _db: Optional[AsyncIOMotorDatabase] = None

    @classmethod
    async def connect(cls) -> None:
        logger.info("mongodb.connecting")
        cls._client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=10_000,
            connectTimeoutMS=10_000,
            maxPoolSize=50,
            minPoolSize=10,
        )
        cls._db = cls._client[settings.MONGODB_DB_NAME]
        await cls._client.admin.command("ping")
        logger.info("mongodb.connected", db=settings.MONGODB_DB_NAME)

    @classmethod
    async def disconnect(cls) -> None:
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            cls._db = None
            logger.info("mongodb.disconnected")

    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        if cls._db is None:
            raise RuntimeError("MongoDB not connected. Call MongoDB.connect() first.")
        return cls._db

    @classmethod
    def get_collection(cls, name: str) -> AsyncIOMotorCollection:
        return cls.get_db()[name]

async def get_db() -> AsyncIOMotorDatabase:
    return MongoDB.get_db()
