import asyncio
import traceback
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.logging import get_logger
from app.models.common import JobStatus, PDFType
from app.models.job import JobError, JobLog
from app.models.question import BookQuestion, QuestionOptions
from app.repositories.job_repository import JobRepository
from app.repositories.question_repository import BookQuestionRepository
from app.services.pdf_detector import detect_pdf_type
from app.services.text_extractor import extract_text_from_pdf
from app.services.ocr.paddle_ocr import extract_text_from_scanned_pdf
from app.services.ai.chunker import chunk_text
from app.services.ai.provider_factory import get_ai_provider
from app.services.validators.book_question_validator import validate_book_questions, generate_book_validation_report
logger = get_logger(__name__)
_CONCURRENT_AI_REQUESTS = 3
async def run_book_ingestion(job_id: str, db: AsyncIOMotorDatabase) -> None:
    job_repo = JobRepository(db)
    q_repo = BookQuestionRepository(db)
    try:
        job_doc = await job_repo.get_by_id(job_id)
        if not job_doc:
            logger.error("ingestion.job_not_found", job_id=job_id)
            return
        await job_repo.mark_started(job_id)
        await job_repo.append_log(job_id, JobLog(level="INFO", message="Book ingestion started"))
        file_path = job_doc["file_path"]
        book_title = job_doc.get("book_title", "Unknown")
        book_author = job_doc.get("book_author", "")
        subject = job_doc.get("subject", "General")
        pdf_type, total_pages = detect_pdf_type(file_path)
        await job_repo.update_pdf_info(job_id, pdf_type.value, total_pages)
        await job_repo.append_log(job_id, JobLog(level="INFO", message=f"PDF type: {pdf_type.value}", details={"total_pages": total_pages}))
        if pdf_type == PDFType.SCANNED:
            await job_repo.update_status(job_id, JobStatus.OCR, 10.0)
            async def ocr_progress(pct: float):
                await job_repo.update_status(job_id, JobStatus.OCR, 10.0 + pct * 0.3)
            text = await extract_text_from_scanned_pdf(file_path, progress_callback=ocr_progress)
        else:
            await job_repo.update_status(job_id, JobStatus.RUNNING, 15.0)
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, extract_text_from_pdf, file_path)
        await job_repo.append_log(job_id, JobLog(level="INFO", message="Text extraction complete", details={"chars": len(text)}))
        chunks = chunk_text(text)
        await job_repo.append_log(job_id, JobLog(level="INFO", message="Text chunked", details={"chunk_count": len(chunks)}))
        await job_repo.update_status(job_id, JobStatus.PARSING, 40.0)
        provider = get_ai_provider()
        all_raw: List[dict] = []
        semaphore = asyncio.Semaphore(_CONCURRENT_AI_REQUESTS)
        async def process_chunk(idx: int, chunk: str):
            async with semaphore:
                try:
                    results = await provider.generate_questions(chunk=chunk, chunk_index=idx, book_title=book_title, subject=subject)
                    logger.info("ai.chunk_processed", chunk_index=idx, questions_generated=len(results))
                    return results
                except Exception as e:
                    logger.warning("ai.chunk_failed", chunk_index=idx, error=str(e))
                    await job_repo.append_log(job_id, JobLog(level="WARNING", message=f"AI failed for chunk {idx}: {str(e)[:100]}"))
                    return []
        tasks = [process_chunk(idx, chunk) for idx, chunk in enumerate(chunks)]
        chunk_results = await asyncio.gather(*tasks, return_exceptions=False)
        for results in chunk_results:
            all_raw.extend(results)
        progress_after_ai = 75.0
        await job_repo.update_status(job_id, JobStatus.VALIDATION, progress_after_ai)
        await job_repo.append_log(job_id, JobLog(level="INFO", message="AI generation complete", details={"total_raw": len(all_raw)}))
        valid, invalid = validate_book_questions(all_raw)
        report = generate_book_validation_report(valid, invalid, len(all_raw))
        await job_repo.append_log(job_id, JobLog(level="INFO", message="Validation complete", details=report))
        created_by = job_doc.get("created_by", "admin")
        questions = [
            BookQuestion(
                job_id=job_id,
                book_title=book_title,
                book_author=book_author if book_author else None,
                subject=subject if subject else None,
                chunk_index=q["chunk_index"],
                question=q["question"],
                options=QuestionOptions(**q["options"]),
                correct_answer=q["correct_answer"],
                explanation=q.get("explanation"),
                created_by=created_by,
                updated_by=created_by,
            )
            for q in valid
        ]
        inserted_ids = await q_repo.insert_many(questions)
        await job_repo.mark_finished(job_id, JobStatus.DRAFT_READY, total_questions_found=len(all_raw), total_questions_saved=len(inserted_ids))
        await job_repo.append_log(job_id, JobLog(level="INFO", message="Book ingestion complete", details={"saved": len(inserted_ids)}))
        logger.info("ingestion.book.complete", job_id=job_id, saved=len(inserted_ids))
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("ingestion.book.failed", job_id=job_id, error=str(exc))
        await job_repo.append_error(job_id, JobError(stage="book_ingestion", message=str(exc), traceback=tb))
        await job_repo.update_status(job_id, JobStatus.FAILED)
