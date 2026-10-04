from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.history import ComplaintHistory
from app.utils.text import truncate


def add_history(db: Session, complaint_id: int, action: str, previous: str | None = None,
                new: str | None = None, performed_by: str = "system") -> ComplaintHistory:
    """Append an audit-trail entry (caller commits)."""
    entry = ComplaintHistory(
        complaint_id=complaint_id, action=action,
        previous_value=truncate(previous, 500) if previous is not None else None,
        new_value=truncate(new, 500) if new is not None else None,
        performed_by=performed_by,
    )
    db.add(entry)
    return entry
