from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_professor
from app.database.database import get_db
from app.models.user import User
from app.schemas.complaint import ComplaintDetailOut, ComplaintOut
from app.services import complaint_service as svc

router = APIRouter(prefix="/api/professor", tags=["professor"])


@router.get("/dashboard")
def professor_dashboard(db: Session = Depends(get_db), professor: User = Depends(require_professor)):
    stats = svc.get_professor_stats(db, professor)
    recent = svc.get_professor_complaints(db, professor)[:5]
    return {
        "professor": {
            "name": professor.full_name,
            "professor_id": professor.professor_id,
            "department": professor.department,
            "email": professor.email,
        },
        "stats": stats,
        "recent_complaints": [ComplaintOut.model_validate(c).model_dump() for c in recent],
    }


@router.get("/complaints", response_model=list[ComplaintOut])
def list_professor_complaints(db: Session = Depends(get_db), professor: User = Depends(require_professor)):
    items = svc.get_professor_complaints(db, professor)
    return [ComplaintOut.model_validate(c) for c in items]


@router.get("/complaints/{complaint_id}", response_model=ComplaintDetailOut)
def get_professor_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    professor: User = Depends(require_professor),
):
    c = svc.get_complaint(db, complaint_id)
    return ComplaintDetailOut.model_validate(c)
