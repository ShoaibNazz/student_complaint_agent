import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.database import get_db
from app.models.enums import UserRole, ComplaintStatus
from app.models.user import User
from app.core.security import create_access_token, hash_password
from app.services import complaint_service as svc
from app.schemas.complaint import ComplaintCreate


def test_admin_dashboard_and_navbar(client: TestClient, db: Session):
    admin = db.query(User).filter(User.role == UserRole.ADMIN.value).first()
    if not admin:
        admin = User(
            full_name="Admin User",
            email="admin.test@ue.edu.pk",
            password_hash=hash_password("password123"),
            role=UserRole.ADMIN.value,
            admin_id="ADMIN-TEST-1",
            campus="Multan Campus",
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

    token = create_access_token({"sub": str(admin.id), "role": admin.role})
    client.cookies.set("complaint_session", token)

    # 1. Admin dashboard should have "My Requests" in navbar only, and "Submit Request" on page only
    resp = client.get("/admin/dashboard")
    assert resp.status_code == 200
    assert "/admin/requests" in resp.text
    assert "My Requests" in resp.text
    assert "Submit Request" in resp.text
    assert "Submit Complaint" not in resp.text

    # Navbar check: has My Requests, does NOT have Submit Request
    navbar_html = resp.text[resp.text.find("<nav"):resp.text.find("</nav>")]
    assert "My Requests" in navbar_html
    assert "/admin/requests/new" not in navbar_html

    # Dashboard page check: has Submit Request button, does NOT have My Requests button
    dashboard_actions = resp.text[resp.text.find("d-flex flex-wrap gap-2"):resp.text.find("row g-3 mb-4")]
    assert "Submit Request" in dashboard_actions
    assert "My Requests" not in dashboard_actions

    # And navbar should have Profile
    assert "/admin/profile" in resp.text

    # 2. Admin Profile page works
    resp = client.get("/admin/profile")
    assert resp.status_code == 200
    assert "Edit Profile" in resp.text

    # 3. Admin My Requests page works
    resp = client.get("/admin/requests")
    assert resp.status_code == 200
    assert "My Administrative Requests" in resp.text

    # 4. Admin Submit Request page works
    resp = client.get("/admin/requests/new")
    assert resp.status_code == 200
    assert "Administrative Application" in resp.text
    assert "Send Request To / Target Authority" in resp.text
    assert "Vice Chancellor (VC) / Pro-VC Office" in resp.text

    # 5. Admin Departments page works with modern design
    resp = client.get("/admin/departments")
    assert resp.status_code == 200
    assert "Departments Overview" in resp.text
    assert "Filter Department Distribution" in resp.text
    assert "Total Departments:" in resp.text


def test_employee_dashboard_and_navbar(client: TestClient, db: Session):
    emp = db.query(User).filter(User.role == UserRole.EMPLOYEE.value).first()
    if not emp:
        emp = User(
            full_name="Dr. Irtaza Sheikh",
            email="irtaza.test@ue.edu.pk",
            password_hash=hash_password("password123"),
            role=UserRole.EMPLOYEE.value,
            employee_id="EMP-TEST-001",
            department="Department of Information Sciences",
            campus="Multan Campus",
            role_designation="Assistant Professor",
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)

    token = create_access_token({"sub": str(emp.id), "role": emp.role})
    client.cookies.set("complaint_session", token)

    # 1. Employee dashboard:
    resp = client.get("/employee/dashboard")
    assert resp.status_code == 200
    # Navbar does NOT have "My Complaints" or "Submit Complaint"
    assert "/employee/my-complaints" not in resp.text
    assert "/submit" not in resp.text
    # Navbar has "Assigned Complaints"
    assert "/employee/complaints" in resp.text
    # Navbar has "Profile"
    assert "/employee/profile" in resp.text

    # Verify that the Submit Complaint button was removed from the header card
    # (The welcome card should NOT contain Submit Complaint button)
    welcome_card = resp.text.split("Welcome, ")[1].split("<!-- Summary stats -->")[0]
    assert "Submit Complaint" not in welcome_card

    # 2. Employee My Complaints page works
    resp = client.get("/employee/my-complaints")
    assert resp.status_code == 200
    assert "My Complaints" in resp.text


def test_employee_submit_and_view_my_complaints(client: TestClient, db: Session):
    emp = db.query(User).filter(User.role == UserRole.EMPLOYEE.value).first()
    if not emp:
        emp = User(
            full_name="Dr. Irtaza Sheikh",
            email="irtaza.test2@ue.edu.pk",
            password_hash=hash_password("password123"),
            role=UserRole.EMPLOYEE.value,
            employee_id="EMP-TEST-002",
            department="Department of Information Sciences",
            campus="Multan Campus",
            role_designation="Assistant Professor",
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)

    token = create_access_token({"sub": str(emp.id), "role": emp.role})
    client.cookies.set("complaint_session", token)

    # Create a complaint submitted by this employee
    c = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name=emp.full_name,
            student_id=emp.employee_id,
            email=emp.email,
            complaint_title="Test Projector Issue in Lab 3",
            complaint_text="The projector in Lab 3 has ceased functioning during lectures.",
            target_campus="Multan Campus",
            originating_campus="Multan Campus",
            class_or_program=emp.department,
        ),
        user_id=emp.id,
    )

    # Check that it shows up on /employee/my-complaints
    resp = client.get("/employee/my-complaints")
    assert resp.status_code == 200
    assert c.complaint_number in resp.text
    assert "Test Projector Issue in Lab 3" in resp.text

    # Check detail page /employee/my-complaints/{id}
    resp = client.get(f"/employee/my-complaints/{c.id}")
    assert resp.status_code == 200
    assert c.complaint_number in resp.text
    assert "Test Projector Issue in Lab 3" in resp.text
    assert "Back to My Complaints" in resp.text


def test_administrative_requests_and_departments_enhancements(client: TestClient, db: Session):
    emp = db.query(User).filter(User.role == UserRole.EMPLOYEE.value).first()
    if not emp:
        emp = User(
            full_name="Dr. Irtaza Sheikh",
            email="irtaza.requests@ue.edu.pk",
            password_hash=hash_password("password123"),
            role=UserRole.EMPLOYEE.value,
            employee_id="EMP-TEST-003",
            department="Department of Information Sciences",
            campus="Multan Campus",
            role_designation="Assistant Professor",
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)

    token = create_access_token({"sub": str(emp.id), "role": emp.role})
    client.cookies.set("complaint_session", token)

    # 1. Employee Submit Request form has target recipient dropdown with recommended employee options
    resp = client.get("/employee/requests/new")
    assert resp.status_code == 200
    assert "Send Request To / Target Authority" in resp.text
    assert "Head of Department (HoD) / Chairperson" in resp.text
    assert "Dean of Faculty" in resp.text
    assert "Registrar Office" in resp.text
    assert "Human Resources (HR) Department" in resp.text
    assert "Campus Director / Campus Administrator" in resp.text
    assert "Accounts / Finance Department" in resp.text
    assert "Directorate of Student Affairs" in resp.text

    # 2. Submit application with target recipient
    target_auth = "Head of Department (HoD) / Chairperson – For departmental workload, internal schedules, and course assignments."
    post_resp = client.post("/employee/requests/new", data={
        "category": "Workload Change",
        "target_authority": target_auth,
        "title": "Semester Workload Adjustment Request",
        "description": "Requesting course allocation revision according to departmental policy guidelines.",
    }, follow_redirects=True)
    assert post_resp.status_code == 200
    assert "Semester Workload Adjustment Request" in post_resp.text
    assert "Head of Department (HoD) / Chairperson" in post_resp.text

    # 3. Request appears on /employee/requests
    list_resp = client.get("/employee/requests")
    assert list_resp.status_code == 200
    assert "Semester Workload Adjustment Request" in list_resp.text
    assert "Head of Department (HoD) / Chairperson" in list_resp.text
