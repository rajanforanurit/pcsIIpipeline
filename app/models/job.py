from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.common import AuditMixin, BaseDocument, JobStatus, JobType, PDFType
class JobLog(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    level: str = Field(default='INFO')
    message: str
    details: Optional[Dict[str, Any]] = None
class JobError(BaseModel):
    stage: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    traceback: Optional[str] = None
class IngestionJob(BaseDocument, AuditMixin):
    job_type: JobType
    original_filename: str
    file_path: str
    year: Optional[int] = None
    exam: Optional[str] = None
    paper: Optional[str] = None
    set_name: Optional[str] = None
    book_title: Optional[str] = None
    book_author: Optional[str] = None
    subject: Optional[str] = None
    pdf_type: Optional[PDFType] = None
    total_pages: int = 0
    total_questions_found: int = 0
    total_questions_saved: int = 0
    status: JobStatus = Field(default=JobStatus.PENDING)
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    logs: List[JobLog] = Field(default_factory=list)
    errors: List[JobError] = Field(default_factory=list)
class EnglishIngestionRequest(BaseModel):
    year: int = Field(..., ge=1900, le=2100)
    exam: str = Field(..., min_length=1, max_length=100)
    paper: str = Field(..., min_length=1, max_length=50)
    set_name: Optional[str] = Field(default=None, max_length=10)
class HindiIngestionRequest(BaseModel):
    year: int = Field(..., ge=1900, le=2100)
    exam: str = Field(..., min_length=1, max_length=100)
    paper: str = Field(..., min_length=1, max_length=50)
    set_name: Optional[str] = Field(default=None, max_length=10)
class BilingualIngestionRequest(BaseModel):
    year: int = Field(..., ge=1900, le=2100)
    exam: str = Field(..., min_length=1, max_length=100)
    paper: str = Field(..., min_length=1, max_length=50)
    set_name: Optional[str] = Field(default=None, max_length=10)
class BookIngestionRequest(BaseModel):
    book_title: str = Field(..., min_length=1, max_length=200)
    book_author: Optional[str] = Field(default=None, max_length=100)
    subject: Optional[str] = Field(default=None, max_length=100)
class JobResponse(BaseModel):
    job_id: str
    job_type: JobType
    status: JobStatus
    progress_percent: float
    total_pages: int
    total_questions_found: int
    total_questions_saved: int
    original_filename: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    errors: List[JobError] = Field(default_factory=list)
class JobDetailResponse(JobResponse):
    logs: List[JobLog] = Field(default_factory=list)
    pdf_type: Optional[PDFType] = None
    year: Optional[int] = None
    exam: Optional[str] = None
    paper: Optional[str] = None
    book_title: Optional[str] = None
    subject: Optional[str] = None
class DashboardStats(BaseModel):
    total_jobs: int
    pending_jobs: int
    running_jobs: int
    failed_jobs: int
    draft_ready_jobs: int
    total_pcs_questions: int
    total_book_questions: int
    draft_pcs_questions: int
    draft_book_questions: int
    approved_pcs_questions: int
    approved_book_questions: int
