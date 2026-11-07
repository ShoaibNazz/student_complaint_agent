from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.user import User


class ComplaintAssignment(Base):
    __tablename__ = "complaint_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), index=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    department_name: Mapped[str] = mapped_column(String(120))
    handler_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    handler_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    assigned_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_by_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE")

    complaint: Mapped["Complaint"] = relationship(back_populates="assignments")
    handler: Mapped[Optional["User"]] = relationship(foreign_keys=[handler_id])
