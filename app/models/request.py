from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.enums import RequestStatus
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.user import User


class EmployeeRequest(Base):
    """Staff administrative applications kept distinct from student complaints."""
    __tablename__ = "employee_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    employee_name: Mapped[str] = mapped_column(String(120))
    employee_id: Mapped[str] = mapped_column(String(60), index=True)
    department: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    campus: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    target_authority: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    attachment_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    attachment_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default=RequestStatus.SUBMITTED.value, index=True)
    current_stage: Mapped[str] = mapped_column(String(80), default="Reviewing Officer")
    reviewing_officer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewing_officer_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    approving_authority_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approving_authority_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    decision_remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    approvals: Mapped[list["RequestApproval"]] = relationship(
        back_populates="request", order_by="RequestApproval.id", cascade="all, delete-orphan"
    )


class RequestApproval(Base):
    __tablename__ = "request_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("employee_requests.id"), index=True)
    stage: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(120))
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    request: Mapped["EmployeeRequest"] = relationship(back_populates="approvals")
