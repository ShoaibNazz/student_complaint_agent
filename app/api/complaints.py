"""REST API for complaints. Submission is public; everything else needs admin auth."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.security import AdminUser, get_current_admin
from app.database.database import get_db
from app.models.enums import Priority
from app.schemas.complaint import (AssignmentUpdate, ComplaintCreate, ComplaintDetailOut, ComplaintListOut,
                                   ComplaintOut, ComplaintReceipt, ComplaintUpdate, ResponseUpdate, StatusUpdate)
from app.services import complaint_service as svc

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


@router.post("", response_model=ComplaintReceipt, status_code=status.HTTP_201_CREATED,
             summary="Submit a complaint (public)")
def submit_complaint(payload: ComplaintCreate, db: Session = Depends(get_db)):
    c = svc.create_complaint(db, payload)
    return ComplaintReceipt(id=c.id, complaint_number=c.complaint_number, status=c.status)


@router.get("", response_model=ComplaintListOut, summary="List/filter/search complaints")
def list_complaints(
    q: Optional[str] = Query(None, max_length=200, description="Text search"),
    priority: Optional[Priority] = None,
    category: Optional[str] = None,
    department: Optional[str] = None,
    status_: Optional[str] = Query(None, alias="status", description="A status, or OPEN for all unfinished"),
    requires_human_review: Optional[bool] = None,
    analysis_status: Optional[str] = None,
    sort: Literal["newest", "oldest", "priority"] = "newest",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db), _: AdminUser = Depends(get_current_admin),
):
    filters = svc.ComplaintFilters(q=q, priority=priority, category=category, department=department,
                                   status=status_, requires_human_review=requires_human_review,
                                   analysis_status=analysis_status, sort=sort, skip=skip, limit=limit)
    items, total = svc.list_complaints(db, filters)
    return ComplaintListOut(total=total, skip=skip, limit=limit, items=items)


@router.get("/{complaint_id}", response_model=ComplaintDetailOut)
def get_complaint(complaint_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(get_current_admin)):
    return svc.get_complaint(db, complaint_id)


@router.put("/{complaint_id}", response_model=ComplaintOut, summary="Update contact details / internal notes")
def update_complaint(complaint_id: int, data: ComplaintUpdate, db: Session = Depends(get_db),
                     admin: AdminUser = Depends(get_current_admin)):
    return svc.update_complaint(db, svc.get_complaint(db, complaint_id), data, admin.username)


@router.delete("/{complaint_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Soft-delete (audit trail kept)")
def delete_complaint(complaint_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    svc.soft_delete(db, svc.get_complaint(db, complaint_id), admin.username)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{complaint_id}/analyze", response_model=ComplaintOut, summary="(Re)run AI analysis")
def analyze_complaint(complaint_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return svc.reanalyze(db, svc.get_complaint(db, complaint_id), admin.username)


@router.put("/{complaint_id}/status", response_model=ComplaintOut)
def set_status(complaint_id: int, data: StatusUpdate, db: Session = Depends(get_db),
               admin: AdminUser = Depends(get_current_admin)):
    return svc.update_status(db, svc.get_complaint(db, complaint_id), data, admin.username)


@router.put("/{complaint_id}/assignment", response_model=ComplaintOut,
            summary="Change category, subcategory, department or priority")
def set_assignment(complaint_id: int, data: AssignmentUpdate, db: Session = Depends(get_db),
                   admin: AdminUser = Depends(get_current_admin)):
    return svc.update_assignment(db, svc.get_complaint(db, complaint_id), data, admin.username)


@router.put("/{complaint_id}/response", response_model=ComplaintOut, summary="Edit/approve the draft response")
def set_response(complaint_id: int, data: ResponseUpdate, db: Session = Depends(get_db),
                 admin: AdminUser = Depends(get_current_admin)):
    return svc.update_response(db, svc.get_complaint(db, complaint_id), data, admin.username)
