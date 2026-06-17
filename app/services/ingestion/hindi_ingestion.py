import asyncio
import traceback
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.logging import get_logger
from app.models.common import JobStatus, PDFType
from app.models.job import JobError, JobLog
from app.models.question import PCSQuestion, QuestionOptions
from app.repositories.job_repository import JobRepository
from app.repositories.question_repository import HindiQuestionRepository
from app.services.pdf_detector import detect_pdf_type
from app.services.text_extractor import extract_text_from_pdf
from app.services.ocr.paddle_ocr import extract_text_from_scanned_pdf
from app.services.parsers.hindi_parser import parse_hindi_questions
from app.services.validators.question_validator import validate_questions, generate_validation_report
logger = get_logger(__name__)
async def run_hindi_ingestion(job_id: str, db: AsyncIOMotorDatabase) -> None:
    job_repo = JobRepository(db)
    q_repo = HindiQuestionRepository(db)
    try:
        job_doc = await job_repo.get_by_id(job_id)
        if not job_doc:
            logger.error('ingestion.job_not_found', job_id=job_id)
            return
        await job_repo.mark_started(job_id)
        await job_repo.append_log(job_id, JobLog(level='INFO', message='Hindi ingestion started'))
        file_path = job_doc['file_path']
        pdf_type, total_pages = detect_pdf_type(file_path)
        await job_repo.update_pdf_info(job_id, pdf_type.value, total_pages)
        await job_repo.append_log(job_id, JobLog(level='INFO', message=f'PDF type: {pdf_type.value}', details={'total_pages': total_pages}))
        if pdf_type == PDFType.SCANNED:
            await job_repo.update_status(job_id, JobStatus.OCR, 10.0)
            async def ocr_progress(pct: float):
                await job_repo.update_status(job_id, JobStatus.OCR, 10.0 + pct * 0.5)
            text = await extract_text_from_scanned_pdf(file_path, progress_callback=ocr_progress)
        else:
            await job_repo.update_status(job_id, JobStatus.RUNNING, 20.0)
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, extract_text_from_pdf, file_path)
        await job_repo.append_log(job_id, JobLog(level='INFO', message='Text extraction complete', details={'chars': len(text)}))
        await job_repo.update_status(job_id, JobStatus.PARSING, 60.0)
        raw = parse_hindi_questions(text=text, year=job_doc['year'], exam=job_doc['exam'], paper=job_doc['paper'], set_name=job_doc.get('set_name'), job_id=job_id)
        await job_repo.append_log(job_id, JobLog(level='INFO', message='Hindi parsing complete', details={'raw_count': len(raw)}))
        await job_repo.update_status(job_id, JobStatus.VALIDATION, 75.0)
        valid, invalid = validate_questions(raw)
        report = generate_validation_report(valid, invalid, len(raw))
        await job_repo.append_log(job_id, JobLog(level='INFO', message='Validation complete', details=report))
        created_by = job_doc.get('created_by', 'admin')
        questions = [PCSQuestion(job_id=job_id, question_no=q['question_no'], year=q['year'], exam=q['exam'], paper=q['paper'], language=q['language'], set_name=q.get('set_name'), question=q['question'], options=QuestionOptions(**q['options']), correct_answer=None, created_by=created_by, updated_by=created_by) for q in valid]
        inserted_ids = await q_repo.insert_many(questions)
        await job_repo.mark_finished(job_id, JobStatus.DRAFT_READY, total_questions_found=len(raw), total_questions_saved=len(inserted_ids))
        await job_repo.append_log(job_id, JobLog(level='INFO', message='Hindi ingestion complete', details={'saved': len(inserted_ids)}))
        logger.info('ingestion.hindi.complete', job_id=job_id, saved=len(inserted_ids))
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error('ingestion.hindi.failed', job_id=job_id, error=str(exc))
        await job_repo.append_error(job_id, JobError(stage='hindi_ingestion', message=str(exc), traceback=tb))
        await job_repo.update_status(job_id, JobStatus.FAILED)
