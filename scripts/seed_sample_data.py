"""Load sample_data/sample_complaints.json through the normal service pipeline.

Usage (from project root):  python -m scripts.seed_sample_data
"""
import json
from pathlib import Path

from app.core.config import BASE_DIR, setup_logging
from app.database.database import SessionLocal, init_db
from app.models.user import User
from app.schemas.complaint import ComplaintCreate
from app.services import complaint_service


def main() -> None:
    setup_logging("WARNING")
    init_db()
    data = json.loads(Path(BASE_DIR / "sample_data" / "sample_complaints.json").read_text(encoding="utf-8"))
    with SessionLocal() as db:
        for item in data:
            stu_id = item.get("student_id")
            user = db.query(User).filter(User.student_id == stu_id).first() if stu_id else None
            user_id = user.id if user else None
            c = complaint_service.create_complaint(db, ComplaintCreate(**item), user_id=user_id)
            a = c.analysis
            print(f"{c.complaint_number}  {a.category:<24} {a.priority:<9} {a.assigned_department}  review={a.requires_human_review}")



if __name__ == "__main__":
    main()
