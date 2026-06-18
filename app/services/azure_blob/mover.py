from app.core.logging import get_logger
from app.services.azure_blob.client import get_blob_service_client, get_container_name

logger = get_logger(__name__)


async def move_blob(source_folder: str, dest_folder: str, file_name: str) -> bool:
    source_blob = f"{source_folder}/{file_name}"
    dest_blob = f"{dest_folder}/{file_name}"

    client = get_blob_service_client()
    container = get_container_name()

    try:
        async with client:
            source_client = client.get_blob_client(container=container, blob=source_blob)
            dest_client = client.get_blob_client(container=container, blob=dest_blob)
            # Copy then delete
            source_url = source_client.url
            await dest_client.start_copy_from_url(source_url)
            await source_client.delete_blob()
        logger.info('blob_mover.moved', source=source_blob, dest=dest_blob)
        return True
    except Exception as exc:
        logger.error('blob_mover.failed', source=source_blob, dest=dest_blob, error=str(exc))
        return False


async def delete_blob(folder: str, file_name: str) -> bool:
    blob_name = f"{folder}/{file_name}"
    client = get_blob_service_client()
    container = get_container_name()

    try:
        async with client:
            blob_client = client.get_blob_client(container=container, blob=blob_name)
            await blob_client.delete_blob()
        logger.info('blob_mover.deleted', blob=blob_name)
        return True
    except Exception as exc:
        logger.error('blob_mover.delete_failed', blob=blob_name, error=str(exc))
        return False
