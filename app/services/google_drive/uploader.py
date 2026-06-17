import asyncio
import io
import json as json_module
from typing import Any, Dict
from googleapiclient.http import MediaIoBaseUpload
from app.core.logging import get_logger
from app.services.google_drive.client import get_drive_service
logger = get_logger(__name__)
async def upload_json(folder_id: str, file_name: str, data: Any) -> str:
    loop = asyncio.get_event_loop()
    service = get_drive_service()
    json_bytes = json_module.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
    def _upload() -> str:
        file_metadata = {'name': file_name, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(json_bytes), mimetype='application/json', resumable=False)
        result = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return result.get('id', '')
    file_id = await loop.run_in_executor(None, _upload)
    logger.info('drive_uploader.uploaded', folder_id=folder_id, file_name=file_name, file_id=file_id)
    return file_id
async def upload_text(folder_id: str, file_name: str, content: str, mime_type: str='text/plain') -> str:
    loop = asyncio.get_event_loop()
    service = get_drive_service()
    text_bytes = content.encode('utf-8')
    def _upload() -> str:
        file_metadata = {'name': file_name, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(text_bytes), mimetype=mime_type, resumable=False)
        result = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return result.get('id', '')
    file_id = await loop.run_in_executor(None, _upload)
    logger.info('drive_uploader.uploaded_text', folder_id=folder_id, file_name=file_name, file_id=file_id)
    return file_id
async def download_json(file_id: str) -> Any:
    loop = asyncio.get_event_loop()
    service = get_drive_service()
    def _download() -> bytes:
        request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        from googleapiclient.http import MediaIoBaseDownload
        dl = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = dl.next_chunk()
        return buf.getvalue()
    raw = await loop.run_in_executor(None, _download)
    return json_module.loads(raw.decode('utf-8'))
