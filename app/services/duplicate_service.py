"""Basic duplicate detection (normalised text + keyword overlap + difflib).

`similarity_fn` is a module-level hook: replace it with an embedding-based function
(cosine similarity of vectors) later without changing callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from difflib import SequenceMatcher
from typing import Callable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.complaint import Complaint
from app.utils.text import keyword_set, normalize
from app.utils.time import utcnow


def lexical_similarity(a: str, b: str) -> float:
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    ratio = SequenceMatcher(None, na, nb).ratio()
    ka, kb = keyword_set(a), keyword_set(b)
    jaccard = len(ka & kb) / len(ka | kb) if ka | kb else 0.0
    return round(0.6 * ratio + 0.4 * jaccard, 4)


similarity_fn: Callable[[str, str], float] = lexical_similarity


@dataclass
class DuplicateMatch:
    complaint_id: int
    complaint_number: str
    score: float


def find_possible_duplicate(db: Session, *, student_id: str | None, email: str | None, title: str, text: str,
                            exclude_id: int | None = None, settings: Settings | None = None) -> DuplicateMatch | None:
    settings = settings or get_settings()
    identity = []
    if student_id:
        identity.append(Complaint.student_id == student_id)
    if email:
        identity.append(func.lower(Complaint.email) == email.lower())
    if not identity:
        return None
    cutoff = utcnow() - timedelta(days=settings.duplicate_window_days)
    stmt = select(Complaint).where(or_(*identity), Complaint.is_deleted.is_(False), Complaint.created_at >= cutoff)
    if exclude_id is not None:
        stmt = stmt.where(Complaint.id != exclude_id)
    best: DuplicateMatch | None = None
    for other in db.scalars(stmt):
        score = similarity_fn(f"{title} {text}", f"{other.title} {other.complaint_text}")
        if score >= settings.duplicate_threshold and (best is None or score > best.score):
            best = DuplicateMatch(other.id, other.complaint_number, score)
    return best
