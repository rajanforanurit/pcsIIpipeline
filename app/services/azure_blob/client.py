from azure.storage.blob.aio import BlobServiceClient
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

FOLDER_UNPROCESSED = 'unprocessed'
FOLDER_PROCESSED_PDF = 'processed_pdf'
FOLDER_PROCESSED_JSON = 'processed_json'
FOLDER_FAILED = 'failed'
FOLDER_PROCESSED_LOG = 'processed_log'


def get_blob_service_client() -> BlobServiceClient:
    # Always return a fresh async client — do NOT cache async clients
    # because async with closes the transport and lru_cache would return the closed instance
    return BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)


def get_container_name() -> str:
    return settings.AZURE_BLOB_CONTAINER_NAME
