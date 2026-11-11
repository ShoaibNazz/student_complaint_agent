from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.enums import AnalysisStatus, ComplaintStatus
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.analysis import ComplaintAnalysis
    from app.models.assignment import ComplaintAssignment
    from app.models.campus import Campus
    from app.models.feedback import ComplaintFeedback
    from app.models.forwarding import ComplaintForwarding
    from app.models.history import ComplaintStatusHistory
    from app.models.user import Student, User


class Complaint(Base):
    """Core complaint entity tracking university grievance submissions."""
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    complaint_number: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    student_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    student_id_code: Mapped[Optional[str]] = mapped_column(String(60), index=True, nullable=True)
    student_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(254), index=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    class_or_program: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    account_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    originating_campus_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campuses.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    target_campus_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campuses.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    originating_campus: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    target_campus: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    attachment_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    attachment_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    complaint_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40), default=ComplaintStatus.NEW.value, index=True, nullable=False
    )
    is_confidential: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    analysis_status: Mapped[str] = mapped_column(
        String(20), default=AnalysisStatus.PENDING.value, nullable=False
    )
    possible_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_of_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("complaints.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    internal_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Hybrid property to maintain seamless backwards compatibility with complaint.student_id
    @hybrid_property
    def student_id(self) -> Optional[str]:
        return self.student_id_code

    @student_id.setter
    def student_id(self, val: Optional[str]) -> None:
        self.student_id_code = val

    @student_id.expression
    def student_id(cls):
        return cls.student_id_code

    # Relational Associations
    user: Mapped[Optional["User"]] = relationship(back_populates="complaints")
    student: Mapped[Optional["Student"]] = relationship(foreign_keys=[student_profile_id])
    originating_campus_rel: Mapped[Optional["Campus"]] = relationship(foreign_keys=[originating_campus_id])
    target_campus_rel: Mapped[Optional["Campus"]] = relationship(foreign_keys=[target_campus_id])

    analysis: Mapped[Optional["ComplaintAnalysis"]] = relationship(
        back_populates="complaint", uselist=False, cascade="all, delete-orphan"
    )
    history: Mapped[list["ComplaintStatusHistory"]] = relationship(
        back_populates="complaint", order_by="ComplaintStatusHistory.id", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["ComplaintAssignment"]] = relationship(
        back_populates="complaint", order_by="ComplaintAssignment.id", cascade="all, delete-orphan"
    )
    forwardings: Mapped[list["ComplaintForwarding"]] = relationship(
        back_populates="complaint", order_by="ComplaintForwarding.id", cascade="all, delete-orphan"
    )
    resolution_feedback: Mapped[Optional["ComplaintFeedback"]] = relationship(
        back_populates="complaint", uselist=False, cascade="all, delete-orphan"
    )
