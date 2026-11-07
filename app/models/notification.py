from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.enums import DeliveryStatus
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.request import EmployeeRequest


class EmailNotification(Base):
    """Tracks queued and dispatched transactional emails without revealing sensitive secrets."""
    __tablename__ = "email_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipient_email: Mapped[str] = mapped_column(String(254), index=True)
    recipient_name: Mapped[str] = mapped_column(String(120))
    related_complaint_id: Mapped[Optional[int]] = mapped_column(ForeignKey("complaints.id"), nullable=True, index=True)
    related_request_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employee_requests.id"), nullable=True, index=True)
    notification_type: Mapped[str] = mapped_column(String(60), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    body_preview: Mapped[str] = mapped_column(Text)
    delivery_status: Mapped[str] = mapped_column(String(30), default=DeliveryStatus.QUEUED.value, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
