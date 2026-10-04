from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import Priority


def _to_unit_interval(value):
    if isinstance(value, str):
        value = float(value.strip().rstrip("%"))
    if isinstance(value, (int, float)) and 1 < value <= 100:
        value = value / 100  # tolerate "92" or "92%"
    return value


class AIAnalysisResult(BaseModel):
    """Structured output the AI must return (validated before use)."""

    model_config = ConfigDict(extra="ignore")

    summary: str = Field(min_length=1, max_length=1200)
    category: str = Field(min_length=1, max_length=120)
    subcategory: str = Field(default="General", max_length=120)
    category_confidence: float = Field(ge=0, le=1)
    priority: Priority
    priority_score: float = Field(ge=0, le=1)
    priority_reason: str = Field(min_length=1)
    department: Optional[str] = None
    routing_reason: Optional[str] = None
    requires_human_review: bool = False
    human_review_reason: Optional[str] = None
    suggested_action: str = Field(min_length=1)
    draft_response: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("priority", mode="before")
    @classmethod
    def _priority(cls, v):
        if isinstance(v, Priority):
            return v
        return str(v).strip().upper() if v is not None else v

    @field_validator("category_confidence", "priority_score", mode="before")
    @classmethod
    def _scores(cls, v):
        return _to_unit_interval(v)

    @field_validator("subcategory", mode="before")
    @classmethod
    def _sub(cls, v):
        return v or "General"

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, v):
        if isinstance(v, str):
            v = [t for t in v.split(",")]
        return [str(t).strip().lower() for t in (v or []) if str(t).strip()][:10]


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    summary: str
    category: str
    subcategory: Optional[str]
    category_confidence: float
    priority: str
    priority_score: float
    priority_reason: Optional[str]
    assigned_department: str
    routing_reason: Optional[str]
    requires_human_review: bool
    human_review_reason: Optional[str]
    suggested_action: Optional[str]
    draft_response: str
    original_draft_response: Optional[str]
    response_approved: bool
    tags: list[str]
    ai_model_used: Optional[str]
    analysis_error: Optional[str]
    analyzed_at: datetime
