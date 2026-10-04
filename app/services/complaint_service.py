"""Complaint use-cases: create, query, update, audit, dashboard statistics."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, contains_eager

from app.core.config import Settings, get_settings
from app.core.exceptions import ComplaintNotFound, ComplaintValidationError
from app.models.analysis import ComplaintAnalysis
from app.models.complaint import Complaint
from app.models.enums import FINISHED_STATUSES, OPEN_STATUSES, AnalysisStatus, ComplaintStatus, Priority
from app.models.user import User
from app.schemas.complaint import (AssignmentUpdate, ComplaintCreate, ComplaintUpdate, DashboardStats,
                                   ResponseUpdate, StatusUpdate, StudentDashboardStats, StudentTimelineItem)
from app.services import analysis_service
from app.services.category_service import get_catalog
from app.services.duplicate_service import find_possible_duplicate
from app.services.history_service import add_history
from app.services.routing_service import get_routing_service
from app.utils.text import assess_text_quality, truncate
from app.utils.time import utcnow

logger = logging.getLogger("complaint_agent.complaints")


# ---------------- creation ----------------
def _validate_payload(payload: ComplaintCreate, settings: Settings) -> None:
    errors: list[str] = []
    if settings.require_student_id and not payload.student_id:
        errors.append("Student ID is required.")
    if settings.require_email and not payload.email:
        errors.append("Email is required.")
    if len(payload.complaint_text) > settings.max_complaint_length:
        errors.append(f"The complaint is too long (max {settings.max_complaint_length} characters).")
    errors.extend(assess_text_quality(payload.complaint_text).errors)
    if errors:
        raise ComplaintValidationError(errors)


def create_complaint(
    db: Session,
    payload: ComplaintCreate,
    settings: Settings | None = None,
    user_id: int | None = None,
) -> Complaint:
    settings = settings or get_settings()
    _validate_payload(payload, settings)
    complaint = Complaint(
        user_id=user_id,
        complaint_number=f"TMP-{uuid.uuid4().hex}",
        student_name=payload.student_name, student_id=payload.student_id,
        email=str(payload.email) if payload.email else None, phone=payload.phone,
        class_or_program=payload.class_or_program, subject=payload.subject,
        title=payload.complaint_title, complaint_text=payload.complaint_text,
        status=ComplaintStatus.NEW.value, analysis_status=AnalysisStatus.PENDING.value,
    )
    try:
        db.add(complaint)
        db.flush()
        complaint.complaint_number = f"CMP-{utcnow().year}-{complaint.id:06d}"
        add_history(db, complaint.id, "Complaint created", None, complaint.complaint_number, "student")
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while saving a complaint")
        raise
    logger.info("Complaint created number=%s", complaint.complaint_number)

    try:
        match = find_possible_duplicate(db, student_id=complaint.student_id, email=complaint.email,
                                        title=complaint.title, text=complaint.complaint_text,
                                        exclude_id=complaint.id, settings=settings)
        if match:
            complaint.possible_duplicate, complaint.duplicate_of_id = True, match.complaint_id
            add_history(db, complaint.id, "Possible duplicate flagged", None, match.complaint_number, "system")
            db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Duplicate check failed")

    try:
        analysis_service.run_analysis(db, complaint)
    except Exception:  # the saved complaint must survive any analysis problem
        db.rollback()
        logger.exception("Unexpected analysis failure complaint=%s", complaint.complaint_number)
    db.refresh(complaint)
    return complaint


# ---------------- queries ----------------
def get_complaint(db: Session, complaint_id: int) -> Complaint:
    c = db.get(Complaint, complaint_id)
    if c is None or c.is_deleted:
        raise ComplaintNotFound(complaint_id)
    return c


@dataclass
class ComplaintFilters:
    q: Optional[str] = None
    priority: Optional[Priority] = None
    category: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = None
    requires_human_review: Optional[bool] = None
    analysis_status: Optional[str] = None
    sort: str = "newest"
    skip: int = 0
    limit: int = 50


def _esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def _conditions(f: ComplaintFilters) -> list:
    conds = [Complaint.is_deleted.is_(False)]
    if f.q and f.q.strip():
        like = f"%{_esc(f.q.strip())}%"
        conds.append(or_(*[col.ilike(like, escape="\\") for col in (
            Complaint.title, Complaint.complaint_text, Complaint.student_name, Complaint.complaint_number,
            Complaint.student_id, ComplaintAnalysis.summary)]))
    if f.priority:
        conds.append(ComplaintAnalysis.priority == f.priority.value)
    if f.category:
        conds.append(ComplaintAnalysis.category.ilike(f"%{_esc(f.category)}%", escape="\\"))
    if f.department:
        conds.append(ComplaintAnalysis.assigned_department.ilike(f"%{_esc(f.department)}%", escape="\\"))
    if f.status:
        s = f.status.strip().upper()
        if s == "OPEN":
            conds.append(Complaint.status.in_([x.value for x in OPEN_STATUSES]))
        else:
            try:
                conds.append(Complaint.status == ComplaintStatus(s).value)
            except ValueError:
                raise ComplaintValidationError([f"Unknown status '{f.status}'."])
    if f.requires_human_review is not None:
        conds.append(ComplaintAnalysis.requires_human_review.is_(f.requires_human_review))
    if f.analysis_status:
        conds.append(Complaint.analysis_status == f.analysis_status.upper())
    return conds


def list_complaints(db: Session, f: ComplaintFilters) -> tuple[list[Complaint], int]:
    conds = _conditions(f)
    join = Complaint.id == ComplaintAnalysis.complaint_id
    total = db.scalar(select(func.count(Complaint.id)).outerjoin(ComplaintAnalysis, join).where(*conds)) or 0
    rank = case({"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}, value=ComplaintAnalysis.priority, else_=0)
    order = {"oldest": [Complaint.created_at.asc()], "priority": [rank.desc(), Complaint.created_at.desc()]}.get(
        f.sort, [Complaint.created_at.desc()])
    stmt = (select(Complaint).outerjoin(ComplaintAnalysis, join).options(contains_eager(Complaint.analysis))
            .where(*conds).order_by(*order, Complaint.id.desc()).offset(f.skip).limit(f.limit))
    return list(db.scalars(stmt).unique()), total


def get_dashboard_stats(db: Session) -> DashboardStats:
    base = [Complaint.is_deleted.is_(False)]

    def count(*extra, analysis=False):
        stmt = select(func.count(Complaint.id))
        if analysis:
            stmt = stmt.join(ComplaintAnalysis, Complaint.id == ComplaintAnalysis.complaint_id)
        return db.scalar(stmt.where(*base, *extra)) or 0

    by_cat = db.execute(
        select(ComplaintAnalysis.category, func.count(ComplaintAnalysis.id))
        .join(Complaint, Complaint.id == ComplaintAnalysis.complaint_id).where(*base)
        .group_by(ComplaintAnalysis.category)).all()
    return DashboardStats(
        total=count(),
        new=count(Complaint.status == ComplaintStatus.NEW.value),
        critical=count(ComplaintAnalysis.priority == "CRITICAL", analysis=True),
        high=count(ComplaintAnalysis.priority == "HIGH", analysis=True),
        requires_human_review=count(ComplaintAnalysis.requires_human_review.is_(True), analysis=True),
        resolved=count(Complaint.status == ComplaintStatus.RESOLVED.value),
        pending=count(Complaint.status.notin_([s.value for s in FINISHED_STATUSES])),
        analysis_failed=count(Complaint.analysis_status == AnalysisStatus.FAILED.value),
        possible_duplicates=count(Complaint.possible_duplicate.is_(True)),
        by_category={k: v for k, v in by_cat},
    )


# ---------------- updates (each change is audited) ----------------
def update_complaint(db: Session, c: Complaint, data: ComplaintUpdate, by: str) -> Complaint:
    for field, value in data.model_dump(exclude_unset=True).items():
        value = str(value) if value is not None and field == "email" else value
        old = getattr(c, field)
        if value != old:
            setattr(c, field, value)
            shown = (lambda v: "(updated)") if field == "internal_notes" else (lambda v: v)
            add_history(db, c.id, "Internal notes updated" if field == "internal_notes" else f"{field} updated",
                        shown(old) if old else None, shown(value) if value else None, by)
    db.commit()
    return c


def update_status(db: Session, c: Complaint, data: StatusUpdate, by: str) -> Complaint:
    new = data.status.value
    if new != c.status:
        old = c.status
        c.status = new
        add_history(db, c.id, "Complaint resolved" if new == "RESOLVED" else "Status changed", old,
                    new + (f" - {truncate(data.note, 200)}" if data.note else ""), by)
        db.commit()
        logger.info("Status changed complaint=%s %s->%s", c.complaint_number, old, new)
    return c


def update_assignment(db: Session, c: Complaint, data: AssignmentUpdate, by: str) -> Complaint:
    a = c.analysis
    if a is None:
        raise ComplaintValidationError(["This complaint has no analysis yet. Run the analysis first."])
    catalog, routing = get_catalog(), get_routing_service()
    errors = []
    if data.category and data.category not in catalog.names:
        errors.append(f"Unknown category '{data.category}'.")
    if data.department and data.department not in routing.department_names:
        errors.append(f"Unknown department '{data.department}'.")
    if errors:
        raise ComplaintValidationError(errors)
    changes = [("category", "Category changed", data.category), ("subcategory", "Subcategory changed", data.subcategory),
               ("assigned_department", "Department changed", data.department),
               ("priority", "Priority changed", data.priority.value if data.priority else None)]
    for attr, action, value in changes:
        if value and value != getattr(a, attr):
            add_history(db, c.id, action, getattr(a, attr), value, by)
            setattr(a, attr, value)
            if attr == "assigned_department":
                logger.info("Department changed complaint=%s -> %s", c.complaint_number, value)
    db.commit()
    return c


def update_response(db: Session, c: Complaint, data: ResponseUpdate, by: str) -> Complaint:
    a = c.analysis
    if a is None:
        raise ComplaintValidationError(["This complaint has no analysis yet. Run the analysis first."])
    text = data.draft_response.strip()
    if text != a.draft_response:
        add_history(db, c.id, "Response edited", a.draft_response, text, by)
        a.draft_response = text
    if data.approved != a.response_approved:
        a.response_approved = data.approved
        add_history(db, c.id, "Response approved" if data.approved else "Response approval withdrawn", None, None, by)
    db.commit()
    return c


def reanalyze(db: Session, c: Complaint, by: str) -> Complaint:
    analysis_service.run_analysis(db, c, performed_by=f"AI (requested by {by})")
    db.refresh(c)
    return c


def soft_delete(db: Session, c: Complaint, by: str) -> None:
    """Soft delete keeps the audit trail intact."""
    c.is_deleted, c.deleted_at = True, utcnow()
    add_history(db, c.id, "Complaint deleted", None, None, by)
    db.commit()
    logger.info("Complaint deleted number=%s", c.complaint_number)


# ---------------- Role-Based Queries & Statistics ----------------
def get_student_complaints(db: Session, user: User) -> list[Complaint]:
    """Retrieve only complaints belonging to the authenticated student."""
    conds = [
        Complaint.is_deleted.is_(False),
        or_(Complaint.user_id == user.id, Complaint.student_id == user.student_id),
    ]
    stmt = (
        select(Complaint)
        .outerjoin(ComplaintAnalysis, Complaint.id == ComplaintAnalysis.complaint_id)
        .options(contains_eager(Complaint.analysis))
        .where(*conds)
        .order_by(Complaint.created_at.desc())
    )
    return list(db.scalars(stmt).unique())


def get_student_complaint(db: Session, complaint_id: int, user: User) -> Complaint:
    """Fetch complaint with strict ownership enforcement (prevents IDOR)."""
    c = get_complaint(db, complaint_id)
    is_owner = (c.user_id == user.id) or (user.student_id and c.student_id == user.student_id)
    if not is_owner:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Forbidden: You do not have permission to view this complaint.",
        )
    return c


def get_student_stats(db: Session, user: User) -> StudentDashboardStats:
    """Calculate dashboard statistics strictly for the logged-in student."""
    base = [
        Complaint.is_deleted.is_(False),
        or_(Complaint.user_id == user.id, Complaint.student_id == user.student_id),
    ]

    def count(*extra):
        return db.scalar(select(func.count(Complaint.id)).where(*base, *extra)) or 0

    return StudentDashboardStats(
        total=count(),
        new=count(Complaint.status == ComplaintStatus.NEW.value),
        under_review=count(Complaint.status == ComplaintStatus.UNDER_REVIEW.value),
        in_progress=count(Complaint.status.in_([
            ComplaintStatus.IN_PROGRESS.value,
            ComplaintStatus.ASSIGNED.value,
            ComplaintStatus.WAITING_FOR_STUDENT.value,
        ])),
        resolved=count(Complaint.status == ComplaintStatus.RESOLVED.value),
        closed=count(Complaint.status == ComplaintStatus.CLOSED.value),
        pending=count(Complaint.status.notin_([s.value for s in FINISHED_STATUSES])),
    )


def build_student_timeline(c: Complaint) -> list[StudentTimelineItem]:
    """Build clean visual timeline data without exposing internal administrative notes."""
    status_order = {
        ComplaintStatus.NEW.value: 1,
        ComplaintStatus.UNDER_REVIEW.value: 2,
        ComplaintStatus.ASSIGNED.value: 3,
        ComplaintStatus.IN_PROGRESS.value: 4,
        ComplaintStatus.WAITING_FOR_STUDENT.value: 4,
        ComplaintStatus.RESOLVED.value: 5,
        ComplaintStatus.CLOSED.value: 6,
        ComplaintStatus.REJECTED.value: 2,
    }
    current_rank = status_order.get(c.status, 1)

    dates_by_status: dict[str, str] = {
        "NEW": c.created_at.strftime("%d %b %Y"),
    }
    for h in c.history:
        if h.new_value:
            for s in ComplaintStatus:
                if s.value in h.new_value:
                    dates_by_status[s.value] = h.timestamp.strftime("%d %b %Y")

    dept_label = (
        f"Assigned to {c.analysis.assigned_department}"
        if c.analysis and c.analysis.assigned_department
        else "Assigned to Department"
    )

    steps = [
        ("Complaint Submitted", "NEW", 1),
        ("Under Review", "UNDER_REVIEW", 2),
        (dept_label, "ASSIGNED", 3),
        ("In Progress", "IN_PROGRESS", 4),
        ("Resolved", "RESOLVED", 5),
        ("Closed", "CLOSED", 6),
    ]

    items: list[StudentTimelineItem] = []
    for label, key, rank in steps:
        is_completed = current_rank > rank or (current_rank == rank and rank in (5, 6))
        is_current = (current_rank == rank and not is_completed)
        if c.status == key:
            is_current = True
            if key in ("RESOLVED", "CLOSED"):
                is_completed = True
        date_str = dates_by_status.get(key)
        items.append(StudentTimelineItem(
            step=label,
            status_key=key,
            is_completed=is_completed,
            is_current=is_current,
            date_str=date_str,
        ))
    return items


def get_employee_complaints(db: Session, user: User) -> list[Complaint]:
    """Complaints assigned to the employee's department."""
    conds = [Complaint.is_deleted.is_(False)]
    if user.department:
        conds.append(ComplaintAnalysis.assigned_department.ilike(f"%{user.department}%"))
    stmt = (
        select(Complaint)
        .outerjoin(ComplaintAnalysis, Complaint.id == ComplaintAnalysis.complaint_id)
        .options(contains_eager(Complaint.analysis))
        .where(*conds)
        .order_by(Complaint.created_at.desc())
    )
    return list(db.scalars(stmt).unique())


def get_employee_stats(db: Session, user: User) -> dict[str, int]:
    items = get_employee_complaints(db, user)
    return {
        "total": len(items),
        "pending": sum(1 for c in items if c.status not in [s.value for s in FINISHED_STATUSES]),
        "in_progress": sum(1 for c in items if c.status == ComplaintStatus.IN_PROGRESS.value),
        "resolved": sum(1 for c in items if c.status == ComplaintStatus.RESOLVED.value),
    }


def get_professor_complaints(db: Session, user: User) -> list[Complaint]:
    """Complaints relevant to the professor's department or academic category."""
    conds = [Complaint.is_deleted.is_(False)]
    if user.department:
        conds.append(or_(
            ComplaintAnalysis.assigned_department.ilike(f"%{user.department}%"),
            ComplaintAnalysis.category.ilike("Academic%"),
            Complaint.class_or_program.ilike(f"%{user.department}%"),
        ))
    stmt = (
        select(Complaint)
        .outerjoin(ComplaintAnalysis, Complaint.id == ComplaintAnalysis.complaint_id)
        .options(contains_eager(Complaint.analysis))
        .where(*conds)
        .order_by(Complaint.created_at.desc())
    )
    return list(db.scalars(stmt).unique())


def get_professor_stats(db: Session, user: User) -> dict[str, int]:
    items = get_professor_complaints(db, user)
    return {
        "total": len(items),
        "pending": sum(1 for c in items if c.status not in [s.value for s in FINISHED_STATUSES]),
        "in_progress": sum(1 for c in items if c.status == ComplaintStatus.IN_PROGRESS.value),
        "resolved": sum(1 for c in items if c.status == ComplaintStatus.RESOLVED.value),
    }

