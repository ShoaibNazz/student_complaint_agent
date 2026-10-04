from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_employee
from app.database.database import get_db
from app.models.user import User
from app.schemas.complaint import ComplaintDetailOut, ComplaintOut
from app.services import complaint_service as svc

router = APIRouter(prefix="/api/employee", tags=["employee"])


@router.get("/dashboard")
def employee_dashboard(db: Session = Depends(get_db), employee: User = Depends(require_employee)):
    stats = svc.get_employee_stats(db, employee)
    recent = svc.get_employee_complaints(db, employee)[:5]
    return {
        "employee": {
            "name": employee.full_name,
            "employee_id": employee.employee_id,
            "department": employee.department,
            "email": employee.email,
        },
        "stats": stats,
        "recent_complaints": [ComplaintOut.model_validate(c).model_dump() for c in recent],
    }


@router.get("/complaints", response_model=list[ComplaintOut])
def list_employee_complaints(db: Session = Depends(get_db), employee: User = Depends(require_employee)):
    items = svc.get_employee_complaints(db, employee)
    return [ComplaintOut.model_validate(c) for c in items]


@router.get("/complaints/{complaint_id}", response_model=ComplaintDetailOut)
def get_employee_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    employee: User = Depends(require_employee),
):
    c = svc.get_complaint(db, complaint_id)
    return ComplaintDetailOut.model_validate(c)
