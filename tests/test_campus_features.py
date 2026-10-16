"""Integration and unit tests for campus-based registration, routing,
RBAC scoping, and navbar UI styling.
"""
import pytest
from app.models.campus import Campus
from app.models.enums import UserRole
from app.models.user import User
from app.services import complaint_service as svc
from app.services.user_service import get_user_by_email


def _login(client, account_type: str, identifier: str, password: str = "password123"):
    return client.post("/api/auth/login", json={
        "account_type": account_type,
        "identifier": identifier,
        "password": password,
    })


def _token(client, account_type: str, identifier: str, password: str = "password123"):
    res = _login(client, account_type, identifier, password)
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


# 1. Navbar and Logout UI check
def test_navbar_and_logout_elements_rendered(client):
    token = _token(client, "ADMIN", "ADMIN-001", "adminpassword")
    client.cookies.set("complaint_session", token)

    res = client.get("/admin/dashboard")
    assert res.status_code == 200
    html = res.text

    # Navbar links must have portal-nav-link (not the old yellow button style)
    assert "portal-nav-link" in html
    assert "btn-portal-logout" in html
    assert "Logout" in html

    # Public submit button preserved
    public_res = client.get("/submit")
    assert public_res.status_code == 200
    assert "cmp-submit-btn" in public_res.text


# 2. Registration fails without campus
def test_registration_requires_campus(client):
    res = client.post("/register", data={
        "account_type": "STUDENT",
        "full_name": "Test Student Campus",
        "identifier": "STU-8801",
        "email": "test.campus.8801@example.edu",
        "program": "BS Computer Science",
        "campus": "",  # Empty campus
        "password": "password123",
        "confirm_password": "password123",
    })
    assert res.status_code == 422
    assert "Please select your Campus" in res.text


# 3. Registration fails if passwords do not match
def test_registration_password_mismatch(client):
    res = client.post("/register", data={
        "account_type": "STUDENT",
        "full_name": "Test Mismatch",
        "identifier": "STU-8802",
        "email": "test.mismatch.8802@example.edu",
        "program": "BS Computer Science",
        "campus": "Township Campus, Lahore (Main Campus)",
        "password": "password123",
        "confirm_password": "wrongpassword123",
    })
    assert res.status_code == 422
    assert "Passwords do not match" in res.text


# 4. Successful registration stores campus in database
def test_registration_success_stores_campus(client, db):
    email = "multan.student@example.edu"
    res = client.post("/register", data={
        "account_type": "STUDENT",
        "full_name": "Multan Student",
        "identifier": "STU-8803",
        "email": email,
        "program": "BS Computer Science",
        "campus": "Multan Campus",
        "password": "password123",
        "confirm_password": "password123",
    })
    assert res.status_code == 200
    assert "Registration successful" in res.text

    # Verify user record in database
    user = get_user_by_email(db, email)
    assert user is not None
    assert user.campus == "Multan Campus"
    assert user.campus_id is not None
    assert user.student_id == "STU-8803"


# 5. Admin registration requires secret authorization token
def test_admin_registration_requires_secret(client):
    res = client.post("/api/auth/register", json={
        "account_type": "ADMIN",
        "identifier": "ADMIN-8804",
        "full_name": "Unauthorized Admin",
        "email": "unauth.admin@example.edu",
        "campus": "Township Campus, Lahore (Main Campus)",
        "password": "password123",
        "confirm_password": "password123",
    })
    assert res.status_code == 400
    assert "authorized code" in res.json()["detail"].lower()


# 6. Student complaint inherits campus
def test_student_complaint_inherits_campus(client, db):
    # Register student at Faisalabad Campus
    email = "fsd.student@example.edu"
    client.post("/register", data={
        "account_type": "STUDENT",
        "full_name": "Faisalabad Student",
        "identifier": "STU-8805",
        "email": email,
        "program": "BS Computer Science",
        "campus": "Faisalabad Campus",
        "password": "password123",
        "confirm_password": "password123",
    })
    user = get_user_by_email(db, email)
    assert user is not None
    assert user.campus == "Faisalabad Campus"

    # Submit complaint via student API without specifying campus
    token = _token(client, "STUDENT", "STU-8805")
    res = client.post(
        "/api/student/complaints",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "complaint_title": "Faisalabad Computer Lab Issue",
            "complaint_text": "The computer laboratory in the science block has network issues and disconnected PCs.",
        }
    )
    assert res.status_code == 201
    cid = res.json()["id"]

    # Verify complaint in database has student's campus
    c = svc.get_complaint(db, cid)
    assert c.originating_campus == "Faisalabad Campus"
    assert c.target_campus == "Faisalabad Campus"


# 7. Employee campus-scoped access control (IDOR prevention)
def test_employee_campus_scoped_access(client, db):
    # Create employee at Multan Campus in IT Department
    emp_email = "multan.it@example.edu"
    client.post("/register", data={
        "account_type": "EMPLOYEE",
        "full_name": "Multan IT Officer",
        "identifier": "EMP-8806",
        "email": emp_email,
        "role_designation": "Directorate of IT Officer",
        "department": "IT Department",
        "campus": "Multan Campus",
        "password": "password123",
        "confirm_password": "password123",
    })
    emp = get_user_by_email(db, emp_email)
    assert emp is not None
    assert emp.campus == "Multan Campus"

    # Create complaint targeted to Attock Campus
    from app.schemas.complaint import ComplaintCreate
    attock_cmp = svc.create_complaint(
        db,
        ComplaintCreate(
            student_name="Attock Student",
            student_id="STU-8807",
            email="attock8807@example.edu",
            complaint_title="Attock IT Wi-Fi Failure",
            complaint_text="The campus Wi-Fi at Attock campus is completely down and students cannot access portal.",
            originating_campus="Attock Campus",
            target_campus="Attock Campus",
        )
    )

    # Multan employee must not see Attock complaint in their assigned list
    emp_complaints = svc.get_employee_complaints(db, emp)
    assert attock_cmp.id not in [c.id for c in emp_complaints]

    # Multan employee attempting to view Attock complaint detail directly -> 403 Forbidden
    with pytest.raises(Exception) as excinfo:
        svc.get_employee_complaint(db, attock_cmp.id, emp)
    assert "403" in str(excinfo.value) or "different university campus" in str(excinfo.value)


# 8. Admin campus filtering
def test_admin_campus_filtering(client):
    token = _token(client, "ADMIN", "ADMIN-001", "adminpassword")
    client.cookies.set("complaint_session", token)

    # Filter complaints by campus
    res = client.get("/admin/dashboard?campus=Multan+Campus")
    assert res.status_code == 200

    # Filter users by campus
    res_users = client.get("/admin/users?campus=Multan+Campus")
    assert res_users.status_code == 200
    assert "Multan" in res_users.text

    # Filter departments by campus
    res_depts = client.get("/admin/departments?campus=Multan+Campus")
    assert res_depts.status_code == 200


# 9. Login Registered Campus Selection Validation
def test_login_registered_campus_validation(client, db):
    # Register a student for Faisalabad Campus
    email = "fsd.user.login@example.edu"
    client.post("/register", data={
        "account_type": "STUDENT",
        "full_name": "Faisalabad Login User",
        "identifier": "STU-9901",
        "email": email,
        "program": "BS Computer Science",
        "campus": "Faisalabad Campus",
        "password": "password123",
        "confirm_password": "password123",
    })

    # A. Empty campus in web login form fails with 422
    res_empty = client.post("/login", data={
        "account_type": "STUDENT",
        "identifier": "STU-9901",
        "password": "password123",
        "campus": "",
    }, follow_redirects=False)
    assert res_empty.status_code == 422
    assert "Please select your registered campus" in res_empty.text

    # B. Mismatched campus fails with 400 and exact error message
    res_mismatch = client.post("/login", data={
        "account_type": "STUDENT",
        "identifier": "STU-9901",
        "password": "password123",
        "campus": "Multan Campus",  # Wrong campus!
    }, follow_redirects=False)
    assert res_mismatch.status_code == 400
    assert "The selected campus does not match your registered campus." in res_mismatch.text

    # C. Correct campus succeeds with redirect (303) to student dashboard
    res_success = client.post("/login", data={
        "account_type": "STUDENT",
        "identifier": "STU-9901",
        "password": "password123",
        "campus": "Faisalabad Campus",
    }, follow_redirects=False)
    assert res_success.status_code == 303
    assert res_success.headers["location"] == "/student/dashboard"

    # D. Selected campus does not override the database campus
    user = get_user_by_email(db, email)
    assert user.campus == "Faisalabad Campus"


# 10. User Management Campus Isolation and Category Tabs
def test_user_management_campus_isolation_and_tabs(client):
    # Multan Admin login
    res_login = client.post("/login", data={
        "account_type": "ADMIN",
        "identifier": "admin.multan@ue.edu.pk",
        "password": "adminpassword",
        "campus": "Multan Campus",
    }, follow_redirects=False)
    assert res_login.status_code == 303
    token = res_login.cookies["complaint_session"]
    client.cookies.set("complaint_session", token)

    # User Management page
    res_page = client.get("/admin/users")
    assert res_page.status_code == 200
    html = res_page.text

    # Displays assigned campus as read-only text in badge and filter
    assert "Multan Campus" in html
    assert "User Management" in html

    # Shows category tabs: Students, Employees, Admins
    assert "Students" in html
    assert "Employees" in html
    assert "Admins" in html

    # Multan student present, other campus users excluded
    assert "BSF24005343" in html
    assert "STU-1024" not in html

    # Tampering with campus query parameter is rejected server-side
    res_tampered = client.get("/admin/users?campus=Township+Campus%2C+Lahore+(Main+Campus)")
    assert res_tampered.status_code == 200
    assert "Multan Campus" in res_tampered.text
    assert "STU-1024" not in res_tampered.text  # Township student NOT leaked

    # Employees tab displays employee details
    res_emp = client.get("/admin/users?tab=employees")
    assert res_emp.status_code == 200
    assert "Dr. Tariq Mahmood" in res_emp.text
    assert "EMP240011" in res_emp.text

    # Admins tab displays admin details
    res_adm = client.get("/admin/users?tab=admins")
    assert res_adm.status_code == 200
    assert "ADMIN-MLT-001" in res_adm.text
    assert "Multan Administrator" in res_adm.text

