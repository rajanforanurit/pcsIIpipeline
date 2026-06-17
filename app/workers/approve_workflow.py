"""
Admin Approve Workflow.

When admin approves a PendingReviewDocument:
  1. Validate final questions
  2. Insert into MongoDB (englishquestions / hindiquestions)
  3. Move JSON: pending → processed_json
  4. Move PDF: unprocessed → processed_pdf
  5. Upload approval processing log
  6. Update PendingReviewDocument & DriveIngestionJob status

Rollback: if MongoDB insert fails, no file moves occur.
"""
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.logging import get_logger
from app.models.common import JobStatus, Language, QuestionStatus
from app.models.question import PCSQuestion, QuestionOptions
from app.repositories.drive_repository import DriveRepository
from app.repositories.question_repository import EnglishQuestionRepository, HindiQuestionRepository
from app.services.google_drive.logger import upload_processing_log
from app.services.google_drive.mover import move_file
from app.services.validators.pipeline_validator import validate_pipeline_questions, normalise_question

logger = get_logger(__name__)


async def run_approve_workflow(
    review_id: str,
    questions: List[Dict[str, Any]],
    db: AsyncIOMotorDatabase,
    approved_by: str = "admin",
) -> Dict[str, Any]:
    """
    Execute the full approve workflow.
    Returns dict with success, inserted_count, errors.
    """
    repo = DriveRepository(db)
    started_at = datetime.now(timezone.utc)

    review_doc = await repo.get_pending_review(review_id)
    if not review_doc:
        return {"success": False, "errors": [f"Review {review_id} not found"]}

    drive_job_id = review_doc.get("drive_job_id", "")
    drive_file_id = review_doc.get("drive_file_id", "")
    pending_json_id = review_doc.get("pending_json_drive_id", "")
    file_name = review_doc.get("file_name", "unknown.pdf")
    language_str = review_doc.get("language", "English")
    document_type = review_doc.get("document_type", "Other")

    # ------------------------------------------------------------------
    # 1. Final validation
    # ------------------------------------------------------------------
    valid, invalid = validate_pipeline_questions(questions)
    if not valid:
        return {"success": False, "errors": ["No valid questions after validation"], "invalid": len(invalid)}

    normalised = [normalise_question(q) for q in valid]
    for i, q in enumerate(normalised, start=1):
        q["id"] = i

    # ------------------------------------------------------------------
    # 2. Insert into MongoDB
    # ------------------------------------------------------------------
    language = Language.HINDI if "hindi" in language_str.lower() else Language.ENGLISH
    q_repo = (
        HindiQuestionRepository(db)
        if language == Language.HINDI
        else EnglishQuestionRepository(db)
    )

    pcs_questions = []
    for q in normalised:
        pcs_q = PCSQuestion(
            job_id=drive_job_id,
            question_no=q["id"],
            year=q["year"] or 0,
            exam=q["exam"] or "",
            paper=q["paper"] or "",
            language=language,
            question=q["question"],
            options=QuestionOptions(**q["options"]),
            correct_answer=q.get("correct_answer"),
            status=QuestionStatus.APPROVED,
            created_by=approved_by,
            updated_by=approved_by,
        )
        pcs_questions.append(pcs_q)

    try:
        inserted_ids = await q_repo.insert_many(pcs_questions)
    except Exception as exc:
        logger.error("approve_workflow.mongo_insert_failed", error=str(exc))
        return {"success": False, "errors": [f"MongoDB insert failed: {str(exc)}"]}

    logger.info("approve_workflow.inserted", count=len(inserted_ids), language=language.value)

    # ------------------------------------------------------------------
    # 3 & 4. Move files (only after successful insert)
    # ------------------------------------------------------------------
    move_errors: List[str] = []

    # Move JSON: pending → processed
    if pending_json_id and settings.GOOGLE_DRIVE_PROCESSED_JSON_FOLDER_ID:
        ok = await move_file(
            pending_json_id,
            settings.GOOGLE_DRIVE_PROCESSED_JSON_FOLDER_ID,
            settings.GOOGLE_DRIVE_PENDING_JSON_FOLDER_ID,
        )
        if not ok:
            move_errors.append("Failed to move JSON to processed folder")

    # Move PDF: unprocessed → processed_pdf
    if drive_file_id and settings.GOOGLE_DRIVE_PROCESSED_PDF_FOLDER_ID:
        ok = await move_file(
            drive_file_id,
            settings.GOOGLE_DRIVE_PROCESSED_PDF_FOLDER_ID,
            settings.GOOGLE_DRIVE_UNPROCESSED_FOLDER_ID,
        )
        if not ok:
            move_errors.append("Failed to move PDF to processed folder")

    # ------------------------------------------------------------------
    # 5. Upload approval log
    # ------------------------------------------------------------------
    finished_at = datetime.now(timezone.utc)
    try:
        await upload_processing_log(
            file_name=file_name,
            drive_file_id=drive_file_id,
            started_at=started_at,
            finished_at=finished_at,
            total_pages=review_doc.get("total_pages", 0),
            ocr_duration_seconds=0.0,
            ai_duration_seconds=0.0,
            question_count=len(inserted_ids),
            document_type=document_type,
            language=language_str,
            errors=move_errors,
            warnings=[f"Invalid questions skipped: {len(invalid)}"] if invalid else [],
            outcome="approved",
        )
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 6. Update statuses
    # ------------------------------------------------------------------
    await repo.set_pending_review_status(review_id, "approved")
    if drive_job_id:
        await repo.update_job_status(drive_job_id, JobStatus.APPROVED)
    await repo.mark_drive_file_processed(drive_file_id, drive_job_id, "approved")

    return {
        "success": True,
        "inserted_count": len(inserted_ids),
        "invalid_count": len(invalid),
        "move_errors": move_errors,
    }


async def run_reject_workflow(
    review_id: str,
    reason: Optional[str],
    db: AsyncIOMotorDatabase,
) -> Dict[str, Any]:
    """Mark a pending review as rejected, move JSON to failed (optional)."""
    repo = DriveRepository(db)

    review_doc = await repo.get_pending_review(review_id)
    if not review_doc:
        return {"success": False, "errors": [f"Review {review_id} not found"]}

    drive_job_id = review_doc.get("drive_job_id", "")
    drive_file_id = review_doc.get("drive_file_id", "")
    pending_json_id = review_doc.get("pending_json_drive_id", "")
    file_name = review_doc.get("file_name", "unknown.pdf")

    # Move JSON to failed folder if configured
    if pending_json_id and settings.GOOGLE_DRIVE_FAILED_FOLDER_ID:
        await move_file(
            pending_json_id,
            settings.GOOGLE_DRIVE_FAILED_FOLDER_ID,
            settings.GOOGLE_DRIVE_PENDING_JSON_FOLDER_ID,
        )

    await repo.set_pending_review_status(review_id, "rejected")
    if drive_job_id:
        await repo.update_job_status(drive_job_id, JobStatus.REJECTED)
    await repo.mark_drive_file_processed(drive_file_id, drive_job_id, "rejected")

    # Log
    try:
        now = datetime.now(timezone.utc)
        await upload_processing_log(
            file_name=file_name,
            drive_file_id=drive_file_id,
            started_at=now,
            finished_at=now,
            total_pages=0,
            ocr_duration_seconds=0.0,
            ai_duration_seconds=0.0,
            question_count=0,
            document_type=review_doc.get("document_type", "Unknown"),
            language=review_doc.get("language", "Unknown"),
            errors=[f"Rejected by admin. Reason: {reason}" if reason else "Rejected by admin."],
            warnings=[],
            outcome="rejected",
        )
    except Exception:
        pass

    logger.info("reject_workflow.complete", review_id=review_id, reason=reason)
    return {"success": True}
