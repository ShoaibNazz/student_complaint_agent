from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.enums import DeliveryStatus
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.request import EmployeeRequest
    from app.models.user import User


class Notification(Base):
    """Tracks queued and dispatched transactional emails and system notifications."""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    recipient_email: Mapped[str] = mapped_column(String(254), index=True, nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    related_complaint_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    related_request_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employee_requests.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    notification_type: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body_preview: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    delivery_status: Mapped[str] = mapped_column(
        String(30), default=DeliveryStatus.QUEUED.value, index=True, nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True, nullable=False)

    recipient_user: Mapped[Optional["User"]] = relationship(foreign_keys=[recipient_user_id])
    complaint: Mapped[Optional["Complaint"]] = relationship(foreign_keys=[related_complaint_id])
    request: Mapped[Optional["EmployeeRequest"]] = relationship(foreign_keys=[related_request_id])


# Backwards compatibility alias
EmailNotification = Notification
