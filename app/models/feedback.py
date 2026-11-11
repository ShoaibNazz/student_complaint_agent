from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.user import User


class ComplaintFeedback(Base):
    """Records student confirmation or dispute of complaint resolution (1:1 with complaints)."""
    __tablename__ = "complaint_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    complaint_id: Mapped[int] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE", onupdate="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
        nullable=False,
    )
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    satisfaction_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    feedback_remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    reopened_review_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    complaint: Mapped["Complaint"] = relationship(back_populates="resolution_feedback")
    student: Mapped["User"] = relationship(foreign_keys=[student_id])


# Backwards compatibility alias
ResolutionFeedback = ComplaintFeedback
