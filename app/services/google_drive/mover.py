import asyncio
from typing import Optional
from app.core.logging import get_logger
from app.services.google_drive.client import get_drive_service
logger = get_logger(__name__)
async def move_file(file_id: str, destination_folder_id: str, source_folder_id: Optional[str]=None) -> bool:
    loop = asyncio.get_event_loop()
    service = get_drive_service()
    def _move() -> bool:
        add_parents = destination_folder_id
        remove_parents = ''
        if source_folder_id:
            remove_parents = source_folder_id
        else:
            meta = service.files().get(fileId=file_id, fields='parents').execute()
            current_parents = meta.get('parents', [])
            remove_parents = ','.join(current_parents)
        service.files().update(fileId=file_id, addParents=add_parents, removeParents=remove_parents, fields='id,parents').execute()
        return True
    try:
        result = await loop.run_in_executor(None, _move)
        logger.info('drive_mover.moved', file_id=file_id, destination=destination_folder_id)
        return result
    except Exception as exc:
        logger.error('drive_mover.failed', file_id=file_id, error=str(exc))
        return False
async def delete_file(file_id: str) -> bool:
    loop = asyncio.get_event_loop()
    service = get_drive_service()
    def _delete() -> None:
        service.files().delete(fileId=file_id).execute()
    try:
        await loop.run_in_executor(None, _delete)
        logger.info('drive_mover.deleted', file_id=file_id)
        return True
    except Exception as exc:
        logger.error('drive_mover.delete_failed', file_id=file_id, error=str(exc))
        return False
