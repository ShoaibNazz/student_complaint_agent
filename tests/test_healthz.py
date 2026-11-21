import pytest
from sqlalchemy.orm import sessionmaker

from app.database.database import Base, make_engine
from app.models.enums import UserRole, ComplaintStatus
from app.models.user import User
from app.models.complaint import Complaint
from app.models.feedback import ComplaintFeedback
from app.services.complaint_service import get_department_csat_summary


@pytest.fixture()
def mem_db():
    eng = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with Session() as s:
        yield s
    eng.dispose()


def test_system_csat_health_calculation(mem_db):
    # Empty case
    empty_stats = get_department_csat_summary(mem_db)
    assert empty_stats["total_reviews"] == 0
    assert empty_stats["average"] == 5.0

    # Create user and complaints with ratings
    user = User(
        email="student.csat.sum@ue.edu.pk",
        full_name="CSAT Reviewer",
        password_hash="pwd",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    mem_db.add(user)
    mem_db.commit()

    c1 = Complaint(
        complaint_number="CMP-CSAT-1",
        user_id=user.id,
        student_name=user.full_name,
        title="WiFi issue",
        complaint_text="Slow internet in lab",
        status=ComplaintStatus.CLOSED.value,
    )
    c2 = Complaint(
        complaint_number="CMP-CSAT-2",
        user_id=user.id,
        student_name=user.full_name,
        title="Transport issue",
        complaint_text="Bus delay",
        status=ComplaintStatus.CLOSED.value,
    )
    mem_db.add_all([c1, c2])
    mem_db.commit()

    fb1 = ComplaintFeedback(
        complaint_id=c1.id,
        student_id=user.id,
        is_resolved=True,
        satisfaction_rating=5,
    )
    fb2 = ComplaintFeedback(
        complaint_id=c2.id,
        student_id=user.id,
        is_resolved=True,
        satisfaction_rating=3,
    )
    mem_db.add_all([fb1, fb2])
    mem_db.commit()

    stats = get_department_csat_summary(mem_db)
    assert stats["total_reviews"] == 2
    assert stats["average"] == 4.0  # (5 + 3) / 2 = 4.0
    assert stats["distribution"][5] == 1
    assert stats["distribution"][3] == 1
    assert stats["distribution"][4] == 0
