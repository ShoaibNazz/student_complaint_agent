from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database.database import get_db
from app.models.enums import Priority
from app.models.user import User
from app.schemas.complaint import (AssignmentUpdate, ComplaintDetailOut, ComplaintListOut, ComplaintOut,
                                   ComplaintUpdate, DashboardStats, ResponseUpdate, StatusUpdate)
from app.services import complaint_service as svc

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/dashboard", response_model=DashboardStats)
def admin_dashboard_stats(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return svc.get_dashboard_stats(db)


@router.get("/complaints", response_model=ComplaintListOut)
def list_admin_complaints(
    q: Optional[str] = Query(None, max_length=200),
    priority: Optional[Priority] = None,
    category: Optional[str] = None,
    department: Optional[str] = None,
    status_: Optional[str] = Query(None, alias="status"),
    requires_human_review: Optional[bool] = None,
    analysis_status: Optional[str] = None,
    sort: Literal["newest", "oldest", "priority"] = "newest",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    filters = svc.ComplaintFilters(
        q=q, priority=priority, category=category, department=department,
        status=status_, requires_human_review=requires_human_review,
        analysis_status=analysis_status, sort=sort, skip=skip, limit=limit,
    )
    items, total = svc.list_complaints(db, filters)
    return ComplaintListOut(total=total, skip=skip, limit=limit, items=items)


@router.get("/complaints/{complaint_id}", response_model=ComplaintDetailOut)
def get_admin_complaint(complaint_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return svc.get_complaint(db, complaint_id)


@router.put("/complaints/{complaint_id}", response_model=ComplaintOut)
def update_admin_complaint(
    complaint_id: int,
    data: ComplaintUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return svc.update_complaint(db, svc.get_complaint(db, complaint_id), data, admin.username)


@router.put("/complaints/{complaint_id}/status", response_model=ComplaintOut)
def set_admin_status(
    complaint_id: int,
    data: StatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return svc.update_status(db, svc.get_complaint(db, complaint_id), data, admin.username)


@router.put("/complaints/{complaint_id}/assignment", response_model=ComplaintOut)
def set_admin_assignment(
    complaint_id: int,
    data: AssignmentUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return svc.update_assignment(db, svc.get_complaint(db, complaint_id), data, admin.username)


@router.put("/complaints/{complaint_id}/response", response_model=ComplaintOut)
def set_admin_response(
    complaint_id: int,
    data: ResponseUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return svc.update_response(db, svc.get_complaint(db, complaint_id), data, admin.username)
