from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_serializer
class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    @classmethod
    def validate(cls, v: Any) -> str:
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str) and ObjectId.is_valid(v):
            return v
        raise ValueError(f'Invalid ObjectId: {v!r}')
class Language(str, Enum):
    ENGLISH = 'English'
    HINDI = 'Hindi'
class JobType(str, Enum):
    ENGLISH = 'English'
    HINDI = 'Hindi'
    BOOK = 'Book'
    BILINGUAL = 'Bilingual'
    DRIVE = 'Drive'
class JobStatus(str, Enum):
    PENDING = 'Pending'
    RUNNING = 'Running'
    OCR = 'OCR'
    PARSING = 'Parsing'
    AI = 'AI'
    VALIDATION = 'Validation'
    DRAFT_READY = 'Draft Ready'
    PENDING_REVIEW = 'Pending Review'
    APPROVED = 'Approved'
    REJECTED = 'Rejected'
    FAILED = 'Failed'
class QuestionStatus(str, Enum):
    DRAFT = 'draft'
    APPROVED = 'approved'
    REJECTED = 'rejected'
class PDFType(str, Enum):
    TEXT = 'text'
    SCANNED = 'scanned'
class DocumentType(str, Enum):
    UPSC_PYQ = 'UPSC PYQ'
    UPPCS_PYQ = 'UPPCS PYQ'
    HISTORY_BOOK = 'History Book'
    POLITY_BOOK = 'Polity Book'
    GEOGRAPHY_BOOK = 'Geography Book'
    ECONOMY_BOOK = 'Economy Book'
    ENVIRONMENT = 'Environment'
    SCIENCE = 'Science'
    CURRENT_AFFAIRS = 'Current Affairs'
    OTHER = 'Other'
class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, json_encoders={ObjectId: str})
    id: Optional[str] = Field(default=None, alias='_id')
    @field_serializer('id')
    def serialize_id(self, value: Optional[str]) -> Optional[str]:
        return str(value) if value else None
class AuditMixin(BaseModel):
    revision_number: int = Field(default=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default='admin')
    updated_by: str = Field(default='admin')
class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Any] = None
class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    details: Optional[Dict[str, Any]] = None
    status_code: int
