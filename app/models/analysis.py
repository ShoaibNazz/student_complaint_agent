from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.complaint import Complaint


class ComplaintAnalysis(Base):
    __tablename__ = "complaint_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), unique=True, index=True)
    summary: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80), index=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    category_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    priority: Mapped[str] = mapped_column(String(10), index=True)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    priority_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_department: Mapped[str] = mapped_column(String(120), index=True)
    routing_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    human_review_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    draft_response: Mapped[str] = mapped_column(Text)  # editable by administrators
    original_draft_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # AI version, kept for audit
    response_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    ai_model_used: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    analysis_error: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    complaint: Mapped["Complaint"] = relationship(back_populates="analysis")
