"""Google Drive authenticated client – single shared instance."""
import json
import os
from functools import lru_cache
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

from app.core.config import settings
from app.core.exceptions import GoogleDriveNotConfiguredError
from app.core.logging import get_logger

logger = get_logger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive"]


def _build_credentials() -> service_account.Credentials:
    raw = settings.GOOGLE_SERVICE_ACCOUNT_JSON
    if not raw:
        raise GoogleDriveNotConfiguredError()
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GoogleDriveNotConfiguredError() from exc
    return service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)


@lru_cache(maxsize=1)
def get_drive_service():
    """Return a cached Google Drive v3 service resource."""
    creds = _build_credentials()
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    logger.info("google_drive.client_initialized")
    return service
