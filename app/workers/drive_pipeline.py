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
from app.models.common import JobStatus, JobType, PDFType
from app.models.pipeline import PendingQuestion, PendingReviewDocument
from app.repositories.job_repository import JobRepository
from app.repositories.pending_review_repository import PendingReviewRepository
from app.services.ai.drive_provider import DriveAIProvider
from app.services.ai.chunker import chunk_text
from app.services.azure_blob.downloader import download_pdf
from app.services.azure_blob.mover import move_blob
from app.services.azure_blob.uploader import upload_json
from app.services.azure_blob.logger import upload_processing_log
from app.services.azure_blob.client import FOLDER_UNPROCESSED, FOLDER_PROCESSED_PDF, FOLDER_FAILED, FOLDER_PROCESSED_JSON
from app.services.ocr.paddle_ocr import extract_text_from_scanned_pdf
from app.services.pdf_detector import detect_pdf_type, assess_text_quality
from app.services.text_extractor import extract_text_from_pdf
from app.models.job import IngestionJob

logger = get_logger(__name__)
_MAX_CHUNK_WORKERS = 3
_MIN_TEXT_LENGTH = 200
_MIN_QUALITY_SCORE = 0.40


async def run_blob_pipeline(blob_name: str, file_name: str, db: AsyncIOMotorDatabase) -> bool:
    review_repo = PendingReviewRepository(db)
    job_repo = JobRepository(db)
    started_at = datetime.now(timezone.utc)
    job_id: Optional[str] = None
    local_path: Optional[str] = None
    t_start = time.monotonic()
    ocr_duration = 0.0
    ai_duration = 0.0
    total_pages = 0

    try:
        job = IngestionJob(
            job_type=JobType.BLOB,
            original_filename=file_name,
            file_path=blob_name,
            status=JobStatus.RUNNING,
        )
        job_id = await job_repo.create(job)
        logger.info('blob_pipeline.started', job_id=job_id, file=file_name)

        await job_repo.mark_started(job_id)

        # Download from blob
        local_path = await download_pdf(file_name)
        logger.info('blob_pipeline.downloaded', job_id=job_id, local_path=local_path)

        # OCR / text extraction
        await job_repo.update_status(job_id, JobStatus.OCR)
        t_ocr_start = time.monotonic()

        pdf_type, total_pages = detect_pdf_type(local_path)
        await job_repo.update_pdf_info(job_id, pdf_type.value, total_pages)
        logger.info('blob_pipeline.pdf_detected', job_id=job_id, pdf_type=pdf_type.value, pages=total_pages)

        if pdf_type == PDFType.SCANNED:
            text = await extract_text_from_scanned_pdf(local_path)
        else:
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, extract_text_from_pdf, local_path)
            # If text layer is poor quality, fall back to OCR
            quality = assess_text_quality(text)
            logger.info('blob_pipeline.text_quality', job_id=job_id, chars=len(text), quality=round(quality, 3))
            if len(text) < _MIN_TEXT_LENGTH or quality < _MIN_QUALITY_SCORE:
                logger.info('blob_pipeline.falling_back_to_ocr', job_id=job_id, reason='low quality or too short')
                text = await extract_text_from_scanned_pdf(local_path)

        ocr_duration = time.monotonic() - t_ocr_start
        logger.info('blob_pipeline.ocr_done', job_id=job_id, chars=len(text), ocr_s=round(ocr_duration, 2))

        if not text.strip():
            raise ValueError('No text extracted from PDF after OCR — PDF may be corrupted or image-only with no readable content')

        # AI extraction
        await job_repo.update_status(job_id, JobStatus.AI)
        t_ai_start = time.monotonic()
        provider = DriveAIProvider()
        try:
            chunks = chunk_text(text)
            logger.info('blob_pipeline.chunked', job_id=job_id, chunks=len(chunks))
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
                    logger.warning('blob_pipeline.chunk_failed', error=str(res))
                    continue
                if not meta:
                    meta = {k: v for k, v in res.items() if k != 'questions'}
                all_questions.extend(res.get('questions', []))
        finally:
            await provider.close()

        ai_duration = time.monotonic() - t_ai_start
        logger.info('blob_pipeline.ai_done', job_id=job_id, raw_q=len(all_questions), ai_s=round(ai_duration, 2))

        # Validation
        await job_repo.update_status(job_id, JobStatus.VALIDATION)
        valid = [q for q in all_questions if q.get('english') or q.get('hindi')]
        invalid_count = len(all_questions) - len(valid)
        warnings: List[str] = []
        if invalid_count:
            warnings.append(f'{invalid_count} questions skipped (missing both language sections)')

        # Deduplicate by question id
        seen_ids = set()
        deduped = []
        for q in valid:
            qid = q.get('id')
            if qid not in seen_ids:
                seen_ids.add(qid)
                deduped.append(q)
        valid = deduped

        # Re-number sequentially
        for i, q in enumerate(valid, start=1):
            q['id'] = i

        logger.info('blob_pipeline.validation_done', job_id=job_id, valid=len(valid), invalid=invalid_count)

        document_type = meta.get('document_type', 'Other')
        year = meta.get('year')
        exam = meta.get('exam', '')

        pending_payload = {
            'blob_name': blob_name,
            'file_name': file_name,
            'document_type': document_type,
            'year': year,
            'exam': exam,
            'question_count': len(valid),
            'questions': valid,
        }

        stem = file_name.replace('.pdf', '')
        json_name = f'pending_{stem}_{job_id}.json'
        pending_json_blob = await upload_json(FOLDER_PROCESSED_JSON, json_name, pending_payload)

        pq_list = [PendingQuestion(**q) for q in valid]
        review_doc = PendingReviewDocument(
            job_id=job_id,
            blob_name=blob_name,
            file_name=file_name,
            pending_json_blob=pending_json_blob,
            document_type=document_type,
            year=year,
            exam=exam,
            question_count=len(pq_list),
            questions=pq_list,
        )
        await review_repo.create(review_doc)

        total_s = time.monotonic() - t_start
        await job_repo.mark_finished(
            job_id,
            JobStatus.PENDING_REVIEW,
            total_questions_found=len(all_questions),
            total_questions_saved=len(valid),
        )

        finished_at = datetime.now(timezone.utc)
        await upload_processing_log(
            file_name=file_name,
            blob_name=blob_name,
            started_at=started_at,
            finished_at=finished_at,
            total_pages=total_pages,
            ocr_duration_seconds=ocr_duration,
            ai_duration_seconds=ai_duration,
            question_count=len(valid),
            document_type=document_type,
            language='bilingual',
            errors=[],
            warnings=warnings,
            outcome='pending_review',
        )

        logger.info(
            'blob_pipeline.complete',
            job_id=job_id,
            questions=len(valid),
            pending_json=pending_json_blob,
            total_s=round(total_s, 2),
        )
        return True

    except Exception as exc:
        tb = traceback.format_exc()
        logger.error('blob_pipeline.failed', file=file_name, error=str(exc))
        logger.debug('blob_pipeline.traceback', tb=tb)
        try:
            await move_blob(FOLDER_UNPROCESSED, FOLDER_FAILED, file_name)
        except Exception:
            pass
        if job_id:
            await job_repo.mark_finished(job_id, JobStatus.FAILED)
        try:
            finished_at = datetime.now(timezone.utc)
            await upload_processing_log(
                file_name=file_name,
                blob_name=blob_name,
                started_at=started_at,
                finished_at=finished_at,
                total_pages=total_pages,
                ocr_duration_seconds=ocr_duration,
                ai_duration_seconds=ai_duration,
                question_count=0,
                document_type='Unknown',
                language='Unknown',
                errors=[str(exc)],
                warnings=[],
                outcome='failed',
            )
        except Exception:
            pass
        return False

    finally:
        if local_path and settings.DELETE_LOCAL_TEMP_FILES:
            try:
                Path(local_path).unlink(missing_ok=True)
            except Exception:
                pass


# Keep backward-compatible name
run_drive_pipeline = run_blob_pipeline
