import pytest
from sqlalchemy.orm import sessionmaker

from app.database.database import Base, make_engine
from app.models.enums import UserRole, ComplaintStatus
from app.models.user import User
from app.models.complaint import Complaint
from app.models.clarification import ComplaintClarification
from app.models.notification import Notification
from app.services.complaint_service import add_complaint_clarification


@pytest.fixture()
def mem_db():
    eng = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with Session() as s:
        yield s
    eng.dispose()


def test_clarification_strict_privacy_confidential_complaint(mem_db):
    student = User(
        email="hidden.student@ue.edu.pk",
        full_name="Anonymous Student",
        password_hash="pwd",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    admin = User(
        email="admin@ue.edu.pk",
        full_name="Campus Admin",
        password_hash="pwd",
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    employee = User(
        email="emp@ue.edu.pk",
        full_name="IT Officer",
        password_hash="pwd",
        role=UserRole.EMPLOYEE.value,
        is_active=True,
    )
    mem_db.add_all([student, admin, employee])
    mem_db.commit()

    c = Complaint(
        complaint_number="CMP-CONF-777",
        user_id=student.id,
        student_name=student.full_name,
        email=student.email,
        title="Harassment Incident",
        complaint_text="Details are confidential",
        is_confidential=True,  # STRICT PRIVACY ACTIVE
        status=ComplaintStatus.IN_PROGRESS.value,
    )
    mem_db.add(c)
    mem_db.commit()
    mem_db.refresh(c)

    # 1. Student attempting to post clarification on confidential complaint MUST raise ValueError
    with pytest.raises(ValueError) as excinfo:
        add_complaint_clarification(mem_db, c.id, student, "Can I get an update?")
    assert "Two-way communication is disabled for confidential complaints" in str(excinfo.value)

    # 2. Staff members (Employee/Admin) can still post internal notes without exposing student
    emp_note = add_complaint_clarification(mem_db, c.id, employee, "Reviewed server logs for the incident.")
    assert emp_note.id is not None
    assert emp_note.sender_name == employee.full_name
    assert emp_note.message == "Reviewed server logs for the incident."


def test_clarification_two_way_collaboration_notifications(mem_db):
    student = User(
        email="student.open@ue.edu.pk",
        full_name="Hamza Tariq",
        password_hash="pwd",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    admin = User(
        email="admin.central@ue.edu.pk",
        full_name="Central Admin",
        password_hash="pwd",
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    authority = User(
        email="vc@ue.edu.pk",
        full_name="Vice Chancellor",
        password_hash="pwd",
        role=UserRole.HIGHER_AUTHORITY.value,
        authority_name="Vice Chancellor Office",
        is_active=True,
    )
    mem_db.add_all([student, admin, authority])
    mem_db.commit()

    c = Complaint(
        complaint_number="CMP-OPEN-888",
        user_id=student.id,
        student_name=student.full_name,
        email=student.email,
        title="Fee Challan Error",
        complaint_text="Duplicate fee voucher generated",
        is_confidential=False,
        status=ComplaintStatus.IN_PROGRESS.value,
    )
    mem_db.add(c)
    mem_db.commit()
    mem_db.refresh(c)

    # 1. Student asks Admin for clarification -> Admin gets notification
    m1 = add_complaint_clarification(mem_db, c.id, student, "I have attached my bank receipt.")
    assert m1.id is not None
    admin_notif = (
        mem_db.query(Notification)
        .filter(Notification.recipient_user_id == admin.id)
        .order_by(Notification.id.desc())
        .first()
    )
    assert admin_notif is not None
    assert "Clarification from Student" in admin_notif.subject

    # 2. Admin replies -> Student gets notification
    m2 = add_complaint_clarification(mem_db, c.id, admin, "We verified the receipt with Accounts branch.")
    assert m2.id is not None
    student_notif = (
        mem_db.query(Notification)
        .filter(Notification.recipient_user_id == student.id)
        .order_by(Notification.id.desc())
        .first()
    )
    assert student_notif is not None
    assert "Message from Admin" in student_notif.subject

    # 3. Higher Authority posts note -> Admin gets notification
    m3 = add_complaint_clarification(mem_db, c.id, authority, "Approved for fee waiver adjustment.")
    assert m3.id is not None
    auth_notif = (
        mem_db.query(Notification)
        .filter(Notification.recipient_user_id == admin.id)
        .order_by(Notification.id.desc())
        .first()
    )
    assert "Authority Direct Note" in auth_notif.subject
