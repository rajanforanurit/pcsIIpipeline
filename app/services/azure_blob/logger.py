from datetime import datetime
from typing import Any, Dict, List
from app.core.logging import get_logger
from app.services.azure_blob.client import FOLDER_PROCESSED_LOG
from app.services.azure_blob.uploader import upload_json

logger = get_logger(__name__)


async def upload_processing_log(
    file_name: str,
    blob_name: str,
    started_at: datetime,
    finished_at: datetime,
    total_pages: int,
    ocr_duration_seconds: float,
    ai_duration_seconds: float,
    question_count: int,
    document_type: str,
    language: str,
    errors: List[str],
    warnings: List[str],
    outcome: str,
) -> str:
    processing_time = (finished_at - started_at).total_seconds()
    log_data: Dict[str, Any] = {
        'file_name': file_name,
        'blob_name': blob_name,
        'started_at': started_at.isoformat(),
        'finished_at': finished_at.isoformat(),
        'processing_time_seconds': round(processing_time, 2),
        'total_pages': total_pages,
        'ocr_duration_seconds': round(ocr_duration_seconds, 2),
        'ai_duration_seconds': round(ai_duration_seconds, 2),
        'question_count': question_count,
        'document_type': document_type,
        'language': language,
        'errors': errors,
        'warnings': warnings,
        'outcome': outcome,
    }
    stem = file_name.replace('.pdf', '')
    log_name = f"log_{stem}_{finished_at.strftime('%Y%m%d_%H%M%S')}.json"

    blob_path = await upload_json(FOLDER_PROCESSED_LOG, log_name, log_data)
    logger.info('blob_logger.log_uploaded', log_name=log_name, blob=blob_path)
    return blob_path
