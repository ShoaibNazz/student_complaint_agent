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


class ComplaintForwarding(Base):
    """Preserves the original complaint ID throughout all escalation stages."""
    __tablename__ = "complaint_forwardings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), index=True)
    forwarded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    forwarded_by_name: Mapped[str] = mapped_column(String(120))
    sender_authority: Mapped[str] = mapped_column(String(120))
    receiving_authority: Mapped[str] = mapped_column(String(120), index=True)
    recipient_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    forwarding_reason: Mapped[str] = mapped_column(Text)
    admin_remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(80))
    priority: Mapped[str] = mapped_column(String(20))
    forwarded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    response_status: Mapped[str] = mapped_column(String(40), default="PENDING")
    response_remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    complaint: Mapped["Complaint"] = relationship(back_populates="forwardings")
