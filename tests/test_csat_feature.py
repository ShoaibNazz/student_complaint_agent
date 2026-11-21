import pytest
from sqlalchemy.orm import sessionmaker

from app.database.database import Base, make_engine
from app.models.enums import UserRole, ComplaintStatus
from app.models.user import User
from app.models.complaint import Complaint
from app.models.feedback import ComplaintFeedback
from app.models.notification import Notification
from app.services.complaint_service import record_resolution_feedback


@pytest.fixture()
def mem_db():
    eng = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with Session() as s:
        yield s
    eng.dispose()


def test_student_csat_5_star_resolution(mem_db):
    # 1. Setup Student and Admin
    admin = User(
        email="admin@ue.edu.pk",
        full_name="Super Administrator",
        password_hash="pwdhash",
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    student = User(
        email="student.csat@ue.edu.pk",
        full_name="Farhan Ali",
        password_hash="pwdhash",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    mem_db.add_all([admin, student])
    mem_db.commit()
    mem_db.refresh(admin)
    mem_db.refresh(student)

    # 2. Setup Complaint assigned to student
    c = Complaint(
        complaint_number="CMP-CSAT-101",
        user_id=student.id,
        student_name=student.full_name,
        email=student.email,
        title="Hostel Internet Issue",
        complaint_text="Wi-Fi not working on 2nd floor",
        status=ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value,
    )
    mem_db.add(c)
    mem_db.commit()
    mem_db.refresh(c)

    # 3. Student submits CSAT rating (5 stars)
    fb = record_resolution_feedback(
        mem_db,
        complaint_id=c.id,
        user=student,
        is_resolved=True,
        feedback_remarks="The IT team fixed the router promptly. Excellent service!",
        satisfaction_rating=5,
    )

    assert fb.id is not None
    assert fb.is_resolved is True
    assert fb.satisfaction_rating == 5
    assert "router promptly" in fb.feedback_remarks
    assert c.status == ComplaintStatus.CLOSED.value

    # 4. Check admin notification generated
    admin_notif = (
        mem_db.query(Notification)
        .filter(Notification.recipient_user_id == admin.id)
        .order_by(Notification.id.desc())
        .first()
    )
    assert admin_notif is not None
    assert "Resolution Confirmed" in admin_notif.subject
    assert "5/5" in admin_notif.body_preview


def test_student_dispute_resolution_reopens_complaint(mem_db):
    # Setup Student and Complaint
    student = User(
        email="student.dispute@ue.edu.pk",
        full_name="Sara Ahmed",
        password_hash="pwdhash",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    mem_db.add(student)
    mem_db.commit()
    mem_db.refresh(student)

    c = Complaint(
        complaint_number="CMP-DISPUTE-202",
        user_id=student.id,
        student_name=student.full_name,
        email=student.email,
        title="Lab AC not working",
        complaint_text="Lab 3 AC unit is making noise and not cooling",
        status=ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value,
    )
    mem_db.add(c)
    mem_db.commit()
    mem_db.refresh(c)

    # Student disputes resolution
    fb = record_resolution_feedback(
        mem_db,
        complaint_id=c.id,
        user=student,
        is_resolved=False,
        feedback_remarks="The AC was turned on for 5 minutes and stopped again. Still hot.",
    )

    assert fb.is_resolved is False
    assert c.status == ComplaintStatus.REOPENED.value
    assert fb.reopened_review_status == "PENDING_ADMIN_REVIEW"
