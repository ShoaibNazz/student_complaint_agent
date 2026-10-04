from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.complaint import Complaint


class ComplaintHistory(Base):
    __tablename__ = "complaint_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    action: Mapped[str] = mapped_column(String(80))
    previous_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    performed_by: Mapped[str] = mapped_column(String(80), default="system")

    complaint: Mapped["Complaint"] = relationship(back_populates="history")
