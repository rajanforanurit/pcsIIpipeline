from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.common import AuditMixin, BaseDocument, DocumentType, JobStatus, Language


class PipelineResult(BaseModel):
    success: bool
    pdf_name: str
    blob_name: str
    language: Optional[str] = None
    document_type: Optional[str] = None
    question_count: int = 0
    pending_json_blob: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    processing_time_seconds: float = 0.0
    ocr_duration_seconds: float = 0.0
    ai_duration_seconds: float = 0.0
    total_pages: int = 0


class PendingQuestionLanguage(BaseModel):
    question: str
    options: Dict[str, str]


class PendingQuestion(BaseModel):
    id: int
    year: Optional[int] = None
    exam: Optional[str] = None
    paper: Optional[str] = None
    english: Optional[PendingQuestionLanguage] = None
    hindi: Optional[PendingQuestionLanguage] = None
    answer: Optional[str] = None
    marks: float = 2.0
    negativeMarks: float = 0.66
    status: str = 'pending'


class PendingReviewDocument(BaseDocument, AuditMixin):
    job_id: str
    blob_name: str
    file_name: str
    pending_json_blob: Optional[str] = None
    document_type: Optional[str] = None
    language: Optional[str] = None
    year: Optional[int] = None
    exam: Optional[str] = None
    paper: Optional[str] = None
    question_count: int = 0
    questions: List[PendingQuestion] = Field(default_factory=list)
    status: str = 'pending'


class ApproveReviewRequest(BaseModel):
    questions: List[PendingQuestion]


class RejectReviewRequest(BaseModel):
    reason: Optional[str] = None


class ProcessingLog(BaseModel):
    file_name: str
    blob_name: str
    started_at: datetime
    finished_at: datetime
    processing_time_seconds: float
    total_pages: int
    ocr_duration_seconds: float
    ai_duration_seconds: float
    question_count: int
    document_type: Optional[str] = None
    language: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    outcome: str
