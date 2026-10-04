from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.enums import UserRole
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.complaint import Complaint


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=UserRole.STUDENT.value, index=True)
    student_id: Mapped[Optional[str]] = mapped_column(String(60), unique=True, index=True, nullable=True)
    employee_id: Mapped[Optional[str]] = mapped_column(String(60), unique=True, index=True, nullable=True)
    professor_id: Mapped[Optional[str]] = mapped_column(String(60), unique=True, index=True, nullable=True)
    admin_id: Mapped[Optional[str]] = mapped_column(String(60), unique=True, index=True, nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    program: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    complaints: Mapped[list["Complaint"]] = relationship(back_populates="user")

    @property
    def identifier(self) -> str:
        if self.role == UserRole.STUDENT.value:
            return self.student_id or self.email
        if self.role == UserRole.EMPLOYEE.value:
            return self.employee_id or self.email
        if self.role == UserRole.PROFESSOR.value:
            return self.professor_id or self.email
        return self.admin_id or self.employee_id or "ADMIN-001"

    @property
    def username(self) -> str:
        return self.identifier


class UniversityDirectory(Base):
    """Official university roster of provisioned IDs before or after self-registration."""
    __tablename__ = "university_directory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role: Mapped[str] = mapped_column(String(20), index=True)
    identifier: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    department: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    program: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_claimed: Mapped[bool] = mapped_column(Boolean, default=False)

