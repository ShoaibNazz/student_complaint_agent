"""Complaint use-cases: create, query, update, audit, dashboard statistics."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, contains_eager, selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import ComplaintNotFound, ComplaintValidationError
from app.models.analysis import ComplaintAnalysis
from app.models.complaint import Complaint
from app.models.enums import FINISHED_STATUSES, OPEN_STATUSES, AnalysisStatus, ComplaintStatus, Priority, UserRole
from app.models.user import User
from app.schemas.complaint import (AssignmentUpdate, ComplaintCreate, ComplaintUpdate, DashboardStats,
                                   ResponseUpdate, StatusUpdate, StudentDashboardStats, StudentTimelineItem)
from app.services import analysis_service
from app.services.category_service import get_catalog
from app.services.duplicate_service import find_possible_duplicate
from app.services.history_service import add_history
from app.services.routing_service import get_routing_service
from app.models.assignment import ComplaintAssignment
from app.models.campus import DepartmentRecord
from app.models.clarification import ComplaintClarification
from app.models.feedback import ComplaintFeedback, ResolutionFeedback
from app.models.forwarding import ComplaintForwarding
from app.services.notification_service import NotificationService
from app.utils.text import assess_text_quality, truncate
from app.utils.time import utcnow

logger = logging.getLogger("complaint_agent.complaints")


DEFAULT_CAMPUSES: list[str] = [
    "Township Campus, Lahore (Main Campus)",
    "Lower Mall Campus, Lahore",
    "Bank Road Campus, Lahore",
    "Attock Campus",
    "Dera Ghazi Khan Campus",
    "Faisalabad Campus",
    "Jauharabad Campus",
    "Multan Campus",
    "Vehari Campus",
]

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
    "image/png",
    "image/x-png",
    "image/webp",
}
MAX_ATTACHMENT_BYTES = 500 * 1024  # 500 KB


def get_campus_names() -> list[str]:
    """Load available campuses from config/campuses.json with safe fallback."""
    from app.core.config import load_json_config
    try:
        data = load_json_config("campuses")
        names = [c["name"] for c in data.get("campuses", []) if c.get("name")]
        return names if names else list(DEFAULT_CAMPUSES)
    except Exception:
        return list(DEFAULT_CAMPUSES)


def _is_valid_image_header(content: bytes, ext: str) -> bool:
    if len(content) < 12:
        return False
    if ext in (".jpg", ".jpeg"):
        return content.startswith(b"\xff\xd8\xff")
    if ext == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".webp":
        return content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    return False


def save_complaint_attachment(upload_file) -> tuple[Optional[str], Optional[str]]:
    """Validate and persist an optional image attachment under /static/uploads/complaints."""
    from pathlib import Path
    from app.core.config import BASE_DIR

    if upload_file is None:
        return None, None

    raw_filename = (getattr(upload_file, "filename", None) or "").strip()
    if not raw_filename:
        return None, None

    # Read file bytes
    file_obj = getattr(upload_file, "file", None)
    if file_obj is not None:
        file_obj.seek(0)
        content = file_obj.read()
    else:
        content = b""

    if not content:
        raise ComplaintValidationError(["Uploaded image file is empty."])

    ext = Path(raw_filename).suffix.lower()
    raw_content_type = (getattr(upload_file, "content_type", None) or "").lower().strip()
    content_type = raw_content_type.split(";")[0].strip() if raw_content_type else ""

    if ext not in ALLOWED_IMAGE_EXTENSIONS or (content_type and content_type not in ALLOWED_IMAGE_MIME_TYPES and content_type != "application/octet-stream"):
        raise ComplaintValidationError(["Unsupported image format. Allowed formats: PNG, JPG, JPEG, WEBP."])

    if len(content) > MAX_ATTACHMENT_BYTES:
        raise ComplaintValidationError(["Attached image exceeds the maximum allowed size of 500 KB."])

    if not _is_valid_image_header(content, ext):
        raise ComplaintValidationError(["Invalid or corrupted image file. Please upload a valid PNG, JPG, JPEG, or WEBP image."])

    upload_dir = Path(BASE_DIR) / "app" / "static" / "uploads" / "complaints"
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = f"cmp_{uuid.uuid4().hex[:16]}{ext}"
    dest_path = upload_dir / safe_filename
    dest_path.write_bytes(content)

    clean_original = Path(raw_filename).name[:200]
    return f"/static/uploads/complaints/{safe_filename}", clean_original


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
    
    student_name = payload.student_name
    student_id = payload.student_id
    email_val = str(payload.email) if payload.email else None
    account_type = payload.account_type or "STUDENT"
    orig_campus = payload.originating_campus

    # Module 1.2: Automatically enforce verified user info from authenticated account
    if user_id:
        u = db.get(User, user_id)
        if u:
            student_name = u.full_name
            student_id = u.student_id or u.employee_id or u.identifier or student_id
            email_val = u.email or email_val
            account_type = u.role
            orig_campus = u.campus or orig_campus

    if not orig_campus:
        orig_campus = "Township Campus, Lahore (Main Campus)"
    targ_campus = payload.target_campus or orig_campus
    is_conf = getattr(payload, "is_confidential", False)

    from app.models.campus import Campus
    orig_rec = db.scalars(select(Campus).where(Campus.name == orig_campus)).first() if orig_campus else None
    targ_rec = db.scalars(select(Campus).where(Campus.name == targ_campus)).first() if targ_campus else None
    stu_prof_id = None
    if user_id:
        u_obj = db.get(User, user_id)
        if u_obj and u_obj.student_profile:
            stu_prof_id = u_obj.student_profile.id

    complaint = Complaint(
        user_id=user_id,
        student_profile_id=stu_prof_id,
        complaint_number=f"TMP-{uuid.uuid4().hex}",
        student_name=student_name,
        student_id=student_id,
        email=email_val,
        phone=payload.phone,
        class_or_program=payload.class_or_program,
        subject=payload.subject,
        account_type=account_type,
        originating_campus_id=orig_rec.id if orig_rec else None,
        target_campus_id=targ_rec.id if targ_rec else None,
        originating_campus=orig_campus,
        target_campus=targ_campus,
        attachment_path=payload.attachment_path,
        attachment_name=payload.attachment_name,
        title=payload.complaint_title,
        complaint_text=payload.complaint_text,
        status=ComplaintStatus.NEW.value,
        is_confidential=is_conf,
        analysis_status=AnalysisStatus.PENDING.value,
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
    campus: Optional[str] = None
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
    if f.campus:
        conds.append(or_(
            Complaint.target_campus == f.campus,
            Complaint.originating_campus == f.campus,
        ))
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
    raw_status = data.status.value
    # Module 2: Separate administrative resolution from student confirmation
    # If handler or administrator marks the complaint as Resolved, set to RESOLVED_AWAITING_CONFIRMATION
    if raw_status == ComplaintStatus.RESOLVED.value:
        new = ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value
    else:
        new = raw_status

    if new != c.status:
        old = c.status
        c.status = new
        action_name = (
            "Complaint marked resolved — awaiting student confirmation"
            if new == ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value
            else ("Complaint closed" if new == ComplaintStatus.CLOSED.value else "Status changed")
        )
        add_history(db, c.id, action_name, old,
                    new + (f" - {truncate(data.note, 200)}" if data.note else ""), by)
        db.commit()
        logger.info("Status changed complaint=%s %s->%s by=%s", c.complaint_number, old, new, by)

        # Automatically notify student when resolution awaits their confirmation
        if new == ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value:
            from app.services.notification_service import NotificationService
            NotificationService.send_resolution_pending_notification(db, c)
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

    # Record assignment record
    if data.department:
        dept_name = data.department
        h_id = getattr(data, "handler_id", None)
        h_name = getattr(data, "handler_name", None)
        if h_id and not h_name:
            handler_user = db.get(User, h_id)
            if handler_user:
                h_name = handler_user.full_name

        dept_rec = db.scalars(select(DepartmentRecord).where(DepartmentRecord.name == dept_name)).first()
        dept_id = dept_rec.id if dept_rec else None

        # Supersede any previous active assignments for this complaint
        for prev_asg in c.assignments:
            if getattr(prev_asg, "status", None) == "ACTIVE":
                prev_asg.status = "SUPERSEDED"

        assign_rec = ComplaintAssignment(
            complaint_id=c.id,
            department_id=dept_id,
            department_name=dept_name,
            handler_id=h_id,
            handler_name=h_name,
            assigned_by_name=by,
            assigned_at=utcnow(),
            notes=f"Assigned by {by}",
            status="ACTIVE",
        )
        db.add(assign_rec)
        if c.status in (ComplaintStatus.NEW.value, "PENDING"):
            old_st = c.status
            c.status = ComplaintStatus.ASSIGNED.value
            add_history(db, c.id, "Status changed", old_st, c.status, by)

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


def get_user_submitted_complaints(db: Session, user: User) -> list[Complaint]:
    """Retrieve all complaints submitted by the given user (Student, Employee, Professor, or Admin)."""
    user_conds = [Complaint.user_id == user.id]
    if user.email:
        user_conds.append(Complaint.email.ilike(user.email.strip()))
    if user.student_id:
        user_conds.append(Complaint.student_id.ilike(user.student_id.strip()))
    if user.employee_id:
        user_conds.append(Complaint.student_id.ilike(user.employee_id.strip()))
    if user.professor_id:
        user_conds.append(Complaint.student_id.ilike(user.professor_id.strip()))
    if user.admin_id:
        user_conds.append(Complaint.student_id.ilike(user.admin_id.strip()))

    stmt = (
        select(Complaint)
        .outerjoin(ComplaintAnalysis, Complaint.id == ComplaintAnalysis.complaint_id)
        .options(contains_eager(Complaint.analysis))
        .where(
            Complaint.is_deleted.is_(False),
            or_(*user_conds),
        )
        .order_by(Complaint.created_at.desc())
    )
    return list(db.scalars(stmt).unique())


def get_user_submitted_complaint(db: Session, complaint_id: int, user: User) -> Complaint:
    """Fetch complaint submitted by this user with strict ownership verification (prevents IDOR)."""
    c = get_complaint(db, complaint_id)
    identifiers = [
        ident.lower() for ident in [
            user.student_id,
            user.employee_id,
            user.professor_id,
            user.admin_id,
            user.identifier,
        ] if ident
    ]
    is_owner = (
        (c.user_id == user.id)
        or (user.email and c.email and c.email.lower() == user.email.lower())
        or (c.student_id and c.student_id.lower() in identifiers)
    )
    if not is_owner:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Forbidden: You do not have permission to view this complaint.",
        )
    return c


def get_user_submitted_stats(db: Session, user: User) -> dict[str, int]:
    """Calculate summary statistics for complaints submitted by the given user."""
    items = get_user_submitted_complaints(db, user)
    return {
        "total": len(items),
        "pending": sum(1 for c in items if c.status not in [s.value for s in FINISHED_STATUSES]),
        "in_progress": sum(1 for c in items if c.status in [
            ComplaintStatus.IN_PROGRESS.value,
            ComplaintStatus.ASSIGNED.value,
            ComplaintStatus.WAITING_FOR_STUDENT.value,
        ]),
        "resolved": sum(1 for c in items if c.status in [
            ComplaintStatus.RESOLVED.value,
            ComplaintStatus.CLOSED.value,
        ]),
    }


def build_student_timeline(c: Complaint) -> list[StudentTimelineItem]:
    """Build clean visual timeline data without exposing internal administrative notes."""
    status_order = {
        ComplaintStatus.NEW.value: 1,
        ComplaintStatus.UNDER_REVIEW.value: 2,
        ComplaintStatus.ASSIGNED.value: 3,
        ComplaintStatus.IN_PROGRESS.value: 4,
        ComplaintStatus.WAITING_FOR_STUDENT.value: 4,
        ComplaintStatus.REOPENED.value: 4,
        ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value: 5,
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
        ("Resolved — Awaiting Confirmation" if c.status == ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value else "Resolved", "RESOLVED", 5),
        ("Closed & Confirmed", "CLOSED", 6),
    ]

    items: list[StudentTimelineItem] = []
    for label, key, rank in steps:
        is_completed = current_rank > rank
        is_current = (current_rank == rank and not is_completed)
        if c.status == key or (key == "RESOLVED" and c.status == ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value):
            is_current = True
            if key == "CLOSED" or (key == "RESOLVED" and c.status == ComplaintStatus.RESOLVED.value):
                is_completed = True
        date_str = dates_by_status.get(key) or (dates_by_status.get(ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value) if key == "RESOLVED" else None)
        items.append(StudentTimelineItem(
            step=label,
            status_key=ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value if (key == "RESOLVED" and c.status == ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value) else key,
            is_completed=is_completed,
            is_current=is_current,
            date_str=date_str,
        ))
    return items


def get_employee_complaints(db: Session, user: User) -> list[Complaint]:
    """Complaints officially assigned by an administrator to the employee's department and campus."""
    conds = [Complaint.is_deleted.is_(False)]
    
    # Only visible if admin has assigned the complaint to the employee's department or directly to the employee
    from app.models.assignment import ComplaintAssignment
    if user.department:
        assignment_cond = or_(
            ComplaintAssignment.department_name.ilike(f"%{user.department}%"),
            ComplaintAssignment.handler_id == user.id,
        )
    else:
        assignment_cond = (ComplaintAssignment.handler_id == user.id)

    conds.append(assignment_cond)
    conds.append(ComplaintAssignment.status == "ACTIVE")

    if user.campus:
        conds.append(or_(
            Complaint.target_campus == user.campus,
            Complaint.originating_campus == user.campus,
            Complaint.target_campus.is_(None),
        ))
    stmt = (
        select(Complaint)
        .join(ComplaintAssignment, Complaint.id == ComplaintAssignment.complaint_id)
        .outerjoin(ComplaintAnalysis, Complaint.id == ComplaintAnalysis.complaint_id)
        .options(contains_eager(Complaint.analysis))
        .where(*conds)
        .order_by(Complaint.created_at.desc())
    )
    return list(db.scalars(stmt).unique())


def get_employee_complaint(db: Session, complaint_id: int, user: User) -> Complaint:
    """Fetch complaint with department and campus scope enforcement (prevents IDOR)."""
    c = get_complaint(db, complaint_id)
    # Verify complaint has an active assignment to this employee or their department
    is_assigned = False
    for a in c.assignments:
        if a.status == "ACTIVE":
            if a.handler_id == user.id:
                is_assigned = True
                break
            if user.department and a.department_name and user.department.lower() in a.department_name.lower():
                is_assigned = True
                break
    if not is_assigned:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Forbidden: This complaint has not been assigned to your department by an Administrator.",
        )
    if user.campus:
        campuses = [c.target_campus, c.originating_campus]
        if any(campuses) and user.campus not in campuses:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Forbidden: This complaint belongs to a different university campus.",
            )
    return c


def get_employee_stats(db: Session, user: User) -> dict[str, int]:
    items = get_employee_complaints(db, user)
    return {
        "total": len(items),
        "pending": sum(1 for c in items if c.status not in [s.value for s in FINISHED_STATUSES]),
        "in_progress": sum(1 for c in items if c.status == ComplaintStatus.IN_PROGRESS.value),
        "resolved": sum(1 for c in items if c.status == ComplaintStatus.RESOLVED.value),
    }


def get_professor_complaints(db: Session, user: User) -> list[Complaint]:
    """Complaints relevant to the professor's department, campus, or academic category."""
    conds = [Complaint.is_deleted.is_(False)]
    if user.department:
        conds.append(or_(
            ComplaintAnalysis.assigned_department.ilike(f"%{user.department}%"),
            ComplaintAnalysis.category.ilike("Academic%"),
            Complaint.class_or_program.ilike(f"%{user.department}%"),
        ))
    if user.campus:
        conds.append(or_(
            Complaint.target_campus == user.campus,
            Complaint.originating_campus == user.campus,
            Complaint.target_campus.is_(None),
        ))
    stmt = (
        select(Complaint)
        .outerjoin(ComplaintAnalysis, Complaint.id == ComplaintAnalysis.complaint_id)
        .options(contains_eager(Complaint.analysis))
        .where(*conds)
        .order_by(Complaint.created_at.desc())
    )
    return list(db.scalars(stmt).unique())


def get_professor_complaint(db: Session, complaint_id: int, user: User) -> Complaint:
    """Fetch complaint with campus scope enforcement (prevents IDOR)."""
    c = get_complaint(db, complaint_id)
    if user.campus:
        campuses = [c.target_campus, c.originating_campus]
        if any(campuses) and user.campus not in campuses:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Forbidden: This complaint belongs to a different university campus.",
            )
    return c


def get_professor_stats(db: Session, user: User) -> dict[str, int]:
    items = get_professor_complaints(db, user)
    return {
        "total": len(items),
        "pending": sum(1 for c in items if c.status not in [s.value for s in FINISHED_STATUSES]),
        "in_progress": sum(1 for c in items if c.status == ComplaintStatus.IN_PROGRESS.value),
        "resolved": sum(1 for c in items if c.status == ComplaintStatus.RESOLVED.value),
    }



# ---------------- Module 2: Resolution Feedback ----------------
def record_resolution_feedback(
    db: Session,
    complaint_id: int,
    user: User,
    is_resolved: bool,
    feedback_remarks: str = "",
    satisfaction_rating: Optional[int] = None,
) -> ResolutionFeedback:
    """Record student confirmation or dispute regarding complaint resolution."""
    c = get_complaint(db, complaint_id)
    is_owner = (
        (c.user_id == user.id)
        or (user.student_id and c.student_id == user.student_id)
        or (c.email and user.email and c.email.strip().lower() == user.email.strip().lower())
    )
    if not is_owner:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Forbidden: You can only confirm resolution for your own complaints.",
        )

    # Find existing or create new
    fb = db.scalar(select(ResolutionFeedback).where(ResolutionFeedback.complaint_id == c.id))
    if fb is None:
        fb = ResolutionFeedback(
            complaint_id=c.id,
            student_id=user.id,
            is_resolved=is_resolved,
            satisfaction_rating=satisfaction_rating,
            feedback_remarks=feedback_remarks.strip() or None,
            confirmed_at=utcnow(),
        )
        db.add(fb)
    else:
        fb.is_resolved = is_resolved
        fb.satisfaction_rating = satisfaction_rating
        fb.feedback_remarks = feedback_remarks.strip() or None
        fb.confirmed_at = utcnow()

    if is_resolved:
        c.status = ComplaintStatus.CLOSED.value
        rating_info = f" (CSAT Rating: {satisfaction_rating}/5 stars)" if satisfaction_rating else ""
        add_history(db, c.id, f"Student confirmed resolution{rating_info} (Closed)", ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value, feedback_remarks or "Resolved", user.full_name)
        # Notify admin of satisfied resolution
        try:
            from app.services.notification_service import NotificationService
            from app.models.enums import UserRole
            campus_admin = db.query(User).filter(User.role == UserRole.ADMIN.value).first()
            if campus_admin:
                NotificationService.create_in_app_notification(
                    db,
                    recipient_user_id=campus_admin.id,
                    recipient_email=campus_admin.email,
                    recipient_name=campus_admin.full_name,
                    subject=f"Resolution Confirmed: Complaint #{c.complaint_number}",
                    body_preview=f"Student rated {satisfaction_rating or 5}/5 stars. Feedback: \"{(feedback_remarks or 'Issue resolved satisfactorily')[:120]}\"",
                    link=f"/admin/complaints/{c.id}",
                    notification_type="RESOLUTION_CONFIRMED",
                )
        except Exception as n_err:
            logger.warning("Could not dispatch confirmation notification: %s", n_err)
    else:
        c.status = ComplaintStatus.REOPENED.value
        fb.reopened_review_status = "PENDING_ADMIN_REVIEW"
        add_history(db, c.id, "Student reported issue NOT resolved (Reopened)", ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value, feedback_remarks or "Unresolved", user.full_name)
        from app.services.notification_service import NotificationService
        NotificationService.send_unresolved_feedback_notification(db, c, fb)

    db.commit()
    db.refresh(c)
    logger.info("Resolution feedback recorded for %s: is_resolved=%s", c.complaint_number, is_resolved)
    return fb


# ---------------- Module 5: Forwarding and Escalation ----------------
def forward_complaint(
    db: Session,
    complaint_id: int,
    admin_user: User,
    receiving_authority: str,
    forwarding_reason: str,
    admin_remarks: Optional[str] = None,
) -> ComplaintForwarding:
    """Escalate complaint while strictly preserving the original complaint ID and confidentiality."""
    c = get_complaint(db, complaint_id)
    sender_authority = f"{admin_user.campus or 'Campus'} Administration"
    category = c.analysis.category if c.analysis else "General"
    priority = c.analysis.priority if c.analysis else "MEDIUM"

    fwd = ComplaintForwarding(
        complaint_id=c.id,
        forwarded_by_id=admin_user.id,
        forwarded_by_name=admin_user.full_name,
        sender_authority=sender_authority,
        receiving_authority=receiving_authority,
        forwarding_reason=forwarding_reason,
        admin_remarks=admin_remarks,
        category=category,
        priority=priority,
        forwarded_at=utcnow(),
        response_status="PENDING",
    )
    db.add(fwd)

    # Status updated to IN_PROGRESS at higher authority
    c.status = ComplaintStatus.IN_PROGRESS.value
    add_history(
        db,
        c.id,
        f"Complaint forwarded to {receiving_authority}",
        sender_authority,
        receiving_authority,
        admin_user.full_name,
    )
    db.commit()
    db.refresh(fwd)
    logger.info("Complaint %s forwarded to %s", c.complaint_number, receiving_authority)

    # Feature 4: In-App notification dispatched to Higher Authority users
    try:
        from app.models.notification import Notification
        from app.models.enums import DeliveryStatus
        from app.models.user import UserRole
        auth_users = db.query(User).filter(User.role == UserRole.HIGHER_AUTHORITY.value).all()
        for au in auth_users:
            db.add(Notification(
                recipient_user_id=au.id,
                recipient_email=au.email,
                recipient_name=au.full_name or "Higher Authority",
                related_complaint_id=c.id,
                notification_type="FORWARDED_TO_AUTHORITY",
                subject=f"New Escalation: Complaint #{c.complaint_number}",
                body_preview=f"Forwarded by {admin_user.full_name} ({sender_authority}) to {receiving_authority}. Reason: {forwarding_reason[:120]}",
                link=f"/authority/complaints/{c.id}",
                delivery_status=DeliveryStatus.SENT.value,
                sent_at=utcnow(),
                created_at=utcnow(),
            ))
        db.commit()
    except Exception as exc:
        logger.warning("Could not dispatch authority forwarding notification: %s", exc)

    return fwd


DEPT_ROLE_MAP: dict[str, list[str]] = {
    "it department": ["it officer", "directorate of it officer", "it", "information technology"],
    "library department": ["librarian", "library officer", "library"],
    "accounts department": ["accounts officer", "treasurer / accounts officer", "accountant", "finance", "treasurer"],
    "examination department": ["controller of examinations", "examination officer", "examination", "exam"],
    "transport department": ["transport officer", "transport"],
    "hostel administration": ["hostel warden", "warden", "hostel"],
    "security / student affairs": ["security officer", "security", "safeguarding"],
    "directorate of student affairs": ["directorate of student affairs officer", "student affairs"],
    "student affairs": ["directorate of student affairs officer", "student affairs"],
    "student affairs / administration": ["directorate of student affairs officer", "student affairs", "administration"],
    "student affairs / designated safeguarding officer": ["directorate of student affairs officer", "safeguarding", "student affairs"],
    "administration office": ["registrar / administrative officer", "assistant registrar", "administrator", "admin", "principal / campus director", "director of division"],
    "administration / maintenance": ["assistant registrar", "maintenance", "administration"],
    "academic administration": ["registrar / administrative officer", "dean", "director of division", "academic"],
    "academic department": ["dean", "head of department (hod)", "director of division", "academic"],
    "quality enhancement cell (qec)": ["qec", "quality"],
    "office of research, innovation & commercialization (oric)": ["oric", "research"],
    "health & medical center": ["doctor", "physician", "medical", "health"],
    "admissions department": ["admissions", "admission"],
}


def user_matches_department(u: User, dept_name: str) -> bool:
    """Check if an employee, professor, or admin matches a department by department or designation."""
    if not dept_name:
        return False
    d_clean = dept_name.strip().lower()
    u_dept = (u.department or "").strip().lower()
    u_desig = (u.role_designation or "").strip().lower()
    u_role = (u.role or "").strip().lower()

    # 1. Exact or substring department match
    if u_dept and (u_dept == d_clean or d_clean in u_dept or u_dept in d_clean):
        return True

    # 2. Functional roles mapped to department keywords
    for dept_key, keywords in DEPT_ROLE_MAP.items():
        if dept_key in d_clean or d_clean in dept_key:
            if any(kw in u_desig or (u_dept and kw in u_dept) for kw in keywords):
                return True
            if dept_key == "administration office" and u_role == "admin":
                return True

    return False


def get_all_department_names(db: Optional[Session] = None) -> list[str]:
    """Retrieve complete, sorted list of official departments."""
    routing = get_routing_service()
    depts = set(routing.department_names)
    if db:
        try:
            records = db.scalars(select(DepartmentRecord.name)).all()
            for r in records:
                if r and r.strip():
                    depts.add(r.strip())
        except Exception as exc:
            logger.debug("Could not query departments table: %s", exc)
    return sorted(list(depts))


def get_department_handlers(db: Session, department_name: str, campus: Optional[str] = None) -> list[User]:
    """Retrieve authorized employees, professors, and staff eligible to handle complaints in a department."""
    if not department_name or not department_name.strip():
        return []

    stmt = (
        select(User)
        .where(
            User.is_active.is_(True),
            User.role.in_(["EMPLOYEE", "PROFESSOR", "ADMIN"]),
        )
        .order_by(User.full_name.asc())
    )
    all_staff = list(db.scalars(stmt).all())

    # Campus matching: match same campus or staff with campus=None
    if campus and campus.lower() not in ("all", "all campuses"):
        campus_clean = campus.strip().lower()
        campus_staff = [u for u in all_staff if not u.campus or u.campus.strip().lower() == campus_clean]
    else:
        campus_staff = all_staff

    matched = [u for u in campus_staff if user_matches_department(u, department_name)]

    # Fallback to matching staff across campuses if none registered at this campus
    if not matched and campus_staff != all_staff:
        matched = [u for u in all_staff if user_matches_department(u, department_name)]

    return matched


def get_all_department_handlers_map(db: Session, campus: Optional[str] = None) -> dict[str, list[dict]]:
    """Return a mapping of department names to list of handler dicts."""
    depts = get_all_department_names(db)
    
    stmt = (
        select(User)
        .where(
            User.is_active.is_(True),
            User.role.in_(["EMPLOYEE", "PROFESSOR", "ADMIN"]),
        )
        .order_by(User.full_name.asc())
    )
    all_staff = list(db.scalars(stmt).all())

    result: dict[str, list[dict]] = {}
    for d in depts:
        handlers = get_department_handlers(db, d, campus)
        result[d] = [
            {
                "id": u.id,
                "name": u.full_name,
                "role": u.role_designation or u.role,
                "campus": u.campus or "All Campuses",
                "department": u.department or "",
            }
            for u in handlers
        ]

    result["__all__"] = [
        {
            "id": u.id,
            "name": u.full_name,
            "role": u.role_designation or u.role,
            "campus": u.campus or "All Campuses",
            "department": u.department or "",
        }
        for u in all_staff
    ]
    return result


def get_escalation_authorities() -> list[dict[str, Any]]:
    """Load authorized higher authorities from config."""
    from app.core.config import load_json_config
    data = load_json_config("escalation_authorities")
    if isinstance(data, dict):
        return data.get("authorities", [])
    return []


def get_authority_forwarded_complaints(
    db: Session,
    authority_name: Optional[str] = None,
    campus: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    q: Optional[str] = None,
) -> list[Complaint]:
    """Retrieve complaints forwarded to a designated higher authority with multi-campus filtering."""
    stmt = (
        select(Complaint)
        .join(ComplaintForwarding, Complaint.id == ComplaintForwarding.complaint_id)
        .where(Complaint.is_deleted.is_(False))
    )

    if authority_name and authority_name.strip() and authority_name.strip().lower() != "all":
        auth_clean = authority_name.strip().lower()
        keywords = [k for k in auth_clean.replace("office", "").replace("secretariat", "").replace("directorate", "").split() if len(k) > 2]
        auth_conds = [
            ComplaintForwarding.receiving_authority.ilike(f"%{auth_clean}%"),
            ComplaintForwarding.receiving_authority.ilike(f"{auth_clean}"),
        ]
        for kw in keywords:
            auth_conds.append(ComplaintForwarding.receiving_authority.ilike(f"%{kw}%"))
        stmt = stmt.where(or_(*auth_conds))

    if campus and campus.strip() and campus.strip().lower() not in ("all", "all campuses"):
        cmp_clean = campus.strip()
        cmp_prefix = cmp_clean.split(",")[0].strip()
        stmt = stmt.where(
            or_(
                Complaint.originating_campus.ilike(f"%{cmp_prefix}%"),
                Complaint.target_campus.ilike(f"%{cmp_prefix}%"),
                ComplaintForwarding.sender_authority.ilike(f"%{cmp_prefix}%"),
            )
        )

    if status and status.strip() and status.strip().lower() not in ("all", "any"):
        st_clean = status.strip().upper()
        if st_clean == "PENDING":
            stmt = stmt.where(
                or_(
                    Complaint.status.in_([ComplaintStatus.NEW.value, ComplaintStatus.PENDING.value]),
                    ComplaintForwarding.response_status == "PENDING",
                )
            )
        elif st_clean == "RESOLVED":
            stmt = stmt.where(
                or_(
                    Complaint.status.in_([ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value, ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value]),
                    ComplaintForwarding.response_status == "RESOLVED",
                )
            )
        elif st_clean == "IN_PROGRESS":
            stmt = stmt.where(
                or_(
                    Complaint.status.in_([ComplaintStatus.IN_PROGRESS.value, ComplaintStatus.ASSIGNED.value, ComplaintStatus.UNDER_REVIEW.value]),
                    ComplaintForwarding.response_status == "IN_PROGRESS",
                )
            )
        elif st_clean == "FORWARDED":
            stmt = stmt.where(ComplaintForwarding.id.is_not(None))
        else:
            stmt = stmt.where(Complaint.status.ilike(st_clean))

    if priority and priority.strip() and priority.strip().lower() not in ("all", "any"):
        p_clean = priority.strip().upper()
        stmt = stmt.where(
            or_(
                ComplaintForwarding.priority.ilike(p_clean),
                Complaint.analysis.has(ComplaintAnalysis.priority == p_clean),
            )
        )

    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Complaint.complaint_number.ilike(term),
                Complaint.student_name.ilike(term),
                Complaint.title.ilike(term),
                Complaint.complaint_text.ilike(term),
                ComplaintForwarding.forwarding_reason.ilike(term),
            )
        )

    stmt = stmt.options(selectinload(Complaint.forwardings), selectinload(Complaint.analysis))
    stmt = stmt.order_by(Complaint.id.desc()).distinct()
    complaints = list(db.scalars(stmt).all())

    from app.utils.time import utcnow
    def _latest_fwd_date(comp: Complaint):
        dates = [f.forwarded_at for f in comp.forwardings if f.forwarded_at]
        return max(dates) if dates else (comp.created_at or utcnow())

    complaints.sort(key=_latest_fwd_date, reverse=True)
    return complaints


def get_authority_campus_breakdown(
    db: Session,
    authority_name: Optional[str] = None,
) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]], dict[str, int]]:
    """Generate campus-wise complaint metrics and identify top forwarding campus."""
    all_complaints = get_authority_forwarded_complaints(db, authority_name=authority_name)
    campuses = get_campus_names()

    campus_stats: list[dict[str, Any]] = []
    overall_counts = {"total": 0, "pending": 0, "in_progress": 0, "resolved": 0, "forwarded": 0}

    for camp in campuses:
        camp_short = camp.split(",")[0].strip()
        matched = [
            c for c in all_complaints
            if (c.originating_campus and camp_short.lower() in c.originating_campus.lower())
            or (c.target_campus and camp_short.lower() in c.target_campus.lower())
            or any(f.sender_authority and camp_short.lower() in f.sender_authority.lower() for f in c.forwardings)
        ]
        
        c_total = len(matched)
        c_pending = sum(1 for c in matched if c.status in ("NEW", "PENDING") or any(f.response_status == "PENDING" for f in c.forwardings))
        c_resolved = sum(1 for c in matched if c.status in ("RESOLVED", "CLOSED", "RESOLVED_AWAITING_CONFIRMATION"))
        c_in_progress = sum(1 for c in matched if c.status in ("IN_PROGRESS", "ASSIGNED", "UNDER_REVIEW"))
        c_forwarded = sum(1 for c in matched if len(c.forwardings) > 1)

        campus_stats.append({
            "campus": camp,
            "campus_short": camp_short,
            "total": c_total,
            "pending": c_pending,
            "in_progress": c_in_progress,
            "resolved": c_resolved,
            "forwarded": c_forwarded,
        })

    overall_counts["total"] = len(all_complaints)
    overall_counts["pending"] = sum(1 for c in all_complaints if c.status in ("NEW", "PENDING") or any(f.response_status == "PENDING" for f in c.forwardings))
    overall_counts["resolved"] = sum(1 for c in all_complaints if c.status in ("RESOLVED", "CLOSED", "RESOLVED_AWAITING_CONFIRMATION"))
    overall_counts["in_progress"] = sum(1 for c in all_complaints if c.status in ("IN_PROGRESS", "ASSIGNED", "UNDER_REVIEW"))
    overall_counts["forwarded"] = sum(1 for c in all_complaints if len(c.forwardings) > 1)

    sorted_campuses = sorted(campus_stats, key=lambda x: x["total"], reverse=True)
    top_campus = sorted_campuses[0] if (sorted_campuses and sorted_campuses[0]["total"] > 0) else None

    return campus_stats, top_campus, overall_counts


def update_authority_complaint(
    db: Session,
    complaint_id: int,
    authority_user: User,
    new_status: str,
    remarks: Optional[str] = None,
) -> Complaint:
    """Update complaint status and record authority remarks reflected in student and admin tracking."""
    c = get_complaint(db, complaint_id)
    c.status = new_status
    authority_title = authority_user.authority_name or authority_user.role_designation or "Higher Authority"

    if c.forwardings:
        matching_fwd = None
        for f in reversed(c.forwardings):
            if not matching_fwd:
                matching_fwd = f
            if authority_user.authority_name and authority_user.authority_name.lower() in f.receiving_authority.lower():
                matching_fwd = f
                break
        if matching_fwd:
            matching_fwd.response_status = new_status
            if remarks:
                matching_fwd.response_remarks = remarks.strip()
            matching_fwd.responded_at = utcnow()

    if remarks:
        existing_notes = c.internal_notes or ""
        note_entry = f"[{utcnow().strftime('%Y-%m-%d %H:%M')}] {authority_title} ({authority_user.full_name}): {remarks.strip()}"
        c.internal_notes = f"{existing_notes}\n{note_entry}".strip()

    action_text = f"Status updated to {new_status} by {authority_title}"
    if new_status == ComplaintStatus.RESOLVED.value:
        action_text = f"Complaint resolved by {authority_title}"

    add_history(
        db,
        c.id,
        action_text,
        authority_title,
        authority_title,
        authority_user.full_name,
    )
    db.commit()
    db.refresh(c)
    logger.info("Complaint %s updated to %s by %s", c.complaint_number, new_status, authority_title)
    return c


def forward_authority_complaint_to_another(
    db: Session,
    complaint_id: int,
    from_authority_user: User,
    receiving_authority: str,
    forwarding_reason: str,
    admin_remarks: Optional[str] = None,
) -> ComplaintForwarding:
    """Higher authority escalates or redirects a complaint to another university authority."""
    c = get_complaint(db, complaint_id)
    sender_title = from_authority_user.authority_name or from_authority_user.role_designation or "Higher Authority"
    category = c.analysis.category if c.analysis else "General"
    priority = c.analysis.priority if c.analysis else "MEDIUM"

    fwd = ComplaintForwarding(
        complaint_id=c.id,
        forwarded_by_id=from_authority_user.id,
        forwarded_by_name=from_authority_user.full_name,
        sender_authority=sender_title,
        receiving_authority=receiving_authority,
        forwarding_reason=forwarding_reason,
        admin_remarks=admin_remarks,
        category=category,
        priority=priority,
        forwarded_at=utcnow(),
        response_status="PENDING",
    )
    db.add(fwd)
    c.status = ComplaintStatus.IN_PROGRESS.value

    add_history(
        db,
        c.id,
        f"Complaint re-escalated from {sender_title} to {receiving_authority}",
        sender_title,
        receiving_authority,
        from_authority_user.full_name,
    )
    db.commit()
    db.refresh(fwd)
    logger.info("Complaint %s re-escalated from %s to %s", c.complaint_number, sender_title, receiving_authority)
    return fwd


def compute_sla_info(c: Complaint, a: Optional[ComplaintAnalysis] = None) -> dict:
    """Calculate SLA deadlines, breach status, and remaining hours based on priority."""
    now = utcnow()
    priority = (a and a.priority) or "MEDIUM"
    sla_map = {"CRITICAL": 12, "HIGH": 24, "MEDIUM": 48, "LOW": 72}
    total_hours = sla_map.get(priority, 48)

    created = c.created_at or now
    elapsed_hours = max(0.0, (now - created).total_seconds() / 3600.0)
    remaining_hours = total_hours - elapsed_hours

    is_resolved = c.status in (ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value)
    is_breached = remaining_hours < 0 and not is_resolved

    badge_text = "SLA Met" if is_resolved else (f"Breached by {int(abs(remaining_hours))}h" if is_breached else f"{int(remaining_hours)}h left")
    badge_class = "bg-success" if is_resolved else ("bg-danger" if is_breached else ("bg-warning text-dark" if remaining_hours <= 12 else "bg-primary-subtle text-primary border"))

    return {
        "priority": priority,
        "total_hours": total_hours,
        "elapsed_hours": round(elapsed_hours, 1),
        "remaining_hours": round(remaining_hours, 1),
        "is_breached": is_breached,
        "is_resolved": is_resolved,
        "badge_class": badge_class,
        "badge_text": badge_text,
    }


def export_complaints_csv(complaints: list[Complaint]) -> str:
    """Format complaints as an RFC 4180 CSV spreadsheet string."""
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "Complaint ID",
        "Title",
        "Student Name",
        "Student ID",
        "Confidential",
        "Campus",
        "Category",
        "Priority",
        "Status",
        "Assigned Department",
        "SLA Status",
        "Created At",
        "Updated At",
    ])
    for c in complaints:
        sla = compute_sla_info(c, c.analysis)
        cat = c.analysis.category if c.analysis else "General"
        prio = c.analysis.priority if c.analysis else "MEDIUM"
        dept = c.analysis.assigned_department if c.analysis else "Unassigned"
        s_name = "[Confidential]" if c.is_confidential else c.student_name
        s_code = "[Hidden]" if c.is_confidential else (c.student_id_code or "")
        writer.writerow([
            c.complaint_number,
            c.title,
            s_name,
            s_code,
            "Yes" if c.is_confidential else "No",
            c.originating_campus or c.target_campus or "",
            cat,
            prio,
            c.status,
            dept,
            sla["badge_text"],
            c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "",
            c.updated_at.strftime("%Y-%m-%d %H:%M") if c.updated_at else "",
        ])
    return output.getvalue()


def add_complaint_clarification(
    db: Session,
    complaint_id: int,
    sender_user: User,
    message: str,
) -> ComplaintClarification:
    """Send two-way message between student and staff. Strictly blocks confidential complaints."""
    c = get_complaint(db, complaint_id)
    if c.is_confidential and sender_user.role == UserRole.STUDENT.value:
        raise ValueError("Two-way communication is disabled for confidential complaints to protect student identity.")

    if not message or not message.strip():
        raise ValueError("Message cannot be empty.")

    sender_title = sender_user.role_designation or sender_user.role
    if sender_user.role == UserRole.HIGHER_AUTHORITY.value:
        sender_title = sender_user.authority_name or "Higher Authority"

    clarif = ComplaintClarification(
        complaint_id=c.id,
        sender_id=sender_user.id,
        sender_name=sender_user.full_name,
        sender_role=sender_title,
        message=message.strip(),
        created_at=utcnow(),
    )
    db.add(clarif)

    # Log to status history
    add_history(
        db,
        c.id,
        f"Clarification message from {sender_title} ({sender_user.full_name})",
        None,
        None,
        sender_user.full_name,
    )
    db.commit()
    db.refresh(clarif)

    # Dispatch in-app notifications
    try:
        from app.services.notification_service import NotificationService
        if sender_user.role == UserRole.STUDENT.value:
            admin_u = db.query(User).filter(User.role == UserRole.ADMIN.value).first()
            if admin_u:
                NotificationService.create_in_app_notification(
                    db,
                    recipient_user_id=admin_u.id,
                    recipient_email=admin_u.email,
                    recipient_name=admin_u.full_name,
                    subject=f"Clarification from Student: Complaint #{c.complaint_number}",
                    body_preview=f"{sender_user.full_name}: {message[:120]}",
                    link=f"/admin/complaints/{c.id}",
                    notification_type="CLARIFICATION",
                )
        elif sender_user.role == UserRole.EMPLOYEE.value:
            admin_u = db.query(User).filter(User.role == UserRole.ADMIN.value).first()
            if admin_u:
                NotificationService.create_in_app_notification(
                    db,
                    recipient_user_id=admin_u.id,
                    recipient_email=admin_u.email,
                    recipient_name=admin_u.full_name,
                    subject=f"Staff Collaboration Note: Complaint #{c.complaint_number}",
                    body_preview=f"{sender_user.full_name} ({sender_title}): {message[:120]}",
                    link=f"/admin/complaints/{c.id}",
                    notification_type="CLARIFICATION",
                )
        elif sender_user.role == UserRole.HIGHER_AUTHORITY.value:
            admin_u = db.query(User).filter(User.role == UserRole.ADMIN.value).first()
            if admin_u:
                NotificationService.create_in_app_notification(
                    db,
                    recipient_user_id=admin_u.id,
                    recipient_email=admin_u.email,
                    recipient_name=admin_u.full_name,
                    subject=f"Authority Direct Note: Complaint #{c.complaint_number}",
                    body_preview=f"{sender_title}: {message[:120]}",
                    link=f"/admin/complaints/{c.id}",
                    notification_type="CLARIFICATION",
                )
        elif sender_user.role == UserRole.ADMIN.value:
            if not c.is_confidential:
                stu = None
                if c.user_id:
                    stu = db.get(User, c.user_id)
                if not stu and c.email:
                    stu = db.query(User).filter(User.email == c.email).first()
                if stu:
                    NotificationService.create_in_app_notification(
                        db,
                        recipient_user_id=stu.id,
                        recipient_email=stu.email,
                        recipient_name=stu.full_name,
                        subject=f"Message from Admin: Complaint #{c.complaint_number}",
                        body_preview=f"Administration: {message[:120]}",
                        link=f"/student/complaints/{c.id}",
                        notification_type="CLARIFICATION",
                    )
    except Exception as notif_exc:
        logger.warning("Could not dispatch clarification notification: %s", notif_exc)

    return clarif


def submit_complaint_feedback(
    db: Session,
    complaint_id: int,
    student_user: User,
    rating: int,
    remarks: Optional[str] = None,
) -> ComplaintFeedback:
    """Submit post-resolution student satisfaction rating (CSAT: 1-5 stars) and close case."""
    c = get_complaint(db, complaint_id)

    fb = db.query(ComplaintFeedback).filter(ComplaintFeedback.complaint_id == c.id).first()
    if not fb:
        fb = ComplaintFeedback(
            complaint_id=c.id,
            student_id=student_user.id,
            is_resolved=True,
            satisfaction_rating=rating,
            feedback_remarks=remarks.strip() if remarks else None,
            confirmed_at=utcnow(),
        )
        db.add(fb)
    else:
        fb.satisfaction_rating = rating
        fb.feedback_remarks = remarks.strip() if remarks else None
        fb.confirmed_at = utcnow()

    c.status = ComplaintStatus.CLOSED.value
    add_history(
        db,
        c.id,
        f"Student submitted satisfaction rating: {rating}/5 stars - Resolution confirmed and closed.",
        c.status,
        ComplaintStatus.CLOSED.value,
        student_user.full_name,
    )
    db.commit()
    db.refresh(fb)
    return fb


def get_department_csat_summary(db: Session) -> dict:
    """Compute overall CSAT rating and breakdown across complaints."""
    fbs = db.query(ComplaintFeedback).filter(ComplaintFeedback.satisfaction_rating.isnot(None)).all()
    if not fbs:
        return {"average": 5.0, "total_reviews": 0, "distribution": {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}}
    ratings = [f.satisfaction_rating for f in fbs if f.satisfaction_rating]
    avg = round(sum(ratings) / len(ratings), 1) if ratings else 5.0
    dist = {i: ratings.count(i) for i in range(1, 6)}
    return {"average": avg, "total_reviews": len(ratings), "distribution": dist}

