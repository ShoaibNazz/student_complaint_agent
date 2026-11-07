"""Employee and staff administrative requests use-cases.
Completely separate workflow from student complaints with stage-based approvals.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR
from app.core.exceptions import ComplaintValidationError
from app.models.enums import RequestCategory, RequestStatus
from app.models.request import EmployeeRequest, RequestApproval
from app.models.user import User
from app.utils.time import utcnow

logger = logging.getLogger("complaint_agent.requests")

MAX_ATTACHMENT_BYTES = 500 * 1024  # 500 KB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".webp"}


class RequestCreatePayload(BaseModel):
    category: str
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    attachment_path: Optional[str] = None
    attachment_name: Optional[str] = None


def save_request_attachment(upload_file) -> tuple[Optional[str], Optional[str]]:
    """Save supporting document for administrative application."""
    if upload_file is None:
        return None, None
    raw_name = (getattr(upload_file, "filename", None) or "").strip()
    if not raw_name:
        return None, None

    file_obj = getattr(upload_file, "file", None)
    content = file_obj.read() if file_obj else b""
    if not content:
        return None, None

    ext = Path(raw_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ComplaintValidationError(["Allowed attachment formats for applications: PNG, JPG, JPEG, WEBP, PDF."])
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise ComplaintValidationError(["Attachment file exceeds maximum limit of 500 KB."])

    dest_dir = Path(BASE_DIR) / "app" / "static" / "uploads" / "requests"
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"req_{uuid.uuid4().hex[:16]}{ext}"
    (dest_dir / safe_name).write_bytes(content)
    return f"/static/uploads/requests/{safe_name}", Path(raw_name).name[:200]


def create_employee_request(
    db: Session,
    user: User,
    payload: RequestCreatePayload,
) -> EmployeeRequest:
    """Create a staff administrative request with automatic employee identification."""
    req = EmployeeRequest(
        request_number=f"TMP-{uuid.uuid4().hex}",
        user_id=user.id,
        employee_name=user.full_name,
        employee_id=user.employee_id or user.professor_id or f"EMP-{user.id}",
        department=user.department or "General Administration",
        campus=user.campus or "Main Campus",
        category=payload.category,
        title=payload.title,
        description=payload.description,
        attachment_path=payload.attachment_path,
        attachment_name=payload.attachment_name,
        status=RequestStatus.SUBMITTED.value,
        current_stage="Reviewing Officer",
    )
    db.add(req)
    db.flush()

    req.request_number = f"REQ-{utcnow().year}-{req.id:06d}"
    approval = RequestApproval(
        request_id=req.id,
        stage="Submission",
        action="SUBMITTED",
        actor_id=user.id,
        actor_name=user.full_name,
        remarks="Application submitted through Employee Portal.",
        action_at=utcnow(),
    )
    db.add(approval)
    db.commit()
    db.refresh(req)
    logger.info("Staff request created %s by %s", req.request_number, user.full_name)
    return req


def get_employee_requests(db: Session, user: User) -> list[EmployeeRequest]:
    """Retrieve all requests submitted by the logged-in employee."""
    stmt = (
        select(EmployeeRequest)
        .where(EmployeeRequest.user_id == user.id)
        .order_by(EmployeeRequest.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_employee_request(db: Session, request_id: int, user: User) -> EmployeeRequest:
    """Fetch request enforcing ownership / authorization."""
    req = db.get(EmployeeRequest, request_id)
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application request not found.")
    
    # Allowed if owner or campus admin
    is_owner = req.user_id == user.id
    is_admin = user.role == "ADMIN" and (not user.campus or req.campus == user.campus)
    if not (is_owner or is_admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden: Access denied to this application.")
    return req


def get_campus_requests_for_admin(db: Session, admin_user: User, status_filter: Optional[str] = None) -> list[EmployeeRequest]:
    """Retrieve requests for campus administrator review."""
    conds = []
    if admin_user.campus:
        conds.append(EmployeeRequest.campus == admin_user.campus)
    if status_filter:
        conds.append(EmployeeRequest.status == status_filter)
    
    stmt = (
        select(EmployeeRequest)
        .where(*conds)
        .order_by(EmployeeRequest.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def update_request_status(
    db: Session,
    req: EmployeeRequest,
    actor: User,
    action: str,  # "REVIEWED", "APPROVED", "REJECTED"
    remarks: str,
    next_stage: Optional[str] = None,
) -> EmployeeRequest:
    """Update approval stage and decision on staff application."""
    if action == "APPROVED":
        req.status = RequestStatus.APPROVED.value
        req.current_stage = "Completed"
        req.approving_authority_id = actor.id
        req.approving_authority_name = actor.full_name
        req.decided_at = utcnow()
    elif action == "REJECTED":
        req.status = RequestStatus.REJECTED.value
        req.current_stage = "Completed"
        req.approving_authority_id = actor.id
        req.approving_authority_name = actor.full_name
        req.decided_at = utcnow()
    elif action == "UNDER_REVIEW":
        req.status = RequestStatus.UNDER_REVIEW.value
        if next_stage:
            req.current_stage = next_stage
        req.reviewing_officer_id = actor.id
        req.reviewing_officer_name = actor.full_name

    req.decision_remarks = remarks
    approval = RequestApproval(
        request_id=req.id,
        stage=req.current_stage,
        action=action,
        actor_id=actor.id,
        actor_name=actor.full_name,
        remarks=remarks,
        action_at=utcnow(),
    )
    db.add(approval)
    db.commit()
    db.refresh(req)
    return req
