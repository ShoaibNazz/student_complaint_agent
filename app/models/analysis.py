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
    """AI and algorithmic triage analysis for student complaints (1:1 with complaints)."""
    __tablename__ = "complaint_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    complaint_id: Mapped[int] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE", onupdate="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    subcategory: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    category_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    priority: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    priority_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_department: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    routing_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    human_review_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    draft_response: Mapped[str] = mapped_column(Text, nullable=False)
    original_draft_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    ai_model_used: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    analysis_error: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    complaint: Mapped["Complaint"] = relationship(back_populates="analysis")
