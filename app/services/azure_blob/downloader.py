import os
from pathlib import Path
from app.core.config import settings
from app.core.logging import get_logger
from app.services.azure_blob.client import get_blob_service_client, get_container_name, FOLDER_UNPROCESSED

logger = get_logger(__name__)


async def download_pdf(blob_name: str) -> str:
    temp_dir = Path(settings.TEMP_DIR)
    temp_dir.mkdir(parents=True, exist_ok=True)
    # blob_name may include folder prefix; use just filename for local path
    file_name = os.path.basename(blob_name)
    local_path = str(temp_dir / file_name)

    client = get_blob_service_client()
    container = get_container_name()
    full_blob_name = f"{FOLDER_UNPROCESSED}/{file_name}"

    async with client:
        blob_client = client.get_blob_client(container=container, blob=full_blob_name)
        with open(local_path, 'wb') as fh:
            stream = await blob_client.download_blob()
            data = await stream.readall()
            fh.write(data)

    size = os.path.getsize(local_path)
    logger.info('blob_downloader.downloaded', blob=full_blob_name, local_path=local_path, bytes=size)
    return local_path
