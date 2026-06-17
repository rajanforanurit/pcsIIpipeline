import asyncio
import io
import os
from pathlib import Path
from googleapiclient.http import MediaIoBaseDownload
from app.core.config import settings
from app.core.logging import get_logger
from app.services.google_drive.client import get_drive_service
logger = get_logger(__name__)
async def download_pdf(file_id: str, file_name: str) -> str:
    temp_dir = Path(settings.TEMP_DIR)
    temp_dir.mkdir(parents=True, exist_ok=True)
    local_path = str(temp_dir / file_name)
    loop = asyncio.get_event_loop()
    service = get_drive_service()
    def _download() -> None:
        request = service.files().get_media(fileId=file_id)
        with open(local_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request, chunksize=8 * 1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()
    await loop.run_in_executor(None, _download)
    size = os.path.getsize(local_path)
    logger.info('drive_downloader.downloaded', file_id=file_id, local_path=local_path, bytes=size)
    return local_path
