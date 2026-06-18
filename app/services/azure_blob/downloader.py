import os
from pathlib import Path
from app.core.config import settings
from app.core.logging import get_logger
from app.services.azure_blob.client import get_blob_service_client, get_container_name, FOLDER_UNPROCESSED

logger = get_logger(__name__)


async def download_pdf(file_name: str) -> str:
    temp_dir = Path(settings.TEMP_DIR)
    temp_dir.mkdir(parents=True, exist_ok=True)
    local_path = str(temp_dir / file_name)
    full_blob_name = f"{FOLDER_UNPROCESSED}/{file_name}"
    container = get_container_name()

    async with get_blob_service_client() as client:
        blob_client = client.get_blob_client(container=container, blob=full_blob_name)
        stream = await blob_client.download_blob()
        data = await stream.readall()

    with open(local_path, 'wb') as fh:
        fh.write(data)

    size = os.path.getsize(local_path)
    logger.info('blob_downloader.downloaded', blob=full_blob_name, local_path=local_path, bytes=size)
    return local_path
