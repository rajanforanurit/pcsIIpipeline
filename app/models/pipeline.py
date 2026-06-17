"""Models for the Google Drive ETL pipeline."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.common import AuditMixin, BaseDocument, DocumentType, JobStatus, Language


# ---------------------------------------------------------------------------
# Drive file tracking
# ---------------------------------------------------------------------------

class DriveFileRecord(BaseDocument, AuditMixin):
    """Persistent record for every Drive file we have seen."""
    drive_file_id: str
    file_name: str
    md5_checksum: Optional[str] = None
    mime_type: str = "application/pdf"
    size_bytes: int = 0
    processed: bool = False
    processing_status: str = "new"   # new | processing | pending_review | approved | rejected | failed
    drive_job_id: Optional[str] = None   # links to DriveIngestionJob
    error_message: Optional[str] = None


class DriveWatcherState(BaseModel):
    """Persisted page-token for Changes API."""
    page_token: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------

class PipelineResult(BaseModel):
    success: bool
    pdf_name: str
    drive_file_id: str
    language: Optional[str] = None
    document_type: Optional[str] = None
    question_count: int = 0
    pending_json_file_id: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    processing_time_seconds: float = 0.0
    ocr_duration_seconds: float = 0.0
    ai_duration_seconds: float = 0.0
    total_pages: int = 0


# ---------------------------------------------------------------------------
# Drive ingestion job (extends regular job tracking for Drive-sourced PDFs)
# ---------------------------------------------------------------------------

class DriveIngestionJob(BaseDocument, AuditMixin):
    drive_file_id: str
    file_name: str
    status: JobStatus = JobStatus.PENDING
    document_type: Optional[str] = None
    language: Optional[Language] = None
    year: Optional[int] = None
    exam: Optional[str] = None
    paper: Optional[str] = None

    total_pages: int = 0
    question_count: int = 0
    pending_json_drive_id: Optional[str] = None
    processed_json_drive_id: Optional[str] = None
    log_drive_id: Optional[str] = None

    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    ocr_duration_seconds: float = 0.0
    ai_duration_seconds: float = 0.0
    processing_time_seconds: float = 0.0

    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pending review document (what admin sees in Pending Review panel)
# ---------------------------------------------------------------------------

class PendingQuestion(BaseModel):
    id: int
    year: int
    exam: str
    paper: str
    language: str
    question: str
    options: Dict[str, str]
    correct_answer: str


class PendingReviewDocument(BaseDocument, AuditMixin):
    """A JSON file sitting in GOOGLE_DRIVE_PENDING_JSON_FOLDER_ID."""
    drive_job_id: str
    drive_file_id: str            # file ID in unprocessed folder (the original PDF)
    pending_json_drive_id: str    # file ID of JSON in pending folder
    file_name: str
    document_type: Optional[str] = None
    language: Optional[str] = None
    year: Optional[int] = None
    exam: Optional[str] = None
    paper: Optional[str] = None
    question_count: int = 0
    questions: List[PendingQuestion] = Field(default_factory=list)
    status: str = "pending"     # pending | approved | rejected


# ---------------------------------------------------------------------------
# Admin approve / reject requests
# ---------------------------------------------------------------------------

class ApproveReviewRequest(BaseModel):
    questions: List[PendingQuestion]


class RejectReviewRequest(BaseModel):
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Processing log
# ---------------------------------------------------------------------------

class ProcessingLog(BaseModel):
    file_name: str
    drive_file_id: str
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
    outcome: str   # "approved" | "rejected" | "failed"
