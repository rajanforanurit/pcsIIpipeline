import asyncio
import traceback
from typing import Any, Dict, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.logging import get_logger
from app.models.common import JobStatus, PDFType
from app.models.job import JobError, JobLog
from app.models.question import BilingualQuestion, LanguageContent, QuestionOptions
from app.repositories.job_repository import JobRepository
from app.repositories.question_repository import BilingualQuestionRepository
from app.services.pdf_detector import detect_pdf_type, assess_text_quality
from app.services.text_extractor import extract_text_from_pdf
from app.services.ocr.paddle_ocr import extract_text_from_scanned_pdf
from app.services.question_detector import detect_question_boundaries, strip_leading_question_marker
from app.services.language_detector import analyze_text
from app.services.bilingual_splitter import split_question_block
from app.services.parsers.english_parser import parse_english_questions
from app.services.parsers.hindi_parser import parse_hindi_questions
from app.services.validators.question_validator import validate_bilingual_questions, generate_bilingual_validation_report
logger = get_logger(__name__)
_MIN_QUALITY_SCORE = 0.55
def _build_single_block_text(question_no: int, body: str) -> str:
    return f'{question_no}. {body}'.strip()
def _safe_exam_token(exam: str) -> str:
    return ''.join((ch for ch in exam if ch.isalnum()))
async def run_bilingual_ingestion(job_id: str, db: AsyncIOMotorDatabase) -> None:
    job_repo = JobRepository(db)
    q_repo = BilingualQuestionRepository(db)
    try:
        job_doc = await job_repo.get_by_id(job_id)
        if not job_doc:
            logger.error('ingestion.job_not_found', job_id=job_id)
            return
        await job_repo.mark_started(job_id)
        await job_repo.append_log(job_id, JobLog(level='INFO', message='Bilingual ingestion started'))
        file_path = job_doc['file_path']
        year = job_doc['year']
        exam = job_doc['exam']
        paper = job_doc['paper']
        set_name = job_doc.get('set_name')
        pdf_type, total_pages = detect_pdf_type(file_path)
        await job_repo.update_pdf_info(job_id, pdf_type.value, total_pages)
        await job_repo.append_log(job_id, JobLog(level='INFO', message=f'PDF type: {pdf_type.value}', details={'total_pages': total_pages}))
        async def ocr_progress(pct: float):
            await job_repo.update_status(job_id, JobStatus.OCR, 10.0 + pct * 0.3)
        if pdf_type == PDFType.SCANNED:
            await job_repo.update_status(job_id, JobStatus.OCR, 10.0)
            text = await extract_text_from_scanned_pdf(file_path, progress_callback=ocr_progress)
        else:
            await job_repo.update_status(job_id, JobStatus.RUNNING, 15.0)
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, extract_text_from_pdf, file_path)
            quality_score = assess_text_quality(text)
            await job_repo.append_log(job_id, JobLog(level='INFO', message='Text quality assessed', details={'quality_score': quality_score}))
            if quality_score < _MIN_QUALITY_SCORE:
                await job_repo.append_log(job_id, JobLog(level='WARNING', message='Low quality text detected, falling back to OCR'))
                await job_repo.update_status(job_id, JobStatus.OCR, 20.0)
                text = await extract_text_from_scanned_pdf(file_path, progress_callback=ocr_progress)
        await job_repo.append_log(job_id, JobLog(level='INFO', message='Text extraction complete', details={'chars': len(text)}))
        logger.info('ingestion.bilingual.text_extracted', job_id=job_id, chars=len(text))
        await job_repo.update_status(job_id, JobStatus.PARSING, 40.0)
        question_blocks = detect_question_boundaries(text)
        await job_repo.append_log(job_id, JobLog(level='INFO', message=f'Detected {len(question_blocks)} question blocks', details={'count': len(question_blocks)}))
        if not question_blocks and pdf_type != PDFType.SCANNED:
            await job_repo.append_log(job_id, JobLog(level='WARNING', message='No question blocks found, retrying with OCR'))
            await job_repo.update_status(job_id, JobStatus.OCR, 45.0)
            text = await extract_text_from_scanned_pdf(file_path, progress_callback=ocr_progress)
            await job_repo.append_log(job_id, JobLog(level='INFO', message='OCR re-extraction complete', details={'chars': len(text)}))
            question_blocks = detect_question_boundaries(text)
            await job_repo.append_log(job_id, JobLog(level='INFO', message=f'Re-detected {len(question_blocks)} question blocks after OCR', details={'count': len(question_blocks)}))
        combined_records: List[Dict[str, Any]] = []
        for block in question_blocks:
            qno = block['question_no']
            ratios = analyze_text(block['raw_block'])
            split_result = split_question_block(block)
            eng_body = strip_leading_question_marker(split_result['english_text'])
            hin_body = strip_leading_question_marker(split_result['hindi_text'])
            eng_synthetic = _build_single_block_text(qno, eng_body) if eng_body else ''
            hin_synthetic = _build_single_block_text(qno, hin_body) if hin_body else ''
            eng_parsed = parse_english_questions(text=eng_synthetic, year=year, exam=exam, paper=paper, set_name=set_name, job_id=job_id) if eng_synthetic else []
            hin_parsed = parse_hindi_questions(text=hin_synthetic, year=year, exam=exam, paper=paper, set_name=set_name, job_id=job_id) if hin_synthetic else []
            english_data = {'question': eng_parsed[0]['question'], 'options': eng_parsed[0]['options']} if eng_parsed else None
            hindi_data = {'question': hin_parsed[0]['question'], 'options': hin_parsed[0]['options']} if hin_parsed else None
            await job_repo.append_log(job_id, JobLog(level='INFO', message=f'Question {qno} split into English/Hindi', details={'hindi_ratio': ratios['hindi_ratio'], 'english_ratio': ratios['english_ratio'], 'english_found': english_data is not None, 'hindi_found': hindi_data is not None}))
            combined_records.append({'job_id': job_id, 'question_no': qno, 'year': year, 'exam': exam, 'paper': paper, 'set_name': set_name, 'english': english_data, 'hindi': hindi_data, 'correct_answer': None})
        english_parsed_count = sum((1 for r in combined_records if r['english']))
        hindi_parsed_count = sum((1 for r in combined_records if r['hindi']))
        await job_repo.append_log(job_id, JobLog(level='INFO', message='English questions parsed', details={'count': english_parsed_count}))
        await job_repo.append_log(job_id, JobLog(level='INFO', message='Hindi questions parsed', details={'count': hindi_parsed_count}))
        await job_repo.update_status(job_id, JobStatus.VALIDATION, 75.0)
        valid, invalid = validate_bilingual_questions(combined_records)
        report = generate_bilingual_validation_report(valid, invalid, len(combined_records))
        await job_repo.append_log(job_id, JobLog(level='INFO', message='Validation complete', details=report))
        created_by = job_doc.get('created_by', 'admin')
        questions: List[BilingualQuestion] = []
        for q in valid:
            questions.append(BilingualQuestion(job_id=job_id, question_no=q['question_no'], year=q['year'], exam=q['exam'], paper=q['paper'], set_name=q.get('set_name'), english=LanguageContent(question=q['english']['question'], options=QuestionOptions(**q['english']['options'])) if q.get('english') else None, hindi=LanguageContent(question=q['hindi']['question'], options=QuestionOptions(**q['hindi']['options'])) if q.get('hindi') else None, correct_answer=None, created_by=created_by, updated_by=created_by))
        inserted_ids = await q_repo.insert_many(questions)
        exam_token = _safe_exam_token(exam)
        for q, qid in zip(valid, inserted_ids):
            await job_repo.append_log(job_id, JobLog(level='INFO', message=f'Stored question {exam_token}{year}_Q{q['question_no']}', details={'question_id': qid}))
        await job_repo.mark_finished(job_id, JobStatus.DRAFT_READY, total_questions_found=len(combined_records), total_questions_saved=len(inserted_ids))
        await job_repo.append_log(job_id, JobLog(level='INFO', message='Bilingual ingestion complete', details={'saved': len(inserted_ids)}))
        logger.info('ingestion.bilingual.complete', job_id=job_id, saved=len(inserted_ids))
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error('ingestion.bilingual.failed', job_id=job_id, error=str(exc))
        await job_repo.append_error(job_id, JobError(stage='bilingual_ingestion', message=str(exc), traceback=tb))
        await job_repo.update_status(job_id, JobStatus.FAILED)
