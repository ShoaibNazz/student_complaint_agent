from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import ComplaintStatus, Priority
from app.schemas.analysis import AnalysisOut
from app.utils.text import clean_text

_OPTIONAL_TEXT = (
    "student_id",
    "email",
    "phone",
    "class_or_program",
    "subject",
    "account_type",
    "originating_campus",
    "target_campus",
    "attachment_path",
    "attachment_name",
)


class ComplaintCreate(BaseModel):
    student_name: str = Field(min_length=1, max_length=120)
    student_id: Optional[str] = Field(default=None, max_length=60)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=40)
    class_or_program: Optional[str] = Field(default=None, max_length=120)
    subject: Optional[str] = Field(default=None, max_length=120)
    account_type: Optional[str] = Field(default=None, max_length=30)
    originating_campus: Optional[str] = Field(default=None, max_length=120)
    target_campus: Optional[str] = Field(default=None, max_length=120)
    attachment_path: Optional[str] = Field(default=None, max_length=500)
    attachment_name: Optional[str] = Field(default=None, max_length=255)
    complaint_title: str = Field(min_length=3, max_length=200)
    complaint_text: str = Field(min_length=1, max_length=5000)

    @field_validator("student_name", "complaint_title", "complaint_text", mode="before")
    @classmethod
    def _clean_required(cls, v):
        return clean_text(v) if isinstance(v, str) else v

    @field_validator(*_OPTIONAL_TEXT, mode="before")
    @classmethod
    def _clean_optional(cls, v):
        if isinstance(v, str):
            v = clean_text(v)
            return v or None
        return v


class ComplaintUpdate(BaseModel):
    """Admin-editable contact/notes fields. The original complaint text cannot be changed."""

    student_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=40)
    class_or_program: Optional[str] = Field(default=None, max_length=120)
    subject: Optional[str] = Field(default=None, max_length=120)
    internal_notes: Optional[str] = Field(default=None, max_length=5000)


class StatusUpdate(BaseModel):
    status: ComplaintStatus
    note: Optional[str] = Field(default=None, max_length=500)


class AssignmentUpdate(BaseModel):
    category: Optional[str] = Field(default=None, max_length=120)
    subcategory: Optional[str] = Field(default=None, max_length=120)
    department: Optional[str] = Field(default=None, max_length=120)
    priority: Optional[Priority] = None


class ResponseUpdate(BaseModel):
    draft_response: str = Field(min_length=1, max_length=5000)
    approved: bool = False


class ComplaintReceipt(BaseModel):
    """Public response after submission - deliberately excludes AI analysis."""

    id: int
    complaint_number: str
    status: str
    message: str = "Your complaint has been received."


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_number: str
    student_name: str
    student_id: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    class_or_program: Optional[str]
    subject: Optional[str]
    account_type: Optional[str] = None
    originating_campus: Optional[str] = None
    target_campus: Optional[str] = None
    attachment_path: Optional[str] = None
    attachment_name: Optional[str] = None
    title: str
    complaint_text: str
    status: str
    analysis_status: str
    possible_duplicate: bool
    duplicate_of_id: Optional[int]
    internal_notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    analysis: Optional[AnalysisOut] = None


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    action: str
    previous_value: Optional[str]
    new_value: Optional[str]
    performed_by: str


class ComplaintDetailOut(ComplaintOut):
    history: list[HistoryOut] = []


class ComplaintListOut(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[ComplaintOut]


class DashboardStats(BaseModel):
    total: int
    new: int
    critical: int
    high: int
    requires_human_review: int
    resolved: int
    pending: int
    analysis_failed: int
    possible_duplicates: int
    by_category: dict[str, int]


class StudentComplaintSubmit(BaseModel):
    complaint_title: str = Field(min_length=3, max_length=200)
    subject: Optional[str] = Field(default=None, max_length=120)
    originating_campus: Optional[str] = Field(default=None, max_length=120)
    target_campus: Optional[str] = Field(default=None, max_length=120)
    class_or_program: Optional[str] = Field(default=None, max_length=120)
    complaint_text: str = Field(min_length=1, max_length=5000)


class StudentComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_number: str
    title: str
    status: str
    priority: Optional[str] = None
    category: Optional[str] = None
    assigned_department: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class StudentTimelineItem(BaseModel):
    step: str
    status_key: str
    is_completed: bool
    is_current: bool
    date_str: Optional[str] = None


class StudentComplaintDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_number: str
    student_name: str
    student_id: Optional[str] = None
    email: Optional[str] = None
    class_or_program: Optional[str] = None
    subject: Optional[str] = None
    account_type: Optional[str] = None
    originating_campus: Optional[str] = None
    target_campus: Optional[str] = None
    attachment_path: Optional[str] = None
    attachment_name: Optional[str] = None
    title: str
    complaint_text: str
    status: str
    created_at: datetime
    updated_at: datetime
    category: Optional[str] = None
    subcategory: Optional[str] = None
    priority: Optional[str] = None
    assigned_department: Optional[str] = None
    summary: Optional[str] = None
    official_response: Optional[str] = None
    timeline: list[StudentTimelineItem] = []


class StudentDashboardStats(BaseModel):
    total: int
    new: int
    under_review: int
    in_progress: int
    resolved: int
    closed: int
    pending: int

