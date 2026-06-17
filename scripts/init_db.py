import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.mongodb import MongoDB
from app.db.indexes import create_indexes
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
setup_logging()
logger = get_logger(__name__)
async def init_db():
    logger.info("init_db.start")
    await MongoDB.connect()
    db = MongoDB.get_db()
    await create_indexes(db)
    logger.info("init_db.indexes_created")
    logger.info("init_db.complete")
    logger.info("admin.credentials", admin_id=settings.ADMIN_ID)
    await MongoDB.disconnect()
if __name__ == "__main__":
    asyncio.run(init_db())
