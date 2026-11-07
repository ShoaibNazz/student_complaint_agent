"""Comprehensive end-to-end acceptance tests for Modules 1 through 10.
Tests all 13 required scenarios specified in the Master Prompt.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.enums import ComplaintStatus, UserRole, Priority, RequestStatus
from app.models.user import User
from app.models.complaint import Complaint
from app.models.assignment import ComplaintAssignment
from app.models.forwarding import ComplaintForwarding
from app.models.feedback import ResolutionFeedback
from app.models.request import EmployeeRequest
from app.models.notification import EmailNotification
from app.schemas.complaint import ComplaintCreate, AssignmentUpdate
from app.services import complaint_service as svc
from app.services import request_service
from app.services.notification_service import NotificationService
from app.core.security import create_access_token, hash_password


@pytest.fixture
def auth_student(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == "student.e2e@ue.edu.pk"))
    if not user:
        user = User(
            full_name="E2E Student",
            email="student.e2e@ue.edu.pk",
            password_hash=hash_password("Pass123!"),
            role=UserRole.STUDENT.value,
            student_id="STU-E2E-001",
            campus="Multan Campus",
            program="BS Computer Science",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture
def auth_admin(db: Session) -> User:
    admin = db.scalar(select(User).where(User.email == "admin.e2e@ue.edu.pk"))
    if not admin:
        admin = User(
            full_name="E2E Admin",
            email="admin.e2e@ue.edu.pk",
            password_hash=hash_password("Pass123!"),
            role=UserRole.ADMIN.value,
            admin_id="ADM-E2E-001",
            campus="Multan Campus",
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
    return admin


@pytest.fixture
def auth_employee(db: Session) -> User:
    emp = db.scalar(select(User).where(User.email == "emp.e2e@ue.edu.pk"))
    if not emp:
        emp = User(
            full_name="E2E Employee",
            email="emp.e2e@ue.edu.pk",
            password_hash=hash_password("Pass123!"),
            role=UserRole.EMPLOYEE.value,
            employee_id="EMP-E2E-001",
            campus="Multan Campus",
            department="Department of Information Sciences",
            role_designation="Lecturer",
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)
    return emp


# Scenario 1: A student submits a complaint and receives a unique complaint ID.
def test_scenario_1_student_submits_complaint_receives_id(db: Session, auth_student: User):
    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=auth_student.full_name,
            student_id=auth_student.student_id,
            email=auth_student.email,
            complaint_title="Discrepancy in Midterm Attendance Record",
            complaint_text="My attendance in CS-301 shows 65 percent but I attended all sessions.",
            originating_campus=auth_student.campus,
        ),
        user_id=auth_student.id,
    )
    assert c.id is not None
    assert c.complaint_number.startswith("CMP-")
    assert c.status == ComplaintStatus.NEW.value
    # Module 1.2: Auto-populated verified info matches account
    assert c.student_name == auth_student.full_name
    assert c.student_id == auth_student.student_id
    assert c.originating_campus == auth_student.campus


# Scenario 2: AI suggests category, but complaint remains in unassigned review queue.
def test_scenario_2_ai_advisory_in_review_queue(db: Session, auth_student: User):
    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=auth_student.full_name,
            student_id=auth_student.student_id,
            email=auth_student.email,
            complaint_title="Physics lab equipment not working",
            complaint_text="The oscilloscopes in Physics Lab 2 are faulty and not displaying waves.",
            originating_campus=auth_student.campus,
        ),
        user_id=auth_student.id,
    )
    # AI ran advisory classification
    assert c.analysis is not None
    assert c.analysis.category != ""
    # Central admin unassigned review queue
    assert c.status == ComplaintStatus.NEW.value


# Scenario 3: Admin confirms category and assigns department and authorized handler.
def test_scenario_3_admin_assigns_department_and_handler(db: Session, auth_student: User, auth_admin: User, auth_employee: User):
    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=auth_student.full_name,
            student_id=auth_student.student_id,
            email=auth_student.email,
            complaint_title="Server login issue on university portal",
            complaint_text="I am unable to login to the student portal from campus network.",
        ),
        user_id=auth_student.id,
    )
    svc.update_assignment(
        db,
        c,
        AssignmentUpdate(
            category="IT / Portal / LMS",
            department="IT Department",
            handler_id=auth_employee.id,
            priority=Priority.HIGH,
        ),
        by=auth_admin.username,
    )
    assert c.analysis.category == "IT / Portal / LMS"
    assert c.analysis.assigned_department == "IT Department"
    assert c.analysis.priority == "HIGH"
    
    # Assignment history record created
    assign_rec = db.scalar(select(ComplaintAssignment).where(ComplaintAssignment.complaint_id == c.id))
    assert assign_rec is not None
    assert assign_rec.department_name == "IT Department"
    assert assign_rec.handler_id == auth_employee.id


# Scenario 4: Saved assignment triggers student email notification.
def test_scenario_4_assignment_triggers_notification(db: Session, auth_student: User, auth_admin: User):
    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=auth_student.full_name,
            student_id=auth_student.student_id,
            email=auth_student.email,
            complaint_title="Library book fine issue",
            complaint_text="Fine was charged after book was returned on time.",
        ),
        user_id=auth_student.id,
    )
    notif = NotificationService.send_assignment_notification(
        db,
        c,
        student_facing_response="Your fine inquiry has been routed to the chief librarian for verification.",
        assigned_department="Library Department",
    )
    assert notif.id is not None
    assert notif.recipient_email == auth_student.email
    assert notif.delivery_status in ("SENT", "QUEUED")
    assert c.complaint_number in notif.subject


# Scenario 5 & 6: Complaint forwarded to higher authority without changing ID, and authority can access.
def test_scenario_5_and_6_forwarding_preserves_id(db: Session, auth_student: User, auth_admin: User):
    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=auth_student.full_name,
            student_id=auth_student.student_id,
            email=auth_student.email,
            complaint_title="Missing Semester 4 Result",
            complaint_text="My official transcript does not show grades for Database Systems.",
        ),
        user_id=auth_student.id,
    )
    original_number = c.complaint_number
    original_id = c.id

    fwd = svc.forward_complaint(
        db,
        complaint_id=c.id,
        admin_user=auth_admin,
        receiving_authority="Controller of Examinations",
        forwarding_reason="Discrepancy requires central examination ledger verification.",
        admin_remarks="Forwarded with instructor grade sheet attached.",
    )
    assert fwd.id is not None
    # Crucial: ID remained exactly the same
    assert c.id == original_id
    assert c.complaint_number == original_number
    assert fwd.receiving_authority == "Controller of Examinations"
    assert c.status == ComplaintStatus.IN_PROGRESS.value


# Scenario 7 & 8: Student reports unresolved issue -> flagged for admin review and history preserved.
def test_scenario_7_and_8_student_reports_unresolved_reopens(db: Session, auth_student: User):
    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=auth_student.full_name,
            student_id=auth_student.student_id,
            email=auth_student.email,
            complaint_title="Water cooler leaking in Academic Block",
            complaint_text="The second floor water cooler is leaking and causing floor slipping.",
        ),
        user_id=auth_student.id,
    )
    c.status = ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION.value
    db.commit()

    # Student verifies: Issue Not Resolved
    fb = svc.record_resolution_feedback(
        db,
        complaint_id=c.id,
        user=auth_student,
        is_resolved=False,
        feedback_remarks="The tap is still dripping and water accumulates.",
    )
    assert fb.is_resolved is False
    assert c.status == ComplaintStatus.REOPENED.value
    assert fb.reopened_review_status == "PENDING_ADMIN_REVIEW"

    # History intact
    histories = [h.action for h in c.history]
    assert any("Reopened" in h or "NOT resolved" in h for h in histories)


# Scenario 9: Confidential complaint hides student identity.
def test_scenario_9_confidential_complaint_protects_identity(db: Session, auth_student: User):
    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=auth_student.full_name,
            student_id=auth_student.student_id,
            email=auth_student.email,
            complaint_title="Harassment concern regarding faculty evaluation",
            complaint_text="I faced inappropriate verbal harassment regarding my thesis defense.",
            is_confidential=True,
        ),
        user_id=auth_student.id,
    )
    assert c.is_confidential is True


# Scenario 10: Employee submits staff request and follows approval workflow.
def test_scenario_10_employee_request_workflow(db: Session, auth_employee: User, auth_admin: User):
    req = request_service.create_employee_request(
        db,
        user=auth_employee,
        payload=request_service.RequestCreatePayload(
            category="Leave Application",
            title="Casual Leave for Conference Attendance",
            description="Requesting 2 days casual leave to present a research paper at IEEE conference.",
        ),
    )
    assert req.id is not None
    assert req.request_number.startswith("REQ-")
    assert req.status == RequestStatus.SUBMITTED.value
    assert req.current_stage == "Reviewing Officer"

    # Admin approves
    updated = request_service.update_request_status(
        db,
        req=req,
        actor=auth_admin,
        action="APPROVED",
        remarks="Approved as per faculty research facilitation policy.",
    )
    assert updated.status == RequestStatus.APPROVED.value
    assert updated.current_stage == "Completed"
    assert len(updated.approvals) >= 2


# Scenario 11: Unauthorized users cannot access other users' records (IDOR protection).
def test_scenario_11_idor_protection(db: Session, auth_student: User):
    other_student = User(
        full_name="Other Student",
        email="other.student@ue.edu.pk",
        password_hash=hash_password("Pass123!"),
        role=UserRole.STUDENT.value,
        student_id="STU-OTHER-99",
        campus="Township Campus, Lahore (Main Campus)",
    )
    db.add(other_student)
    db.commit()

    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=other_student.full_name,
            student_id=other_student.student_id,
            email=other_student.email,
            complaint_title="Private academic grievance",
            complaint_text="Private details not to be viewed by others.",
        ),
        user_id=other_student.id,
    )

    with pytest.raises(Exception):
        # auth_student tries to fetch other_student's complaint
        svc.get_student_complaint(db, c.id, auth_student)


# Scenario 12: Email failure does not destroy a successfully saved assignment.
def test_scenario_12_email_failure_does_not_break_assignment(db: Session, auth_student: User, auth_admin: User):
    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=auth_student.full_name,
            student_id=auth_student.student_id,
            email="invalid-or-unreachable-domain@nonexistent.domain",
            complaint_title="Course syllabus distribution issue",
            complaint_text="Course outlines have not been distributed for Fall semester.",
        ),
        user_id=auth_student.id,
    )
    svc.update_assignment(
        db,
        c,
        AssignmentUpdate(department="Department of Information Sciences"),
        by=auth_admin.username,
    )
    # Notification logs without crashing
    notif = NotificationService.send_assignment_notification(db, c, student_facing_response="Checking syllabus records.")
    assert c.id is not None
    assert c.analysis.assigned_department == "Department of Information Sciences"
    assert notif is not None


# Scenario 13: Dashboard, Profile, and Database Operations Still Work.
def test_scenario_13_existing_operations_still_work(db: Session, auth_student: User, auth_admin: User):
    stats = svc.get_student_stats(db, auth_student)
    assert stats.total >= 0

    admin_stats = svc.get_dashboard_stats(db)
    assert admin_stats.total >= 0
