import os
import pytest
from sqlalchemy.orm import sessionmaker
from app.database.database import Base, make_engine
from app.models.user import User, UserRole
from app.models.notification import Notification
from app.services.notification_service import NotificationService


@pytest.fixture()
def mem_db():
    eng = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with Session() as s:
        yield s
    eng.dispose()


def test_in_app_notification_creation_and_lifecycle(mem_db):
    # 1. Create a student user
    student = User(
        email="student.test@ue.edu.pk",
        full_name="Ayesha Khan",
        password_hash="dummyhashedpwd",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    mem_db.add(student)
    mem_db.commit()
    mem_db.refresh(student)

    # 2. Create in-app notification
    notif = NotificationService.create_in_app_notification(
        mem_db,
        recipient_user_id=student.id,
        recipient_email=student.email,
        recipient_name=student.full_name,
        subject="Complaint #CMP-001 Assigned",
        body_preview="Your complaint has been assigned to IT Department",
        link="/student/complaints/1",
        notification_type="COMPLAINT_ASSIGNED",
    )
    assert notif.id is not None
    assert notif.is_read is False
    assert notif.recipient_user_id == student.id
    assert notif.link == "/student/complaints/1"

    # 3. Query unread notifications for student
    from sqlalchemy import or_
    user_notifs = (
        mem_db.query(Notification)
        .filter(or_(Notification.recipient_user_id == student.id, Notification.recipient_email == student.email))
        .order_by(Notification.id.desc())
        .all()
    )
    assert len(user_notifs) == 1
    assert user_notifs[0].subject == "Complaint #CMP-001 Assigned"
    assert user_notifs[0].is_read is False

    # 4. Mark as read
    user_notifs[0].is_read = True
    mem_db.commit()

    # 5. Verify unread count is now 0
    unread_count = (
        mem_db.query(Notification)
        .filter(
            or_(Notification.recipient_user_id == student.id, Notification.recipient_email == student.email),
            Notification.is_read == False,
        )
        .count()
    )
    assert unread_count == 0
