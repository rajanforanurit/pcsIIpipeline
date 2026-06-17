import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.dependencies import get_current_admin
from app.core.logging import get_logger
from app.db.mongodb import get_db
from app.models.common import SuccessResponse
from app.models.question import BulkApproveRequest, PaginatedResponse, UpdatePCSQuestionRequest
from app.repositories.question_repository import HindiQuestionRepository

router = APIRouter(prefix="/questions/hindi", tags=["Hindi Questions Review"])
logger = get_logger(__name__)


def _serialize_doc(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    if "created_at" in doc:
        doc["created_at"] = doc["created_at"].isoformat() if hasattr(doc["created_at"], "isoformat") else str(doc["created_at"])
    if "updated_at" in doc:
        doc["updated_at"] = doc["updated_at"].isoformat() if hasattr(doc["updated_at"], "isoformat") else str(doc["updated_at"])
    return doc


@router.get("", response_model=PaginatedResponse)
async def list_hindi_questions(
    job_id: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    exam: Optional[str] = Query(default=None),
    year: Optional[int] = Query(default=None),
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PaginatedResponse:
    repo = HindiQuestionRepository(db)
    skip = (page - 1) * page_size
    total = await repo.count_questions(job_id=job_id, status=status_filter, exam=exam, year=year, search=search)
    docs = await repo.list_questions(job_id=job_id, status=status_filter, exam=exam, year=year, search=search, skip=skip, limit=page_size)
    items = [_serialize_doc(doc) for doc in docs]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=math.ceil(total / page_size) if total > 0 else 1)


@router.get("/{question_id}")
async def get_hindi_question(
    question_id: str,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = HindiQuestionRepository(db)
    doc = await repo.get_by_id(question_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Question {question_id} not found")
    return _serialize_doc(doc)


@router.patch("/{question_id}", response_model=SuccessResponse)
async def update_hindi_question(
    question_id: str,
    payload: UpdatePCSQuestionRequest,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SuccessResponse:
    repo = HindiQuestionRepository(db)
    doc = await repo.get_by_id(question_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Question {question_id} not found")
    update_data = payload.model_dump(exclude_none=True)
    if "options" in update_data and hasattr(update_data["options"], "model_dump"):
        update_data["options"] = update_data["options"].model_dump()
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    updated = await repo.update_question(question_id, update_data, updated_by=current_admin)
    if not updated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Update failed or no changes made")
    logger.info("question.hindi.updated", question_id=question_id, admin=current_admin)
    return SuccessResponse(message="Question updated successfully")


@router.delete("/{question_id}", response_model=SuccessResponse)
async def delete_hindi_question(
    question_id: str,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SuccessResponse:
    repo = HindiQuestionRepository(db)
    deleted = await repo.delete_question(question_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Question {question_id} not found")
    logger.info("question.hindi.deleted", question_id=question_id, admin=current_admin)
    return SuccessResponse(message="Question deleted successfully")


@router.post("/{question_id}/approve", response_model=SuccessResponse)
async def approve_hindi_question(
    question_id: str,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SuccessResponse:
    repo = HindiQuestionRepository(db)
    approved = await repo.approve_question(question_id, updated_by=current_admin)
    if not approved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Question {question_id} not found or already approved")
    logger.info("question.hindi.approved", question_id=question_id, admin=current_admin)
    return SuccessResponse(message="Question approved successfully")


@router.post("/bulk/approve", response_model=SuccessResponse)
async def bulk_approve_hindi_questions(
    payload: BulkApproveRequest,
    current_admin: str = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SuccessResponse:
    repo = HindiQuestionRepository(db)
    count = await repo.bulk_approve(payload.question_ids, updated_by=current_admin)
    logger.info("question.hindi.bulk_approved", count=count, admin=current_admin)
    return SuccessResponse(message=f"{count} questions approved successfully", data={"approved_count": count})