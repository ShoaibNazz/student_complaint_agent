from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import require_student
from app.database.database import get_db
from app.models.user import User
from app.schemas.complaint import (ComplaintCreate, ComplaintReceipt, StudentComplaintDetailOut,
                                   StudentComplaintOut, StudentComplaintSubmit, StudentDashboardStats)
from app.services import complaint_service as svc

router = APIRouter(prefix="/api/student", tags=["student"])


def _to_student_detail(c) -> StudentComplaintDetailOut:
    a = c.analysis
    return StudentComplaintDetailOut(
        id=c.id,
        complaint_number=c.complaint_number,
        student_name=c.student_name,
        student_id=c.student_id,
        email=c.email,
        class_or_program=c.class_or_program,
        subject=c.subject,
        title=c.title,
        complaint_text=c.complaint_text,
        status=c.status,
        created_at=c.created_at,
        updated_at=c.updated_at,
        category=a.category if a else None,
        subcategory=a.subcategory if a else None,
        priority=a.priority if a else None,
        assigned_department=a.assigned_department if a else None,
        summary=a.summary if a else None,
        official_response=a.draft_response if (a and a.response_approved) else None,
        timeline=svc.build_student_timeline(c),
    )


def _to_student_out(c) -> StudentComplaintOut:
    a = c.analysis
    return StudentComplaintOut(
        id=c.id,
        complaint_number=c.complaint_number,
        title=c.title,
        status=c.status,
        priority=a.priority if a else None,
        category=a.category if a else None,
        assigned_department=a.assigned_department if a else None,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/dashboard", response_model=dict)
def student_dashboard(db: Session = Depends(get_db), student: User = Depends(require_student)):
    stats = svc.get_student_stats(db, student)
    recent = svc.get_student_complaints(db, student)[:5]
    return {
        "student": {
            "name": student.full_name,
            "student_id": student.student_id,
            "program": student.program,
            "email": student.email,
        },
        "stats": stats.model_dump(),
        "recent_complaints": [_to_student_out(c).model_dump() for c in recent],
    }


@router.post("/complaints", response_model=ComplaintReceipt, status_code=status.HTTP_201_CREATED)
def submit_complaint(
    payload: StudentComplaintSubmit,
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
):
    # Automatically attach student's identity - cannot spoof
    create_payload = ComplaintCreate(
        student_name=student.full_name,
        student_id=student.student_id,
        email=student.email,
        class_or_program=student.program,
        subject=payload.subject,
        complaint_title=payload.complaint_title,
        complaint_text=payload.complaint_text,
    )
    c = svc.create_complaint(db, create_payload, user_id=student.id)
    return ComplaintReceipt(
        id=c.id,
        complaint_number=c.complaint_number,
        status=c.status,
        message="Your complaint has been successfully submitted.",
    )


@router.get("/complaints", response_model=list[StudentComplaintOut])
def list_student_complaints(
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
):
    items = svc.get_student_complaints(db, student)
    return [_to_student_out(c) for c in items]


@router.get("/complaints/{complaint_id}", response_model=StudentComplaintDetailOut)
def get_student_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
):
    c = svc.get_student_complaint(db, complaint_id, student)
    return _to_student_detail(c)
