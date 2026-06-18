import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.logging import get_logger
from app.models.common import JobStatus, QuestionStatus
from app.models.question import PCSQuestion, LanguageContent, QuestionOptions
from app.repositories.job_repository import JobRepository
from app.repositories.pending_review_repository import PendingReviewRepository
from app.repositories.question_repository import PCSQuestionRepository
from app.services.azure_blob.logger import upload_processing_log
from app.services.azure_blob.mover import move_blob
from app.services.azure_blob.client import FOLDER_UNPROCESSED, FOLDER_PROCESSED_PDF, FOLDER_FAILED

logger = get_logger(__name__)


async def run_approve_workflow(
    review_id: str,
    questions: List[Dict[str, Any]],
    db: AsyncIOMotorDatabase,
    approved_by: str = 'admin',
) -> Dict[str, Any]:
    review_repo = PendingReviewRepository(db)
    job_repo = JobRepository(db)
    q_repo = PCSQuestionRepository(db)
    started_at = datetime.now(timezone.utc)

    review_doc = await review_repo.get_by_id(review_id)
    if not review_doc:
        return {'success': False, 'errors': [f'Review {review_id} not found']}

    job_id = review_doc.get('job_id', '')
    blob_name = review_doc.get('blob_name', '')
    file_name = review_doc.get('file_name', 'unknown.pdf')
    document_type = review_doc.get('document_type', 'Other')

    valid = [q for q in questions if q.get('english') or q.get('hindi')]
    invalid_count = len(questions) - len(valid)

    if not valid:
        return {'success': False, 'errors': ['No valid questions after validation'], 'invalid': invalid_count}

    pcs_questions = []
    for i, q in enumerate(valid, start=1):
        english_data = q.get('english')
        hindi_data = q.get('hindi')

        english = LanguageContent(
            question=english_data['question'],
            options=QuestionOptions(**english_data['options']),
        ) if english_data else None

        hindi = LanguageContent(
            question=hindi_data['question'],
            options=QuestionOptions(**hindi_data['options']),
        ) if hindi_data else None

        pcs_q = PCSQuestion(
            job_id=job_id,
            question_no=q.get('id', i),
            year=q.get('year'),
            exam=q.get('exam') or '',
            english=english,
            hindi=hindi,
            marks=q.get('marks', 2.0),
            negativeMarks=q.get('negativeMarks', 0.66),
            answer=q.get('answer'),
            status=QuestionStatus.APPROVED,
            created_by=approved_by,
            updated_by=approved_by,
        )
        pcs_questions.append(pcs_q)

    try:
        inserted_ids = await q_repo.insert_many(pcs_questions)
    except Exception as exc:
        logger.error('approve_workflow.mongo_insert_failed', error=str(exc))
        return {'success': False, 'errors': [f'MongoDB insert failed: {str(exc)}']}

    logger.info('approve_workflow.inserted', count=len(inserted_ids))

    move_errors: List[str] = []
    if file_name:
        ok = await move_blob(FOLDER_UNPROCESSED, FOLDER_PROCESSED_PDF, file_name)
        if not ok:
            move_errors.append('Failed to move PDF to processed folder')

    finished_at = datetime.now(timezone.utc)
    try:
        await upload_processing_log(
            file_name=file_name,
            blob_name=blob_name,
            started_at=started_at,
            finished_at=finished_at,
            total_pages=0,
            ocr_duration_seconds=0.0,
            ai_duration_seconds=0.0,
            question_count=len(inserted_ids),
            document_type=document_type,
            language='bilingual',
            errors=move_errors,
            warnings=[f'Invalid questions skipped: {invalid_count}'] if invalid_count else [],
            outcome='approved',
        )
    except Exception:
        pass

    await review_repo.set_status(review_id, 'approved')
    if job_id:
        await job_repo.update_status(job_id, JobStatus.APPROVED)

    return {
        'success': True,
        'inserted_count': len(inserted_ids),
        'invalid_count': invalid_count,
        'move_errors': move_errors,
    }


async def run_reject_workflow(
    review_id: str,
    reason: Optional[str],
    db: AsyncIOMotorDatabase,
) -> Dict[str, Any]:
    review_repo = PendingReviewRepository(db)
    job_repo = JobRepository(db)

    review_doc = await review_repo.get_by_id(review_id)
    if not review_doc:
        return {'success': False, 'errors': [f'Review {review_id} not found']}

    job_id = review_doc.get('job_id', '')
    blob_name = review_doc.get('blob_name', '')
    file_name = review_doc.get('file_name', 'unknown.pdf')

    if file_name:
        await move_blob(FOLDER_UNPROCESSED, FOLDER_FAILED, file_name)

    await review_repo.set_status(review_id, 'rejected')
    if job_id:
        await job_repo.update_status(job_id, JobStatus.REJECTED)

    try:
        now = datetime.now(timezone.utc)
        await upload_processing_log(
            file_name=file_name,
            blob_name=blob_name,
            started_at=now,
            finished_at=now,
            total_pages=0,
            ocr_duration_seconds=0.0,
            ai_duration_seconds=0.0,
            question_count=0,
            document_type=review_doc.get('document_type', 'Unknown'),
            language='Unknown',
            errors=[f'Rejected by admin. Reason: {reason}' if reason else 'Rejected by admin.'],
            warnings=[],
            outcome='rejected',
        )
    except Exception:
        pass

    logger.info('reject_workflow.complete', review_id=review_id, reason=reason)
    return {'success': True}
