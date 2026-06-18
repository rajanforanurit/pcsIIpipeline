from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from app.models.common import AuditMixin, BaseDocument, QuestionStatus


class QuestionOptions(BaseModel):
    A: str = Field(..., min_length=1)
    B: str = Field(..., min_length=1)
    C: str = Field(..., min_length=1)
    D: str = Field(..., min_length=1)

    def as_dict(self) -> Dict[str, str]:
        return {'A': self.A, 'B': self.B, 'C': self.C, 'D': self.D}

    def values_list(self) -> List[str]:
        return [self.A, self.B, self.C, self.D]


class LanguageContent(BaseModel):
    question: str = Field(..., min_length=1)
    options: QuestionOptions


# pcsquestions collection schema: bilingual (English + Hindi)
class PCSQuestion(BaseDocument, AuditMixin):
    job_id: str
    question_no: int = Field(ge=1)
    year: Optional[int] = Field(default=None, ge=1900, le=2100)
    exam: Optional[str] = Field(default=None, max_length=100)
    paper: Optional[str] = Field(default=None, max_length=50)
    set_name: Optional[str] = Field(default=None, max_length=10)
    english: Optional[LanguageContent] = None
    hindi: Optional[LanguageContent] = None
    answer: Optional[str] = Field(default=None)
    status: QuestionStatus = Field(default=QuestionStatus.PENDING)
    reviewer_notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator('answer')
    @classmethod
    def validate_answer(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.upper() not in {'A', 'B', 'C', 'D'}:
            raise ValueError('answer must be A, B, C, or D')
        return v.upper() if v else None


class BookQuestion(BaseDocument, AuditMixin):
    job_id: str
    book_title: str = Field(min_length=1, max_length=200)
    book_author: Optional[str] = Field(default=None, max_length=100)
    subject: Optional[str] = Field(default=None, max_length=100)
    chunk_index: int = Field(ge=0)
    question: str = Field(min_length=1)
    options: QuestionOptions
    correct_answer: str
    explanation: Optional[str] = None
    status: QuestionStatus = Field(default=QuestionStatus.DRAFT)
    reviewer_notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator('correct_answer')
    @classmethod
    def validate_answer(cls, v: str) -> str:
        if v.upper() not in {'A', 'B', 'C', 'D'}:
            raise ValueError('correct_answer must be A, B, C, or D')
        return v.upper()


class UpdatePCSQuestionRequest(BaseModel):
    english: Optional[LanguageContent] = None
    hindi: Optional[LanguageContent] = None
    answer: Optional[str] = None
    reviewer_notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator('answer')
    @classmethod
    def validate_answer(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.upper() not in {'A', 'B', 'C', 'D'}:
            raise ValueError('answer must be A, B, C, or D')
        return v.upper() if v else None


class UpdateBookQuestionRequest(BaseModel):
    question: Optional[str] = Field(default=None, min_length=1)
    options: Optional[QuestionOptions] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    reviewer_notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator('correct_answer')
    @classmethod
    def validate_answer(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.upper() not in {'A', 'B', 'C', 'D'}:
            raise ValueError('correct_answer must be A, B, C, or D')
        return v.upper() if v else None


class BulkApproveRequest(BaseModel):
    question_ids: List[str] = Field(..., min_length=1)


class PCSQuestionResponse(BaseModel):
    id: Optional[str] = Field(default=None, alias='_id')
    job_id: str
    question_no: int
    year: Optional[int]
    exam: Optional[str]
    paper: Optional[str]
    set_name: Optional[str]
    english: Optional[LanguageContent]
    hindi: Optional[LanguageContent]
    answer: Optional[str]
    status: QuestionStatus
    reviewer_notes: Optional[str]
    revision_number: int
    created_at: str
    updated_at: str
    model_config = {'populate_by_name': True}


class BookQuestionResponse(BaseModel):
    id: Optional[str] = Field(default=None, alias='_id')
    job_id: str
    book_title: str
    subject: Optional[str]
    chunk_index: int
    question: str
    options: QuestionOptions
    correct_answer: str
    explanation: Optional[str]
    status: QuestionStatus
    reviewer_notes: Optional[str]
    revision_number: int
    created_at: str
    updated_at: str
    model_config = {'populate_by_name': True}


class PaginatedResponse(BaseModel):
    items: List
    total: int
    page: int
    page_size: int
    total_pages: int
