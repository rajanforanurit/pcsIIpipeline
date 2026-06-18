import json as json_module
from typing import Any
from app.core.logging import get_logger
from app.services.azure_blob.client import get_blob_service_client, get_container_name

logger = get_logger(__name__)


async def upload_json(folder: str, file_name: str, data: Any) -> str:
    json_bytes = json_module.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
    blob_name = f"{folder}/{file_name}"
    container = get_container_name()

    async with get_blob_service_client() as client:
        blob_client = client.get_blob_client(container=container, blob=blob_name)
        await blob_client.upload_blob(json_bytes, overwrite=True)

    logger.info('blob_uploader.uploaded', folder=folder, file_name=file_name, blob=blob_name)
    return blob_name


async def upload_bytes(folder: str, file_name: str, data: bytes, content_type: str = 'application/octet-stream') -> str:
    blob_name = f"{folder}/{file_name}"
    container = get_container_name()

    async with get_blob_service_client() as client:
        blob_client = client.get_blob_client(container=container, blob=blob_name)
        await blob_client.upload_blob(data, overwrite=True)

    logger.info('blob_uploader.uploaded_bytes', folder=folder, file_name=file_name)
    return blob_name
