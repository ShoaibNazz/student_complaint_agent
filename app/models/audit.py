from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(Base):
    """Security audit log for sensitive operations without exposing confidential identity records."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    user_identifier: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_type: Mapped[str] = mapped_column(String(50), index=True)
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    campus: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
