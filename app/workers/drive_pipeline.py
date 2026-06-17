import asyncio
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.logging import get_logger
from app.models.common import JobStatus
from app.models.pipeline import DriveIngestionJob, PendingQuestion, PendingReviewDocument
from app.repositories.drive_repository import DriveRepository
from app.services.ai.drive_provider import DriveAIProvider
from app.services.ai.chunker import chunk_text
from app.services.google_drive.downloader import download_pdf
from app.services.google_drive.mover import move_file
from app.services.google_drive.uploader import upload_json
from app.services.google_drive.logger import upload_processing_log
from app.services.ocr.paddle_ocr import extract_text_from_scanned_pdf
from app.services.pdf_detector import detect_pdf_type
from app.services.text_extractor import extract_text_from_pdf
from app.services.validators.pipeline_validator import normalise_question, validate_pipeline_questions
logger = get_logger(__name__)
_MAX_CHUNK_WORKERS = 3
async def run_drive_pipeline(drive_file_id: str, file_name: str, db: AsyncIOMotorDatabase) -> bool:
    repo = DriveRepository(db)
    started_at = datetime.now(timezone.utc)
    job_id: Optional[str] = None
    local_path: Optional[str] = None
    t_start = time.monotonic()
    ocr_duration = 0.0
    ai_duration = 0.0
    try:
        job = DriveIngestionJob(drive_file_id=drive_file_id, file_name=file_name, status=JobStatus.RUNNING, started_at=started_at)
        job_id = await repo.create_drive_job(job)
        logger.info('drive_pipeline.started', job_id=job_id, file=file_name)
        local_path = await download_pdf(drive_file_id, file_name)
        await repo.update_job_status(job_id, JobStatus.OCR)
        t_ocr_start = time.monotonic()
        pdf_type, total_pages = detect_pdf_type(local_path)
        await repo.update_job_field(job_id, 'total_pages', total_pages)
        if pdf_type.value == 'scanned':
            text = await extract_text_from_scanned_pdf(local_path)
        else:
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, extract_text_from_pdf, local_path)
        ocr_duration = time.monotonic() - t_ocr_start
        logger.info('drive_pipeline.ocr_done', job_id=job_id, chars=len(text), ocr_s=round(ocr_duration, 2))
        await repo.update_job_status(job_id, JobStatus.AI)
        t_ai_start = time.monotonic()
        provider = DriveAIProvider()
        try:
            chunks = chunk_text(text)
            semaphore = asyncio.Semaphore(_MAX_CHUNK_WORKERS)
            all_questions: List[Dict[str, Any]] = []
            meta: Dict[str, Any] = {}
            async def _process_chunk(idx: int, chunk: str) -> Dict[str, Any]:
                async with semaphore:
                    return await provider.extract_questions(chunk, chunk_index=idx)
            tasks = [_process_chunk(i, c) for i, c in enumerate(chunks)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    logger.warning('drive_pipeline.chunk_failed', error=str(res))
                    continue
                if not meta:
                    meta = {k: v for k, v in res.items() if k != 'questions'}
                all_questions.extend(res.get('questions', []))
        finally:
            await provider.close()
        ai_duration = time.monotonic() - t_ai_start
        logger.info('drive_pipeline.ai_done', job_id=job_id, raw_q=len(all_questions), ai_s=round(ai_duration, 2))
        await repo.update_job_status(job_id, JobStatus.VALIDATION)
        valid, invalid = validate_pipeline_questions(all_questions)
        warnings: List[str] = [f'Question {q.get('id', '?')} invalid: {q.get('_validation_errors', [])}' for q in invalid]
        normalised = [normalise_question(q) for q in valid]
        for i, q in enumerate(normalised, start=1):
            q['id'] = i
        document_type = meta.get('document_type', 'Other')
        language = meta.get('language', 'English')
        year = meta.get('year')
        exam = meta.get('exam', '')
        paper = meta.get('paper', '')
        pending_payload = {'drive_file_id': drive_file_id, 'file_name': file_name, 'document_type': document_type, 'language': language, 'year': year, 'exam': exam, 'paper': paper, 'question_count': len(normalised), 'questions': normalised}
        json_name = f'pending_{file_name.replace('.pdf', '')}_{job_id}.json'
        pending_json_id = await upload_json(settings.GOOGLE_DRIVE_PENDING_JSON_FOLDER_ID, json_name, pending_payload)
        pq_list = [PendingQuestion(**q) for q in normalised]
        review_doc = PendingReviewDocument(drive_job_id=job_id, drive_file_id=drive_file_id, pending_json_drive_id=pending_json_id, file_name=file_name, document_type=document_type, language=language, year=year, exam=exam, paper=paper, question_count=len(pq_list), questions=pq_list)
        await repo.create_pending_review(review_doc)
        total_s = time.monotonic() - t_start
        await repo.update_drive_job_finished(job_id=job_id, status=JobStatus.PENDING_REVIEW, pending_json_drive_id=pending_json_id, question_count=len(normalised), ocr_duration=ocr_duration, ai_duration=ai_duration, processing_time=total_s, warnings=warnings)
        await repo.mark_drive_file_processed(drive_file_id=drive_file_id, job_id=job_id, status='pending_review')
        finished_at = datetime.now(timezone.utc)
        await upload_processing_log(file_name=file_name, drive_file_id=drive_file_id, started_at=started_at, finished_at=finished_at, total_pages=total_pages, ocr_duration_seconds=ocr_duration, ai_duration_seconds=ai_duration, question_count=len(normalised), document_type=document_type, language=language, errors=[], warnings=warnings, outcome='pending_review')
        logger.info('drive_pipeline.complete', job_id=job_id, questions=len(normalised), pending_json=pending_json_id, total_s=round(total_s, 2))
        return True
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error('drive_pipeline.failed', file=file_name, error=str(exc))
        try:
            await move_file(drive_file_id, settings.GOOGLE_DRIVE_FAILED_FOLDER_ID, settings.GOOGLE_DRIVE_UNPROCESSED_FOLDER_ID)
        except Exception:
            pass
        if job_id:
            await repo.update_drive_job_finished(job_id=job_id, status=JobStatus.FAILED, pending_json_drive_id=None, question_count=0, ocr_duration=ocr_duration, ai_duration=ai_duration, processing_time=time.monotonic() - t_start, warnings=[], errors=[str(exc)])
        await repo.mark_drive_file_processed(drive_file_id=drive_file_id, job_id=job_id, status='failed', error_message=str(exc))
        try:
            finished_at = datetime.now(timezone.utc)
            await upload_processing_log(file_name=file_name, drive_file_id=drive_file_id, started_at=started_at, finished_at=finished_at, total_pages=0, ocr_duration_seconds=ocr_duration, ai_duration_seconds=ai_duration, question_count=0, document_type='Unknown', language='Unknown', errors=[str(exc)], warnings=[], outcome='failed')
        except Exception:
            pass
        return False
    finally:
        if local_path and settings.DELETE_LOCAL_TEMP_FILES:
            try:
                Path(local_path).unlink(missing_ok=True)
            except Exception:
                pass
