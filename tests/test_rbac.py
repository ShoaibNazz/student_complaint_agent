"""Tests for Role-Based Access Control (RBAC), multi-role authentication,
student complaint ownership, and dashboard workflows.
"""
import pytest
from app.models.enums import ComplaintStatus, UserRole
from app.models.user import User
from app.services import complaint_service as svc


def _login(client, account_type: str, identifier: str, password: str = "password123"):
    res = client.post("/api/auth/login", json={
        "account_type": account_type,
        "identifier": identifier,
        "password": password,
    })
    return res


def _token(client, account_type: str, identifier: str, password: str = "password123"):
    res = _login(client, account_type, identifier, password)
    assert res.status_code == 200, f"Login failed for {account_type} {identifier}: {res.text}"
    return res.json()["access_token"]


def _auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


# 1. Student login
def test_student_login_success(client):
    res = _login(client, "STUDENT", "STU-1024", "password123")
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "STUDENT"
    assert data["user"]["student_id"] == "STU-1024"


# 2. Employee login
def test_employee_login_success(client):
    res = _login(client, "EMPLOYEE", "EMP-1024", "password123")
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "EMPLOYEE"
    assert data["user"]["employee_id"] == "EMP-1024"


# 3. Professor login
def test_professor_login_success(client):
    res = _login(client, "PROFESSOR", "PROF-1024", "password123")
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "PROFESSOR"
    assert data["user"]["professor_id"] == "PROF-1024"


# 4. Admin login
def test_admin_login_success(client):
    res = _login(client, "ADMIN", "ADMIN-001", "adminpassword")
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "ADMIN"


# 5. Invalid login: wrong password, role mismatch, non-existent user
def test_invalid_login_rejected(client):
    # Wrong password
    assert _login(client, "STUDENT", "STU-1024", "wrongpass").status_code == 401

    # Student trying to log in as Employee
    assert _login(client, "EMPLOYEE", "STU-1024", "password123").status_code == 401

    # Student trying to log in as Admin
    assert _login(client, "ADMIN", "STU-1024", "password123").status_code == 401

    # Non-existent user
    assert _login(client, "STUDENT", "NON-EXISTENT", "password123").status_code == 401


# 6. Student accessing admin route -> 403 Forbidden
def test_student_accessing_admin_route_forbidden(client):
    token = _token(client, "STUDENT", "STU-1024")
    # API route
    res = client.get("/api/admin/dashboard", headers=_auth_header(token))
    assert res.status_code == 403

    res2 = client.get("/api/admin/complaints", headers=_auth_header(token))
    assert res2.status_code == 403

    # Web route redirects away to student dashboard
    client.cookies.set("complaint_session", token)
    web_res = client.get("/admin", follow_redirects=False)
    assert web_res.status_code == 303
    assert web_res.headers["location"] == "/student/dashboard"


# 7. Employee accessing admin route -> 403 Forbidden
def test_employee_accessing_admin_route_forbidden(client):
    token = _token(client, "EMPLOYEE", "EMP-1024")
    res = client.get("/api/admin/dashboard", headers=_auth_header(token))
    assert res.status_code == 403

    client.cookies.set("complaint_session", token)
    web_res = client.get("/admin/dashboard", follow_redirects=False)
    assert web_res.status_code == 303
    assert web_res.headers["location"] == "/employee/dashboard"


# 8. Professor accessing admin route -> 403 Forbidden
def test_professor_accessing_admin_route_forbidden(client):
    token = _token(client, "PROFESSOR", "PROF-1024")
    res = client.get("/api/admin/dashboard", headers=_auth_header(token))
    assert res.status_code == 403

    client.cookies.set("complaint_session", token)
    web_res = client.get("/admin", follow_redirects=False)
    assert web_res.status_code == 303
    assert web_res.headers["location"] == "/professor/dashboard"


# 9. Student can submit complaint (identity auto-attached)
def test_student_can_submit_complaint(client):
    token = _token(client, "STUDENT", "STU-1024")
    payload = {
        "complaint_title": "Library air conditioner leaking",
        "subject": "Library Facilities",
        "complaint_text": "The air conditioner in the third floor quiet study hall has been leaking water on desks.",
    }
    res = client.post("/api/student/complaints", json=payload, headers=_auth_header(token))
    assert res.status_code == 201
    body = res.json()
    assert body["complaint_number"].startswith("CMP-")
    assert body["status"] == "NEW"


# 10. Student can see own complaints
def test_student_can_see_own_complaints(client):
    token = _token(client, "STUDENT", "STU-1024")
    # Submit a complaint
    client.post("/api/student/complaints", json={
        "complaint_title": "Exam schedule clash",
        "subject": "Examination",
        "complaint_text": "Two of my scheduled final examinations are on the exact same date and time slot.",
    }, headers=_auth_header(token))

    res = client.get("/api/student/complaints", headers=_auth_header(token))
    assert res.status_code == 200
    complaints = res.json()
    assert len(complaints) >= 1
    assert any(c["title"] == "Exam schedule clash" for c in complaints)


# 11. Student cannot see another student's complaint (IDOR prevention)
def test_student_cannot_see_other_student_complaint(client):
    token_ali = _token(client, "STUDENT", "STU-1024")
    token_sara = _token(client, "STUDENT", "STU-2001")

    # Sara submits a complaint
    res_sara = client.post("/api/student/complaints", json={
        "complaint_title": "Sara private financial issue",
        "subject": "Finance",
        "complaint_text": "Private financial voucher query regarding late payment penalty refund.",
    }, headers=_auth_header(token_sara))
    cid = res_sara.json()["id"]

    # Sara can view her complaint
    assert client.get(f"/api/student/complaints/{cid}", headers=_auth_header(token_sara)).status_code == 200

    # Ali attempts to access Sara's complaint by ID -> MUST return 403 Forbidden!
    res_ali = client.get(f"/api/student/complaints/{cid}", headers=_auth_header(token_ali))
    assert res_ali.status_code == 403


# 12. Admin can see all complaints
def test_admin_can_see_all_complaints(client):
    token_ali = _token(client, "STUDENT", "STU-1024")
    token_sara = _token(client, "STUDENT", "STU-2001")
    token_admin = _token(client, "ADMIN", "ADMIN-001", "adminpassword")

    client.post("/api/student/complaints", json={
        "complaint_title": "Ali test issue for admin",
        "subject": "CS",
        "complaint_text": "Detailed complaint text from student Ali regarding labs.",
    }, headers=_auth_header(token_ali))

    client.post("/api/student/complaints", json={
        "complaint_title": "Sara test issue for admin",
        "subject": "BBA",
        "complaint_text": "Detailed complaint text from student Sara regarding classroom audio.",
    }, headers=_auth_header(token_sara))

    res = client.get("/api/admin/complaints", headers=_auth_header(token_admin))
    assert res.status_code == 200
    all_titles = [c["title"] for c in res.json()["items"]]
    assert "Ali test issue for admin" in all_titles
    assert "Sara test issue for admin" in all_titles


# 13. Admin can change complaint status
def test_admin_can_change_complaint_status(client):
    token_ali = _token(client, "STUDENT", "STU-1024")
    token_admin = _token(client, "ADMIN", "ADMIN-001", "adminpassword")

    res = client.post("/api/student/complaints", json={
        "complaint_title": "Wi-Fi down in hostel",
        "subject": "IT",
        "complaint_text": "The hostel Wi-Fi connection has been non-functional since yesterday evening.",
    }, headers=_auth_header(token_ali))
    cid = res.json()["id"]

    # Admin changes status to UNDER_REVIEW
    r1 = client.put(f"/api/admin/complaints/{cid}/status", json={"status": "UNDER_REVIEW", "note": "Assigned to network engineer"}, headers=_auth_header(token_admin))
    assert r1.status_code == 200
    assert r1.json()["status"] == "UNDER_REVIEW"

    # Admin changes status to RESOLVED
    r2 = client.put(f"/api/admin/complaints/{cid}/status", json={"status": "RESOLVED", "note": "Router replaced"}, headers=_auth_header(token_admin))
    assert r2.status_code == 200
    assert r2.json()["status"] == "RESOLVED"


# 14. Admin can assign department
def test_admin_can_assign_department(client):
    token_ali = _token(client, "STUDENT", "STU-1024")
    token_admin = _token(client, "ADMIN", "ADMIN-001", "adminpassword")

    res = client.post("/api/student/complaints", json={
        "complaint_title": "Broken window in lab",
        "subject": "Facilities",
        "complaint_text": "There is a broken glass window in the ground floor computer science lab.",
    }, headers=_auth_header(token_ali))
    cid = res.json()["id"]

    update_res = client.put(
        f"/api/admin/complaints/{cid}/assignment",
        json={"department": "Administration / Maintenance", "priority": "HIGH"},
        headers=_auth_header(token_admin)
    )
    assert update_res.status_code == 200


# 15. Complaint statistics are correct and isolated per student
def test_complaint_statistics_isolated_per_student(client):
    token_ali = _token(client, "STUDENT", "STU-1024")
    token_sara = _token(client, "STUDENT", "STU-2001")

    # Get initial counts
    init_ali = client.get("/api/student/dashboard", headers=_auth_header(token_ali)).json()["stats"]["total"]
    init_sara = client.get("/api/student/dashboard", headers=_auth_header(token_sara)).json()["stats"]["total"]

    # Ali creates 2 complaints
    for i in range(2):
        client.post("/api/student/complaints", json={
            "complaint_title": f"Ali isolated test {i}",
            "subject": "General",
            "complaint_text": f"Detailed description for complaint number {i} regarding facilities.",
        }, headers=_auth_header(token_ali))

    # Sara creates 1 complaint
    client.post("/api/student/complaints", json={
        "complaint_title": "Sara isolated test",
        "subject": "Finance",
        "complaint_text": "Detailed description for Sara complaint regarding fee deadline extension.",
    }, headers=_auth_header(token_sara))

    after_ali = client.get("/api/student/dashboard", headers=_auth_header(token_ali)).json()["stats"]["total"]
    after_sara = client.get("/api/student/dashboard", headers=_auth_header(token_sara)).json()["stats"]["total"]

    assert after_ali == init_ali + 2
    assert after_sara == init_sara + 1


# 16. Complaint status updates are reflected on student dashboard and timeline
def test_status_update_reflected_on_student_dashboard_and_timeline(client):
    token_ali = _token(client, "STUDENT", "STU-1024")
    token_admin = _token(client, "ADMIN", "ADMIN-001", "adminpassword")

    res = client.post("/api/student/complaints", json={
        "complaint_title": "Water dispenser not cooling",
        "subject": "Hostel",
        "complaint_text": "The drinking water dispenser on second floor is not cooling properly.",
    }, headers=_auth_header(token_ali))
    cid = res.json()["id"]

    # Initially NEW
    student_view = client.get(f"/api/student/complaints/{cid}", headers=_auth_header(token_ali)).json()
    assert student_view["status"] == "NEW"

    # Admin changes status to IN_PROGRESS
    client.put(f"/api/admin/complaints/{cid}/status", json={"status": "IN_PROGRESS"}, headers=_auth_header(token_admin))

    # Student sees IN_PROGRESS and active timeline step
    updated_view = client.get(f"/api/student/complaints/{cid}", headers=_auth_header(token_ali)).json()
    assert updated_view["status"] == "IN_PROGRESS"
    timeline_steps = {t["status_key"]: t for t in updated_view["timeline"]}
    assert timeline_steps["IN_PROGRESS"]["is_current"] is True


# 17. AI analysis still works and populates categories, summary, department
def test_ai_analysis_populates_category_and_department(client, db):
    token_ali = _token(client, "STUDENT", "STU-1024")
    res = client.post("/api/student/complaints", json={
        "complaint_title": "Semester fees payment receipt not generated",
        "subject": "Accounts",
        "complaint_text": "I submitted the challan at the bank branch but the student portal still has not updated my receipt.",
    }, headers=_auth_header(token_ali))
    cid = res.json()["id"]

    detail = client.get(f"/api/student/complaints/{cid}", headers=_auth_header(token_ali)).json()
    assert detail["category"] is not None
    assert detail["assigned_department"] is not None
    assert detail["summary"] is not None


# 18. Student cannot see sensitive internal admin notes
def test_student_cannot_see_internal_admin_notes(client):
    token_ali = _token(client, "STUDENT", "STU-1024")
    token_admin = _token(client, "ADMIN", "ADMIN-001", "adminpassword")

    res = client.post("/api/student/complaints", json={
        "complaint_title": "Classroom projector flickering",
        "subject": "IT",
        "complaint_text": "The classroom projector in Hall 4 flickers constantly during lectures.",
    }, headers=_auth_header(token_ali))
    cid = res.json()["id"]

    # Admin adds sensitive internal notes
    client.put(f"/api/admin/complaints/{cid}", json={
        "internal_notes": "CONFIDENTIAL_ADMIN_NOTE: Order replacement bulb from vendor X next Monday.",
    }, headers=_auth_header(token_admin))

    # Admin sees internal notes
    admin_view = client.get(f"/api/admin/complaints/{cid}", headers=_auth_header(token_admin)).json()
    assert "CONFIDENTIAL_ADMIN_NOTE" in admin_view["internal_notes"]

    # Student does NOT receive internal notes in student detail schema
    student_view = client.get(f"/api/student/complaints/{cid}", headers=_auth_header(token_ali)).json()
    assert "internal_notes" not in student_view
    assert "CONFIDENTIAL_ADMIN_NOTE" not in str(student_view)


# 19. Section 30 Standard Test Accounts Login
def test_all_four_roles_login(client):
    # Student STU-1001
    res = _login(client, "STUDENT", "STU-1001", "password123")
    assert res.status_code == 200
    assert res.json()["user"]["role"] == "STUDENT"

    # Employee EMP-1001
    res = _login(client, "EMPLOYEE", "EMP-1001", "password123")
    assert res.status_code == 200
    assert res.json()["user"]["role"] == "EMPLOYEE"

    # Professor PROF-1001
    res = _login(client, "PROFESSOR", "PROF-1001", "password123")
    assert res.status_code == 200
    assert res.json()["user"]["role"] == "PROFESSOR"

    # Admin ADMIN-1001
    res = _login(client, "ADMIN", "ADMIN-1001", "adminpassword")
    assert res.status_code == 200
    assert res.json()["user"]["role"] == "ADMIN"


# 20. Student Registration Flow
def test_student_registration_success(client):
    payload = {
        "account_type": "STUDENT",
        "identifier": "STU-9901",
        "full_name": "Hamza Tariq",
        "email": "hamza.tariq@example.edu",
        "password": "securepassword123",
        "confirm_password": "securepassword123",
        "program": "BS Data Science",
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["message"] == "Registration successful. You can now login."
    assert data["user"]["student_id"] == "STU-9901"

    # Can now login
    login_res = _login(client, "STUDENT", "STU-9901", "securepassword123")
    assert login_res.status_code == 200


# 21. Registration Rejections: Already registered, Password mismatch, Missing Account Type
def test_registration_validation_errors(client):
    # Already registered ID
    res = client.post("/api/auth/register", json={
        "account_type": "STUDENT",
        "identifier": "STU-1001",
        "full_name": "Another Person",
        "email": "someone.else@example.edu",
        "password": "password123",
        "confirm_password": "password123",
    })
    assert res.status_code == 400
    assert "already registered" in res.json()["detail"].lower()

    # Password mismatch
    res = client.post("/api/auth/register", json={
        "account_type": "STUDENT",
        "identifier": "STU-9902",
        "full_name": "Test User",
        "email": "test9902@example.edu",
        "password": "password123",
        "confirm_password": "mismatchpassword",
    })
    assert res.status_code == 400
    assert "passwords do not match" in res.json()["detail"].lower()

    # Empty account type
    res = client.post("/api/auth/register", json={
        "account_type": "",
        "identifier": "STU-9903",
        "full_name": "Test User",
        "email": "test9903@example.edu",
        "password": "password123",
        "confirm_password": "password123",
    })
    assert res.status_code == 400
    assert "select your account type" in res.json()["detail"].lower()


# 22. Official Directory Anti-Impersonation Protection
def test_anti_impersonation_protection(client):
    # STU-1002 is in official roster for Ayesha Malik (ayesha1002@example.edu)
    # Impersonator tries to register with attacker's email
    res = client.post("/api/auth/register", json={
        "account_type": "STUDENT",
        "identifier": "STU-1002",
        "full_name": "Malicious Attacker",
        "email": "attacker@evil.com",
        "password": "password123",
        "confirm_password": "password123",
    })
    assert res.status_code == 400
    assert "official university records" in res.json()["detail"].lower()

    # Official student registers with matching email
    res2 = client.post("/api/auth/register", json={
        "account_type": "STUDENT",
        "identifier": "STU-1002",
        "full_name": "Ayesha Malik",
        "email": "ayesha1002@example.edu",
        "password": "mypassword123",
        "confirm_password": "mypassword123",
    })
    assert res2.status_code == 201


# 23. Admin Registration Protection: Code required
def test_admin_registration_protection(client):
    # Attempting to register admin without code -> rejected
    res = client.post("/api/auth/register", json={
        "account_type": "ADMIN",
        "identifier": "ADMIN-9999",
        "full_name": "Attacker Admin",
        "email": "attacker.admin@example.edu",
        "password": "adminpassword123",
        "confirm_password": "adminpassword123",
    })
    assert res.status_code == 400
    assert "authorized code" in res.json()["detail"].lower()

    # Attempting with wrong code -> rejected
    res_wrong = client.post("/api/auth/register", json={
        "account_type": "ADMIN",
        "identifier": "ADMIN-9999",
        "full_name": "Attacker Admin",
        "email": "attacker.admin@example.edu",
        "password": "adminpassword123",
        "confirm_password": "adminpassword123",
        "admin_code": "WRONG-KEY",
    })
    assert res_wrong.status_code == 400
    assert "authorized code" in res_wrong.json()["detail"].lower()

    # Registering with valid admin authorization key -> allowed
    res_ok = client.post("/api/auth/register", json={
        "account_type": "ADMIN",
        "identifier": "ADMIN-9999",
        "full_name": "Legitimate Admin",
        "email": "legit.admin@example.edu",
        "password": "adminpassword123",
        "confirm_password": "adminpassword123",
        "admin_code": "ADMIN-SECRET-2026",
    })
    assert res_ok.status_code == 201
    assert res_ok.json()["user"]["role"] == "ADMIN"


# 24. Employee & Professor Registration
def test_employee_and_professor_registration(client):
    # Employee
    res_emp = client.post("/api/auth/register", json={
        "account_type": "EMPLOYEE",
        "identifier": "EMP-9901",
        "full_name": "Staff Member",
        "email": "staff9901@example.edu",
        "password": "password123",
        "confirm_password": "password123",
        "department": "Transport",
    })
    assert res_emp.status_code == 201

    # Professor
    res_prof = client.post("/api/auth/register", json={
        "account_type": "PROFESSOR",
        "identifier": "PROF-9901",
        "full_name": "Faculty Member",
        "email": "faculty9901@example.edu",
        "password": "password123",
        "confirm_password": "password123",
        "department": "Physics",
    })
    assert res_prof.status_code == 201


# 25. Web Pages and Navigation Links for All Roles
def test_web_routes_and_navigation(client):
    token_stu = _token(client, "STUDENT", "STU-1001")
    token_emp = _token(client, "EMPLOYEE", "EMP-1001")
    token_prof = _token(client, "PROFESSOR", "PROF-1001")
    token_admin = _token(client, "ADMIN", "ADMIN-1001", "adminpassword")

    # Public web pages
    assert client.get("/login").status_code == 200
    assert client.get("/register").status_code == 200

    # Student portal pages
    client.cookies.set("complaint_session", token_stu)
    assert client.get("/student/dashboard").status_code == 200
    assert client.get("/student/complaints").status_code == 200
    assert client.get("/student/complaints/new").status_code == 200
    assert client.get("/student/profile").status_code == 200

    # Employee portal pages
    client.cookies.set("complaint_session", token_emp)
    assert client.get("/employee/dashboard").status_code == 200
    assert client.get("/employee/complaints").status_code == 200
    assert client.get("/employee/profile").status_code == 200

    # Professor portal pages
    client.cookies.set("complaint_session", token_prof)
    assert client.get("/professor/dashboard").status_code == 200
    assert client.get("/professor/complaints").status_code == 200
    assert client.get("/professor/profile").status_code == 200

    # Admin portal pages
    client.cookies.set("complaint_session", token_admin)
    assert client.get("/admin/dashboard").status_code == 200
    assert client.get("/admin/complaints").status_code == 200
    assert client.get("/admin/users").status_code == 200
    assert client.get("/admin/departments").status_code == 200
    assert client.get("/admin/reports").status_code == 200
    assert client.get("/admin/settings").status_code == 200


# 26. Logout & Session Persistence
def test_logout_and_session(client):
    token = _token(client, "STUDENT", "STU-1001")
    client.cookies.set("complaint_session", token)

    # Session valid
    res_dash = client.get("/student/dashboard")
    assert res_dash.status_code == 200

    # Logout
    res_logout = client.get("/logout", follow_redirects=False)
    assert res_logout.status_code == 303
    assert res_logout.headers["location"] == "/login"

    # API docs accessible
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200

