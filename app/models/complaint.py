from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.enums import AnalysisStatus, ComplaintStatus
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.analysis import ComplaintAnalysis
    from app.models.history import ComplaintHistory
    from app.models.user import User


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    complaint_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    student_name: Mapped[str] = mapped_column(String(120))
    student_id: Mapped[Optional[str]] = mapped_column(String(60), index=True, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(254), index=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    class_or_program: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    complaint_text: Mapped[str] = mapped_column(Text)  # original text - never overwritten
    status: Mapped[str] = mapped_column(String(30), default=ComplaintStatus.NEW.value, index=True)
    analysis_status: Mapped[str] = mapped_column(String(20), default=AnalysisStatus.PENDING.value)
    possible_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[Optional[int]] = mapped_column(ForeignKey("complaints.id"), nullable=True)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[Optional["User"]] = relationship(back_populates="complaints")
    analysis: Mapped[Optional["ComplaintAnalysis"]] = relationship(
        back_populates="complaint", uselist=False, cascade="all, delete-orphan"
    )
    history: Mapped[list["ComplaintHistory"]] = relationship(
        back_populates="complaint", order_by="ComplaintHistory.id", cascade="all, delete-orphan"
    )
