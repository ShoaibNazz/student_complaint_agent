import io
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from app.main import app
from app.core.config import BASE_DIR
from app.database.database import SessionLocal
from app.models.complaint import Complaint
from app.models.user import User, UniversityDirectory
from app.models.enums import UserRole
from app.core.security import hash_password

client = TestClient(app)

def test_file_upload_under_500kb_success():
    db = SessionLocal()
    stu = db.query(User).filter(User.role == UserRole.STUDENT.value).first()
    if not stu:
        stu = User(
            full_name="Muhammad Ali",
            email="ali1001@example.edu",
            password_hash=hash_password("password123"),
            role=UserRole.STUDENT.value,
            student_id="STU-1001",
            program="BS Computer Science",
            department="Computer Science",
            campus="Township Campus, Lahore (Main Campus)",
        )
        db.add(stu)
        db.commit()
        db.refresh(stu)

    student_id = stu.student_id or stu.identifier or "STU-1001"
    student_name = stu.full_name
    student_email = stu.email
    campus = stu.campus or "Township Campus, Lahore (Main Campus)"
    program = stu.program or "BS Computer Science"
    db.close()

    # Valid PNG header + payload = ~50 KB (well under 500 KB)
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4" + (b"\x00" * 50000)
    data = {
        "ui_mode": "v2",
        "account_type": "STUDENT",
        "student_name": student_name,
        "student_id": student_id,
        "email": student_email,
        "originating_campus": campus,
        "target_campus": campus,
        "class_or_program": program,
        "subject": "Test Area",
        "complaint_title": "Complaint with 50KB image",
        "complaint_text": "This complaint includes a valid image under 500KB that should upload successfully.",
    }
    files = {
        "attachment": ("receipt.png", png_bytes, "image/png")
    }
    resp = client.post("/submit", data=data, files=files)
    assert resp.status_code == 200

    db = SessionLocal()
    complaint = db.query(Complaint).filter(Complaint.student_id == student_id, Complaint.title == "Complaint with 50KB image").first()
    assert complaint is not None
    assert complaint.attachment_name == "receipt.png"
    assert complaint.attachment_path is not None
    assert complaint.attachment_path.startswith("/static/uploads/complaints/")

    # Check file exists on disk
    disk_path = Path(BASE_DIR) / "app" / complaint.attachment_path.lstrip("/")
    assert disk_path.exists()
    disk_path.unlink() # Cleanup

    db.delete(complaint)
    db.commit()
    db.close()


def test_file_upload_over_500kb_rejected():
    # Payload over 500 KB (550 KB)
    oversized_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4" + (b"\x00" * 560000)
    data = {
        "ui_mode": "v2",
        "account_type": "STUDENT",
        "student_name": "Test Student Oversized",
        "student_id": "TEST-2026-OVER",
        "email": "test.over@ue.edu.pk",
        "originating_campus": "Multan Campus",
        "target_campus": "Multan Campus",
        "class_or_program": "BS Computer Science",
        "subject": "Test Area",
        "complaint_title": "Complaint with 550KB image",
        "complaint_text": "This should be rejected due to 500KB limit.",
    }
    files = {
        "attachment": ("large.png", oversized_bytes, "image/png")
    }
    resp = client.post("/submit", data=data, files=files)
    assert resp.status_code == 422
    assert "Attached image exceeds the maximum allowed size of 500 KB" in resp.text
