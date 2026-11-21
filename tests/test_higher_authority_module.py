import os
import pytest
from sqlalchemy.orm import sessionmaker

from app.database.database import Base, make_engine
from app.models.enums import UserRole, ComplaintStatus
from app.models.user import User, HigherAuthorityProfile
from app.models.complaint import Complaint
from app.schemas.user import UserRegisterRequest
from app.services.user_service import register_user, get_user_by_identifier
from app.core.security import authenticate_user
from app.services.complaint_service import (
    get_escalation_authorities,
    forward_complaint,
    get_authority_forwarded_complaints,
    get_authority_campus_breakdown,
    update_authority_complaint,
    forward_authority_complaint_to_another,
)


@pytest.fixture()
def mem_db():
    eng = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with Session() as s:
        yield s
    eng.dispose()


def test_higher_authority_registration_and_login(mem_db):
    authorities = get_escalation_authorities()
    assert len(authorities) >= 6
    names = [a["name"] for a in authorities]
    assert "Controller of Examinations" in names
    assert "Registrar Office" in names
    assert "Pro-Vice Chancellor Office" in names

    # Register Higher Authority
    reg_req = UserRegisterRequest(
        account_type="HIGHER_AUTHORITY",
        identifier="AUTH-1001",
        full_name="Dr. Examination Controller",
        email="controller@ue.edu.pk",
        password="Password123",
        confirm_password="Password123",
        campus="Township Campus, Lahore (Main Campus)",
        authority_name="Controller of Examinations",
        department="Controller of Examinations",
    )
    user = register_user(mem_db, reg_req, strict_mode=False)
    assert user.role == UserRole.HIGHER_AUTHORITY.value
    assert user.identifier == "AUTH-1001"
    assert user.authority_name == "Controller of Examinations"
    assert user.department == "Controller of Examinations"
    assert user.authority_profile is not None
    assert user.authority_profile.authority_name == "Controller of Examinations"

    # Authenticate via ID
    auth_user = authenticate_user(mem_db, "HIGHER_AUTHORITY", "AUTH-1001", "Password123")
    assert auth_user is not None
    assert auth_user.id == user.id

    # Authenticate via Email
    auth_email_user = authenticate_user(mem_db, "HIGHER_AUTHORITY", "controller@ue.edu.pk", "Password123")
    assert auth_email_user is not None
    assert auth_email_user.id == user.id


def test_campus_filtering_and_breakdown(mem_db):
    # Create Admin
    admin_reg = UserRegisterRequest(
        account_type="ADMIN",
        identifier="ADMIN-1001",
        full_name="System Admin",
        email="admin@ue.edu.pk",
        password="Password123",
        confirm_password="Password123",
        campus="Township Campus, Lahore (Main Campus)",
    )
    admin = register_user(mem_db, admin_reg, strict_mode=False)

    # Create Higher Authority
    ha_reg = UserRegisterRequest(
        account_type="HIGHER_AUTHORITY",
        identifier="AUTH-1002",
        full_name="Registrar Officer",
        email="registrar@ue.edu.pk",
        password="Password123",
        confirm_password="Password123",
        campus="Township Campus, Lahore (Main Campus)",
        authority_name="Registrar Office",
        department="Registrar Office",
    )
    ha_user = register_user(mem_db, ha_reg, strict_mode=False)

    # Create complaints across 2 campuses
    c1 = Complaint(
        complaint_number="CMP-2026-000201",
        student_name="Zahid Iqbal",
        student_id_code="bsf21001",
        email="zahid@ue.edu.pk",
        originating_campus="Faisalabad Campus",
        target_campus="Faisalabad Campus",
        title="Degree verification issue",
        complaint_text="Degree verification delayed by administrative cell.",
        status=ComplaintStatus.PENDING.value,
    )
    c2 = Complaint(
        complaint_number="CMP-2026-000202",
        student_name="Hina Tariq",
        student_id_code="bsf21002",
        email="hina@ue.edu.pk",
        originating_campus="Faisalabad Campus",
        target_campus="Faisalabad Campus",
        title="Transcript issuance delay",
        complaint_text="Need verified transcript for scholarship.",
        status=ComplaintStatus.PENDING.value,
    )
    c3 = Complaint(
        complaint_number="CMP-2026-000203",
        student_name="Hamza Aslam",
        student_id_code="bsf21003",
        email="hamza@ue.edu.pk",
        originating_campus="Multan Campus",
        target_campus="Multan Campus",
        title="Enrollment discrepancy",
        complaint_text="Student status showing unconfirmed.",
        status=ComplaintStatus.PENDING.value,
    )
    mem_db.add_all([c1, c2, c3])
    mem_db.commit()

    # Admin forwards to Registrar Office
    forward_complaint(mem_db, c1.id, admin, "Registrar Office", "Official verification needed.")
    forward_complaint(mem_db, c2.id, admin, "Registrar Office", "Transcript clearance required.")
    forward_complaint(mem_db, c3.id, admin, "Registrar Office", "Enrollment database check.")

    # Higher authority queries complaints
    all_fwd = get_authority_forwarded_complaints(mem_db, authority_name="Registrar Office")
    assert len(all_fwd) == 3

    # Filter by campus: Faisalabad
    fsd_only = get_authority_forwarded_complaints(mem_db, authority_name="Registrar Office", campus="Faisalabad Campus")
    assert len(fsd_only) == 2

    # Filter by campus: Multan
    multan_only = get_authority_forwarded_complaints(mem_db, authority_name="Registrar Office", campus="Multan Campus")
    assert len(multan_only) == 1

    # Check breakdown & top campus
    stats, top_campus, counts = get_authority_campus_breakdown(mem_db, authority_name="Registrar Office")
    assert counts["total"] == 3
    assert top_campus is not None
    assert "Faisalabad" in top_campus["campus"]
    assert top_campus["total"] == 2


def test_status_update_and_reforwarding(mem_db):
    admin = register_user(mem_db, UserRegisterRequest(
        account_type="ADMIN", identifier="ADMIN-1003", full_name="Admin", email="admin3@ue.edu.pk",
        password="Password123", confirm_password="Password123",
        campus="Township Campus, Lahore (Main Campus)",
    ), strict_mode=False)

    ha_user = register_user(mem_db, UserRegisterRequest(
        account_type="HIGHER_AUTHORITY", identifier="AUTH-1003", full_name="Dean Affairs", email="dsa@ue.edu.pk",
        password="Password123", confirm_password="Password123",
        campus="Township Campus, Lahore (Main Campus)",
        authority_name="Directorate of Student Affairs (DSA)",
    ), strict_mode=False)

    c = Complaint(
        complaint_number="CMP-2026-000301",
        student_name="Sara Ahmed",
        student_id_code="bsf21004",
        email="sara@ue.edu.pk",
        originating_campus="Township Campus, Lahore (Main Campus)",
        title="Hostel room dispute",
        complaint_text="Room allocation error in Girls Hostel.",
        status=ComplaintStatus.PENDING.value,
    )
    mem_db.add(c)
    mem_db.commit()

    forward_complaint(mem_db, c.id, admin, "Directorate of Student Affairs (DSA)", "Hostel administration matter.")

    # Status update by Higher Authority
    updated = update_authority_complaint(
        mem_db, c.id, ha_user, "RESOLVED", "Room reallocation approved and room key handed over to student."
    )
    assert updated.status == "RESOLVED"
    assert any("resolved" in h.action.lower() for h in updated.history)

    # Re-escalate to Vice-Chancellor's Secretariat
    re_fwd = forward_authority_complaint_to_another(
        mem_db, c.id, ha_user, "Vice-Chancellor's Secretariat", "Policy clarification on hostel quotas."
    )
    assert re_fwd.receiving_authority == "Vice-Chancellor's Secretariat"
    assert re_fwd.sender_authority == "Directorate of Student Affairs (DSA)"
