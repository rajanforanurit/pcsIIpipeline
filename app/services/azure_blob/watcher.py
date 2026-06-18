from typing import Dict, List
from app.core.logging import get_logger
from app.services.azure_blob.client import get_blob_service_client, get_container_name, FOLDER_UNPROCESSED

logger = get_logger(__name__)


async def list_unprocessed_pdfs() -> List[Dict]:
    container = get_container_name()
    prefix = f"{FOLDER_UNPROCESSED}/"
    files: List[Dict] = []

    async with get_blob_service_client() as client:
        container_client = client.get_container_client(container)
        async for blob in container_client.list_blobs(name_starts_with=prefix):
            name = blob.name
            if not name.lower().endswith('.pdf'):
                continue
            file_name = name[len(prefix):]
            if not file_name:
                continue
            files.append({
                'blob_name': name,
                'file_name': file_name,
                'size': blob.size,
                'last_modified': blob.last_modified,
            })

    logger.info('blob_watcher.listed_unprocessed', count=len(files))
    return files


async def blob_exists(folder: str, file_name: str) -> bool:
    blob_name = f"{folder}/{file_name}"
    container = get_container_name()

    async with get_blob_service_client() as client:
        blob_client = client.get_blob_client(container=container, blob=blob_name)
        return await blob_client.exists()
