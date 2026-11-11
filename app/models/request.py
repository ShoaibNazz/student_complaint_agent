from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.enums import RequestStatus
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.campus import Campus, DepartmentRecord
    from app.models.user import Employee, User


class EmployeeRequest(Base):
    """Staff administrative applications kept distinct from student complaints."""
    __tablename__ = "employee_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_number: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
        nullable=False,
    )
    employee_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    employee_id_code: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    employee_name: Mapped[str] = mapped_column(String(120), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    department: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    campus_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campuses.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    campus: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    target_authority: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    attachment_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(40), default=RequestStatus.SUBMITTED.value, index=True, nullable=False
    )
    current_stage: Mapped[str] = mapped_column(String(80), default="Reviewing Officer", nullable=False)
    reviewing_officer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    reviewing_officer_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    approving_authority_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    approving_authority_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    decision_remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    @hybrid_property
    def employee_id(self) -> str:
        return self.employee_id_code

    @employee_id.setter
    def employee_id(self, val: str) -> None:
        self.employee_id_code = val

    @employee_id.expression
    def employee_id(cls):
        return cls.employee_id_code

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    employee_profile: Mapped[Optional["Employee"]] = relationship(foreign_keys=[employee_profile_id])
    department_rel: Mapped[Optional["DepartmentRecord"]] = relationship(foreign_keys=[department_id])
    campus_rel: Mapped[Optional["Campus"]] = relationship(foreign_keys=[campus_id])
    approvals: Mapped[list["RequestApproval"]] = relationship(
        back_populates="request", order_by="RequestApproval.id", cascade="all, delete-orphan"
    )


class RequestApproval(Base):
    """Multi-stage administrative review and recommendation tracking."""
    __tablename__ = "request_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("employee_requests.id", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
        nullable=False,
    )
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    actor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    request: Mapped["EmployeeRequest"] = relationship(back_populates="approvals")
    actor: Mapped[Optional["User"]] = relationship(foreign_keys=[actor_id])
