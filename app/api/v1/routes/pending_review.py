"""
Pending Review Admin Panel routes.

Endpoints:
  GET    /api/v1/pending-review              – list pending reviews
  GET    /api/v1/pending-review/{id}         – get one review (full questions)
  PUT    /api/v1/pending-review/{id}         – update questions (edit before approve)
  POST   /api/v1/pending-review/{id}/approve – approve → MongoDB insert + move files
  POST   /api/v1/pending-review/{id}/reject  – reject
  GET    /api/v1/pending-review/{id}/preview – JSON preview of current questions
"""
import math
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_current_admin
from app.core.logging import get_logger
from app.db.mongodb import get_db
from app.models.common import SuccessResponse
from app.models.pipeline import ApproveReviewRequest, PendingQuestion, RejectReviewRequest
from app.models.question import PaginatedResponse
from app.repositories.drive_repository import DriveRepository
from app.workers.approve_workflow import run_approve_workflow, run_reject_workflow

router = APIRouter(prefix="/pending-review", tags=["Pending Review"])
logger = get_logger(__name__)


def _serialize_review(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("", response_model=PaginatedResponse)
async def list_pending_reviews(
    review_status: str = Query(default="pending", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PaginatedResponse:
    repo = DriveRepository(db)
    skip = (page - 1) * page_size
    total = await repo.count_pending_reviews(status=review_status)
    docs = await repo.list_pending_reviews(status=review_status, skip=skip, limit=page_size)

    items = []
    for doc in docs:
        item = {
            "id": str(doc.get("_id", "")),
            "file_name": doc.get("file_name", ""),
            "document_type": doc.get("document_type"),
            "language": doc.get("language"),
            "year": doc.get("year"),
            "exam": doc.get("exam"),
            "paper": doc.get("paper"),
            "question_count": doc.get("question_count", 0),
            "status": doc.get("status", "pending"),
            "created_at": doc.get("created_at"),
            "drive_job_id": doc.get("drive_job_id"),
        }
        items.append(item)

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/{review_id}")
async def get_pending_review(
    review_id: str,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    repo = DriveRepository(db)
    doc = await repo.get_pending_review(review_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Review {review_id} not found")
    return _serialize_review(doc)


@router.put("/{review_id}", response_model=SuccessResponse)
async def update_review_questions(
    review_id: str,
    payload: ApproveReviewRequest,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SuccessResponse:
    """Update/edit questions before approval."""
    repo = DriveRepository(db)
    doc = await repo.get_pending_review(review_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Review {review_id} not found")
    if doc.get("status") != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Review is in '{doc.get('status')}' state, cannot edit")

    questions_data = [q.model_dump() for q in payload.questions]
    ok = await repo.update_pending_review_questions(review_id, questions_data)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update questions")

    return SuccessResponse(message=f"Updated {len(questions_data)} questions")


@router.post("/{review_id}/approve", response_model=SuccessResponse)
async def approve_review(
    review_id: str,
    payload: ApproveReviewRequest,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SuccessResponse:
    """Approve: validate → insert MongoDB → move files."""
    doc = await DriveRepository(db).get_pending_review(review_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Review {review_id} not found")
    if doc.get("status") != "pending":
        raise HTTPException(status_code=409, detail=f"Review already '{doc.get('status')}'")

    questions_data = [q.model_dump() for q in payload.questions]
    result = await run_approve_workflow(review_id, questions_data, db, approved_by=current_admin)

    if not result["success"]:
        raise HTTPException(status_code=500, detail="; ".join(result.get("errors", ["Approval failed"])))

    msg = (
        f"Approved. Inserted {result['inserted_count']} questions into MongoDB. "
        f"Skipped {result.get('invalid_count', 0)} invalid questions."
    )
    if result.get("move_errors"):
        msg += f" File move warnings: {'; '.join(result['move_errors'])}"

    return SuccessResponse(message=msg, data=result)


@router.post("/{review_id}/reject", response_model=SuccessResponse)
async def reject_review(
    review_id: str,
    payload: RejectReviewRequest,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SuccessResponse:
    doc = await DriveRepository(db).get_pending_review(review_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Review {review_id} not found")
    if doc.get("status") != "pending":
        raise HTTPException(status_code=409, detail=f"Review already '{doc.get('status')}'")

    result = await run_reject_workflow(review_id, payload.reason, db)
    if not result["success"]:
        raise HTTPException(status_code=500, detail="; ".join(result.get("errors", ["Rejection failed"])))

    return SuccessResponse(message="Review rejected successfully")


@router.get("/{review_id}/preview")
async def preview_review_json(
    review_id: str,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    """Return the canonical JSON preview (what would be stored in MongoDB)."""
    repo = DriveRepository(db)
    doc = await repo.get_pending_review(review_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Review {review_id} not found")
    return {
        "file_name": doc.get("file_name"),
        "document_type": doc.get("document_type"),
        "language": doc.get("language"),
        "year": doc.get("year"),
        "exam": doc.get("exam"),
        "paper": doc.get("paper"),
        "question_count": doc.get("question_count", 0),
        "questions": doc.get("questions", []),
    }
