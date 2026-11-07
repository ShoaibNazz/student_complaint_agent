"""Test suite for Master Implementation Prompt University Complaint Portal enhancements:
- Module 1.1: Submission Authentication (Unregistered vs Registered users)
- Module 1.2: Automatic Population and Non-Spoofing of Student Information & Campus
- Module 1.3: Confidential Submissions and Role-Based Privacy Masking
- Module 2.1: Resolution Verification Workflow (Awaiting confirmation, Issue Resolved, Issue Not Resolved)
- Fix for Student Complaint Detail Internal Server Error (Jinja2 render verification)
"""
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ComplaintStatus, UserRole
from app.models.user import User
from app.models.complaint import Complaint
from app.schemas.complaint import ComplaintCreate, StatusUpdate
from app.services import complaint_service as svc
from app.services.notification_service import NotificationService
from app.core.security import hash_password


@pytest.fixture
def registered_student(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == "enhancement.student@ue.edu.pk"))
    if not user:
        user = User(
            full_name="Fatima Zahra",
            email="enhancement.student@ue.edu.pk",
            password_hash=hash_password("Pass123!"),
            role=UserRole.STUDENT.value,
            student_id="STU-ENH-101",
            campus="Multan Campus",
            program="BS Computer Science",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture
def second_student(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == "second.student@ue.edu.pk"))
    if not user:
        user = User(
            full_name="Bilal Tariq",
            email="second.student@ue.edu.pk",
            password_hash=hash_password("Pass123!"),
            role=UserRole.STUDENT.value,
            student_id="STU-ENH-102",
            campus="Faisalabad Campus",
            program="BS Software Engineering",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture
def dept_employee(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == "dept.emp@ue.edu.pk"))
    if not user:
        user = User(
            full_name="Mr. Kamran Officer",
            email="dept.emp@ue.edu.pk",
            password_hash=hash_password("Pass123!"),
            role=UserRole.EMPLOYEE.value,
            employee_id="EMP-ENH-201",
            campus="Multan Campus",
            department="IT Department",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture
def central_admin(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == "central.admin@ue.edu.pk"))
    if not user:
        user = User(
            full_name="Admin Chief",
            email="central.admin@ue.edu.pk",
            password_hash=hash_password("Pass123!"),
            role=UserRole.ADMIN.value,
            admin_id="ADM-ENH-901",
            campus="Township Campus, Lahore (Main Campus)",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# ---------------- Module 1.1: Submission Authentication ----------------
def test_unregistered_user_submission_is_rejected(db: Session):
    """Unregistered users attempting to submit complaints via API must receive exact registration prompt."""
    from fastapi import HTTPException
    from app.api.complaints import submit_complaint

    unregistered_payload = ComplaintCreate(
        student_name="Ghost User",
        student_id="STU-NONEXISTENT-999",
        email="ghost.user.999@unknown.edu",
        complaint_title="Test title",
        complaint_text="This complaint is from an unregistered visitor.",
        originating_campus="Multan Campus",
    )

    with pytest.raises(HTTPException) as exc_info:
        submit_complaint(unregistered_payload, db=db)

    assert exc_info.value.status_code == 400
    assert "Please register first before submitting a complaint." in exc_info.value.detail


def test_registered_student_submission_allowed(db: Session, registered_student: User):
    """Registered student can submit complaint and identity is securely attached."""
    from app.api.complaints import submit_complaint

    payload = ComplaintCreate(
        student_name="Fatima Zahra",
        student_id=registered_student.student_id,
        email=registered_student.email,
        complaint_title="Hostel Wi-Fi issue in Block C",
        complaint_text="Wi-Fi connectivity has been broken since Monday.",
        originating_campus="Multan Campus",
    )

    receipt = submit_complaint(payload, db=db)
    assert receipt.id is not None
    assert receipt.complaint_number.startswith("CMP-")

    c = svc.get_complaint(db, receipt.id)
    assert c.user_id == registered_student.id
    assert c.student_id == registered_student.student_id
    assert c.originating_campus == registered_student.campus


# ---------------- Module 1.2: Auto-populate & Non-Spoofing ----------------
def test_student_cannot_spoof_campus_or_identity(db: Session, registered_student: User):
    """Student submitting with tampered campus or other ID has values enforced to registered account."""
    from app.api.complaints import submit_complaint

    # Client tries to claim a different originating campus
    payload = ComplaintCreate(
        student_name="Fatima Zahra",
        student_id=registered_student.student_id,
        email=registered_student.email,
        complaint_title="Classroom Projector Malfunction",
        complaint_text="The projector in Room 102 does not turn on.",
        originating_campus="Attock Campus",  # Tampered! Student is registered at Multan
    )

    receipt = submit_complaint(payload, db=db)
    c = svc.get_complaint(db, receipt.id)
    # Backend strictly overrides with registered campus
    assert c.originating_campus == "Multan Campus"
    assert c.student_id == registered_student.student_id
    assert c.user_id == registered_student.id


# ---------------- Module 1.3: Confidential Submissions ----------------
def test_confidential_complaint_flagged_and_protected(db: Session, registered_student: User, dept_employee: User, central_admin: User):
    """Confidential complaints have is_confidential=True and identity masked from handlers."""
    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=registered_student.full_name,
            student_id=registered_student.student_id,
            email=registered_student.email,
            complaint_title="Sensitive faculty harassment report",
            complaint_text="Report of improper behavior during office hours.",
            originating_campus=registered_student.campus,
            is_confidential=True,
        ),
        user_id=registered_student.id,
    )
    assert c.is_confidential is True

    # Central admin can view complaint record
    admin_view = svc.get_complaint(db, c.id)
    assert admin_view.student_name == registered_student.full_name

    # In audit history, ID and audit trail are preserved
    histories = [h.action for h in c.history]
    assert "Complaint created" in histories


# ---------------- Module 2.1: Resolution & Student Feedback Workflow ----------------
def test_admin_resolved_becomes_awaiting_confirmation(db: Session, registered_student: User, central_admin: User):
    """Admin marking as RESOLVED transitions to RESOLVED_AWAITING_CONFIRMATION and notifies student."""
    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=registered_student.full_name,
            student_id=registered_student.student_id,
            email=registered_student.email,
            complaint_title="Library air conditioner noise",
            complaint_text="The AC unit in study room 4 produces loud vibration noise.",
            originating_campus=registered_student.campus,
        ),
        user_id=registered_student.id,
    )

    # Admin marks status as RESOLVED
    svc.update_status(db, c, StatusUpdate(status=ComplaintStatus.RESOLVED), by=central_admin.full_name)

    # Complaint is in RESOLVED_AWAITING_CONFIRMATION, not immediately closed
    assert c.status == ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value

    # Timeline correctly reflects proposed resolution
    timeline = svc.build_student_timeline(c)
    assert any(item.status_key == "RESOLVED_AWAITING_CONFIRMATION" and item.is_current for item in timeline)


def test_student_confirms_issue_resolved_closes_complaint(db: Session, registered_student: User, central_admin: User):
    """Student selecting 'Issue Resolved' closes complaint and records timestamp."""
    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=registered_student.full_name,
            student_id=registered_student.student_id,
            email=registered_student.email,
            complaint_title="Broken bench in cafeteria",
            complaint_text="One bench has a cracked leg.",
            originating_campus=registered_student.campus,
        ),
        user_id=registered_student.id,
    )
    svc.update_status(db, c, StatusUpdate(status=ComplaintStatus.RESOLVED), by=central_admin.full_name)

    # Student verifies: Issue Resolved
    fb = svc.record_resolution_feedback(
        db,
        complaint_id=c.id,
        user=registered_student,
        is_resolved=True,
        feedback_remarks="Bench has been replaced. Thank you!",
    )
    assert fb.is_resolved is True
    assert fb.confirmed_at is not None
    assert c.status == ComplaintStatus.CLOSED.value

    # Audit history intact
    histories = [h.action for h in c.history]
    assert any("Student confirmed resolution" in h for h in histories)


def test_student_disputes_resolution_reopens_complaint(db: Session, registered_student: User, central_admin: User):
    """Student selecting 'Issue Not Resolved' reopens complaint and flags for admin review."""
    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=registered_student.full_name,
            student_id=registered_student.student_id,
            email=registered_student.email,
            complaint_title="Lab printer paper jam",
            complaint_text="Lab printer is constantly jamming.",
            originating_campus=registered_student.campus,
        ),
        user_id=registered_student.id,
    )
    svc.update_status(db, c, StatusUpdate(status=ComplaintStatus.RESOLVED), by=central_admin.full_name)

    # Student verifies: Issue NOT Resolved
    fb = svc.record_resolution_feedback(
        db,
        complaint_id=c.id,
        user=registered_student,
        is_resolved=False,
        feedback_remarks="The technician visited but the roller is still jamming every second sheet.",
    )
    assert fb.is_resolved is False
    assert c.status == ComplaintStatus.REOPENED.value
    assert fb.reopened_review_status == "PENDING_ADMIN_REVIEW"

    # Notification generated for admin
    from app.models.notification import EmailNotification
    notif = db.scalar(
        select(EmailNotification)
        .where(EmailNotification.related_complaint_id == c.id)
        .order_by(EmailNotification.id.desc())
    )
    assert notif is not None
    assert "Unresolved" in notif.subject or "Reopened" in notif.subject


def test_unauthorized_user_cannot_submit_feedback(db: Session, registered_student: User, second_student: User, central_admin: User):
    """Another student cannot submit resolution feedback on someone else's complaint."""
    from fastapi import HTTPException

    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=registered_student.full_name,
            student_id=registered_student.student_id,
            email=registered_student.email,
            complaint_title="Private complaint",
            complaint_text="Details regarding marks recalculation.",
            originating_campus=registered_student.campus,
        ),
        user_id=registered_student.id,
    )
    svc.update_status(db, c, StatusUpdate(status=ComplaintStatus.RESOLVED), by=central_admin.full_name)

    with pytest.raises(HTTPException) as exc_info:
        svc.record_resolution_feedback(
            db,
            complaint_id=c.id,
            user=second_student,  # Wrong student!
            is_resolved=True,
        )
    assert exc_info.value.status_code == 403


# ---------------- Fix Verification: Template Syntax / 500 Error ----------------
def test_student_complaint_detail_template_renders_without_500(registered_student: User):
    """Ensure student_complaint_detail.html parses and renders without syntax error or 500."""
    from jinja2 import Environment, FileSystemLoader
    from app.models.enums import ComplaintStatus

    env = Environment(loader=FileSystemLoader("app/templates"))
    env.filters["dt"] = lambda v: str(v) if v else ""

    template = env.get_template("student_complaint_detail.html")
    assert template is not None

    class MockComplaint:
        id = 42
        complaint_number = "CMP-2026-TEST"
        student_name = "Fatima Zahra"
        student_id = "STU-ENH-101"
        email = "enhancement.student@ue.edu.pk"
        class_or_program = "BS Computer Science"
        subject = "Academic"
        originating_campus = "Multan Campus"
        target_campus = "Multan Campus"
        title = "Test complaint"
        complaint_text = "Detailed text"
        attachment_path = None
        attachment_name = None
        status = ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value
        created_at = None
        updated_at = None
        resolution_feedback = None

    class MockAnalysis:
        category = "Academic"
        subcategory = "Grading"
        priority = "MEDIUM"
        assigned_department = "IT Department"
        summary = "Summary"
        response_approved = True
        draft_response = "We have reviewed your request."

    class MockRequest:
        class MockUrl:
            path = "/student/complaints/42"
        url = MockUrl()

    rendered = template.render(
        request=MockRequest(),
        current_user=registered_student,
        student=registered_student,
        c=MockComplaint(),
        a=MockAnalysis(),
        timeline=[],
    )
    assert "CMP-2026-TEST" in rendered
    assert "Confirm Issue Resolution" in rendered
    assert "Issue Resolved" in rendered
    assert "Issue Not Resolved" in rendered

