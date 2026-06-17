import json
from datetime import datetime, timezone
from typing import Any, Dict, List
from app.core.config import settings
from app.core.logging import get_logger
from app.services.google_drive.uploader import upload_json
logger = get_logger(__name__)
async def upload_processing_log(file_name: str, drive_file_id: str, started_at: datetime, finished_at: datetime, total_pages: int, ocr_duration_seconds: float, ai_duration_seconds: float, question_count: int, document_type: str, language: str, errors: List[str], warnings: List[str], outcome: str) -> str:
    processing_time = (finished_at - started_at).total_seconds()
    log_data: Dict[str, Any] = {'file_name': file_name, 'drive_file_id': drive_file_id, 'started_at': started_at.isoformat(), 'finished_at': finished_at.isoformat(), 'processing_time_seconds': round(processing_time, 2), 'total_pages': total_pages, 'ocr_duration_seconds': round(ocr_duration_seconds, 2), 'ai_duration_seconds': round(ai_duration_seconds, 2), 'question_count': question_count, 'document_type': document_type, 'language': language, 'errors': errors, 'warnings': warnings, 'outcome': outcome}
    log_name = f'log_{file_name.replace('.pdf', '')}_{finished_at.strftime('%Y%m%d_%H%M%S')}.json'
    folder_id = settings.GOOGLE_DRIVE_PROCESSED_LOG_FOLDER_ID
    if not folder_id:
        logger.warning('drive_logger.no_log_folder_configured')
        return ''
    file_id = await upload_json(folder_id, log_name, log_data)
    logger.info('drive_logger.log_uploaded', log_name=log_name, file_id=file_id)
    return file_id
