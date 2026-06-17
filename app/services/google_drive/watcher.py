"""Google Drive Changes-API watcher – polls for new PDFs in the unprocessed folder."""
import asyncio
from typing import Dict, List, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.services.google_drive.client import get_drive_service

logger = get_logger(__name__)


async def get_start_page_token() -> str:
    """Fetch the current startPageToken from Drive Changes API."""
    loop = asyncio.get_event_loop()
    service = get_drive_service()

    def _fetch() -> str:
        resp = service.changes().getStartPageToken().execute()
        return resp.get("startPageToken", "")

    return await loop.run_in_executor(None, _fetch)


async def poll_new_pdfs(page_token: str) -> tuple[List[Dict], str]:
    """
    Poll Drive Changes API for new/modified PDF files in the unprocessed folder.
    Returns (list_of_file_metadata, next_page_token).
    """
    loop = asyncio.get_event_loop()
    service = get_drive_service()
    folder_id = settings.GOOGLE_DRIVE_UNPROCESSED_FOLDER_ID

    def _poll() -> tuple[List[Dict], str]:
        new_files: List[Dict] = []
        token = page_token

        while True:
            resp = service.changes().list(
                pageToken=token,
                spaces="drive",
                fields="nextPageToken,newStartPageToken,changes(fileId,removed,file(id,name,mimeType,md5Checksum,size,parents,trashed))",
                includeRemoved=False,
            ).execute()

            for change in resp.get("changes", []):
                if change.get("removed"):
                    continue
                file_meta = change.get("file", {})
                if not file_meta:
                    continue
                if file_meta.get("trashed"):
                    continue
                if file_meta.get("mimeType") != "application/pdf":
                    continue
                parents = file_meta.get("parents", [])
                if folder_id and folder_id not in parents:
                    continue
                new_files.append(file_meta)

            next_token = resp.get("nextPageToken")
            new_start = resp.get("newStartPageToken")

            if next_token:
                token = next_token
            else:
                return new_files, new_start or token

    result = await loop.run_in_executor(None, _poll)
    logger.info("drive_watcher.polled", new_files=len(result[0]))
    return result


async def list_existing_pdfs_in_unprocessed() -> List[Dict]:
    """List all PDF files currently sitting in the unprocessed folder (initial scan)."""
    loop = asyncio.get_event_loop()
    service = get_drive_service()
    folder_id = settings.GOOGLE_DRIVE_UNPROCESSED_FOLDER_ID

    def _list() -> List[Dict]:
        files: List[Dict] = []
        page_token: Optional[str] = None
        query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
        while True:
            resp = service.files().list(
                q=query,
                spaces="drive",
                fields="nextPageToken,files(id,name,mimeType,md5Checksum,size,parents)",
                pageToken=page_token,
            ).execute()
            files.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return files

    files = await loop.run_in_executor(None, _list)
    logger.info("drive_watcher.initial_scan", found=len(files))
    return files
