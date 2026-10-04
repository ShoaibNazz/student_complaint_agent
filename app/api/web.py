"""Server-rendered web pages for Student, Employee, Professor, and Admin portals."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR, get_settings
from app.core.exceptions import ComplaintValidationError
from app.core.security import (authenticate_user, create_access_token, decode_access_token,
                               get_current_user_optional, verify_same_origin)
from app.database.database import get_db
from app.models.complaint import Complaint
from app.models.enums import ComplaintStatus, Priority, UserRole
from app.models.user import User
from app.schemas.complaint import AssignmentUpdate, ComplaintCreate, ComplaintUpdate, ResponseUpdate, StatusUpdate
from app.services import complaint_service as svc
from app.services.category_service import get_catalog
from app.services.routing_service import get_routing_service

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(BASE_DIR) / "app" / "templates"))
templates.env.filters["dt"] = lambda v: v.strftime("%Y-%m-%d %H:%M") if v else ""


def _admin_ctx() -> dict:
    return {
        "categories": get_catalog(),
        "departments": get_routing_service().department_names,
        "priorities": [p.value for p in Priority],
        "statuses": [s.value for s in ComplaintStatus],
    }


def _pydantic_messages(exc: ValidationError) -> list[str]:
    return [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]


def _get_web_user(request: Request, db: Session) -> Optional[User]:
    token = request.cookies.get("complaint_session")
    if token:
        payload = decode_access_token(token)
        if payload and "sub" in payload:
            user = db.get(User, int(payload["sub"]))
            if user and user.is_active:
                return user
    return get_current_user_optional(request, None, None, db)


def _require_web_role(request: Request, db: Session, expected_role: str) -> tuple[Optional[User], Optional[Response]]:
    user = _get_web_user(request, db)
    if not user:
        # Dev fallback for admin if ADMIN_PASSWORD is empty
        if expected_role == UserRole.ADMIN.value and not get_settings().admin_password:
            admin_user = db.query(User).filter(User.role == UserRole.ADMIN.value).first()
            if admin_user:
                return admin_user, None
        return None, RedirectResponse(f"/login?next={request.url.path}", status_code=303)

    if user.role != expected_role:
        if user.role == UserRole.STUDENT.value:
            return None, RedirectResponse("/student/dashboard", status_code=303)
        elif user.role == UserRole.EMPLOYEE.value:
            return None, RedirectResponse("/employee/dashboard", status_code=303)
        elif user.role == UserRole.PROFESSOR.value:
            return None, RedirectResponse("/professor/dashboard", status_code=303)
        elif user.role == UserRole.ADMIN.value:
            return None, RedirectResponse("/admin/dashboard", status_code=303)

    return user, None


# ---------------- Global Entry & Authentication ----------------
@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    user = _get_web_user(request, db)
    if user:
        if user.role == UserRole.STUDENT.value:
            return RedirectResponse("/student/dashboard", status_code=303)
        elif user.role == UserRole.EMPLOYEE.value:
            return RedirectResponse("/employee/dashboard", status_code=303)
        elif user.role == UserRole.PROFESSOR.value:
            return RedirectResponse("/professor/dashboard", status_code=303)
        elif user.role == UserRole.ADMIN.value:
            return RedirectResponse("/admin/dashboard", status_code=303)
    return RedirectResponse("/login", status_code=303)


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    user = _get_web_user(request, db)
    if user:
        if user.role == UserRole.STUDENT.value:
            return RedirectResponse("/student/dashboard", status_code=303)
        elif user.role == UserRole.EMPLOYEE.value:
            return RedirectResponse("/employee/dashboard", status_code=303)
        elif user.role == UserRole.PROFESSOR.value:
            return RedirectResponse("/professor/dashboard", status_code=303)
        elif user.role == UserRole.ADMIN.value:
            return RedirectResponse("/admin/dashboard", status_code=303)

    return templates.TemplateResponse(request, "login.html", {
        "current_user": None,
        "active_tab": "login",
        "selected_type": "",
        "identifier": "",
        "error": None,
        "success_msg": None,
        "values": {},
    })


@router.get("/register")
def register_page(request: Request, db: Session = Depends(get_db)):
    user = _get_web_user(request, db)
    if user:
        if user.role == UserRole.STUDENT.value:
            return RedirectResponse("/student/dashboard", status_code=303)
        elif user.role == UserRole.EMPLOYEE.value:
            return RedirectResponse("/employee/dashboard", status_code=303)
        elif user.role == UserRole.PROFESSOR.value:
            return RedirectResponse("/professor/dashboard", status_code=303)
        elif user.role == UserRole.ADMIN.value:
            return RedirectResponse("/admin/dashboard", status_code=303)

    return templates.TemplateResponse(request, "login.html", {
        "current_user": None,
        "active_tab": "register",
        "selected_type": "",
        "identifier": "",
        "error": None,
        "success_msg": None,
        "values": {},
    })


@router.post("/login")
def handle_login(
    request: Request,
    account_type: str = Form(""),
    identifier: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    account_type_clean = (account_type or "").strip()
    if not account_type_clean or account_type_clean.lower() in ("select account type", "none"):
        return templates.TemplateResponse(request, "login.html", {
            "current_user": None,
            "active_tab": "login",
            "selected_type": "",
            "identifier": identifier,
            "error": "Please select your account type.",
            "success_msg": None,
            "values": {},
        }, status_code=422)

    if not identifier.strip() or not password:
        return templates.TemplateResponse(request, "login.html", {
            "current_user": None,
            "active_tab": "login",
            "selected_type": account_type_clean.upper(),
            "identifier": identifier,
            "error": "Please enter your ID and password.",
            "success_msg": None,
            "values": {},
        }, status_code=422)

    user = authenticate_user(db, account_type_clean, identifier, password)
    if not user:
        return templates.TemplateResponse(request, "login.html", {
            "current_user": None,
            "active_tab": "login",
            "selected_type": account_type_clean.upper(),
            "identifier": identifier,
            "error": "Incorrect ID or password.",
            "success_msg": None,
            "values": {},
        }, status_code=401)

    # Issue session cookie and redirect to respective dashboard
    token = create_access_token({"sub": str(user.id), "role": user.role})
    target_url = "/student/dashboard"
    if user.role == UserRole.EMPLOYEE.value:
        target_url = "/employee/dashboard"
    elif user.role == UserRole.PROFESSOR.value:
        target_url = "/professor/dashboard"
    elif user.role == UserRole.ADMIN.value:
        target_url = "/admin/dashboard"

    resp = RedirectResponse(target_url, status_code=303)
    resp.set_cookie(
        key="complaint_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,
    )
    return resp


@router.post("/register")
def handle_register(
    request: Request,
    account_type: str = Form(""),
    identifier: str = Form(""),
    full_name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    confirm_password: str = Form(""),
    department: str = Form(""),
    program: str = Form(""),
    admin_code: str = Form(""),
    db: Session = Depends(get_db),
):
    from app.schemas.user import UserRegisterRequest
    from app.services.user_service import register_user

    values = dict(
        account_type=account_type,
        identifier=identifier,
        full_name=full_name,
        email=email,
        department=department,
        program=program,
        admin_code=admin_code,
    )

    account_type_clean = (account_type or "").strip()
    if not account_type_clean or account_type_clean.lower() in ("select account type", "none"):
        return templates.TemplateResponse(request, "login.html", {
            "current_user": None,
            "active_tab": "register",
            "selected_type": "",
            "identifier": identifier,
            "error": "Please select your account type.",
            "success_msg": None,
            "values": values,
        }, status_code=422)

    try:
        req = UserRegisterRequest(
            account_type=account_type_clean,
            identifier=identifier.strip(),
            full_name=full_name.strip(),
            email=email.strip(),
            password=password,
            confirm_password=confirm_password,
            department=department.strip() or None,
            program=program.strip() or None,
            admin_code=admin_code.strip() or None,
        )
        user = register_user(db, req)
    except ValidationError as exc:
        msg = "; ".join(e["msg"] for e in exc.errors())
        return templates.TemplateResponse(request, "login.html", {
            "current_user": None,
            "active_tab": "register",
            "selected_type": account_type_clean.upper(),
            "identifier": identifier,
            "error": msg,
            "success_msg": None,
            "values": values,
        }, status_code=422)
    except ValueError as exc:
        return templates.TemplateResponse(request, "login.html", {
            "current_user": None,
            "active_tab": "register",
            "selected_type": account_type_clean.upper(),
            "identifier": identifier,
            "error": str(exc),
            "success_msg": None,
            "values": values,
        }, status_code=422)

    return templates.TemplateResponse(request, "login.html", {
        "current_user": None,
        "active_tab": "login",
        "selected_type": user.role,
        "identifier": user.identifier,
        "error": None,
        "success_msg": "Registration successful. You can now login.",
        "values": {},
    })


@router.get("/logout")
@router.post("/logout")
def handle_logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(key="complaint_session")
    return resp


# ---------------- Student Portal Pages ----------------
@router.get("/student/dashboard")
def student_dashboard_page(request: Request, db: Session = Depends(get_db)):
    student, redirect = _require_web_role(request, db, UserRole.STUDENT.value)
    if redirect:
        return redirect

    stats = svc.get_student_stats(db, student)
    recent = svc.get_student_complaints(db, student)[:5]
    return templates.TemplateResponse(request, "student_dashboard.html", {
        "current_user": student,
        "student": student,
        "stats": stats,
        "complaints": recent,
    })


@router.get("/student/complaints")
def student_complaints_page(request: Request, db: Session = Depends(get_db)):
    student, redirect = _require_web_role(request, db, UserRole.STUDENT.value)
    if redirect:
        return redirect

    complaints = svc.get_student_complaints(db, student)
    stats = svc.get_student_stats(db, student)
    return templates.TemplateResponse(request, "student_complaints.html", {
        "current_user": student,
        "student": student,
        "complaints": complaints,
        "stats": stats,
    })


@router.get("/student/complaints/new")
def student_complaint_form_page(request: Request, db: Session = Depends(get_db)):
    student, redirect = _require_web_role(request, db, UserRole.STUDENT.value)
    if redirect:
        return redirect

    return templates.TemplateResponse(request, "student_complaint_form.html", {
        "current_user": student,
        "student": student,
        "values": {},
        "errors": [],
        "submitted": None,
    })


@router.post("/student/complaints/new")
def student_complaint_form_submit(
    request: Request,
    complaint_title: str = Form(""),
    subject: str = Form(""),
    complaint_text: str = Form(""),
    db: Session = Depends(get_db),
):
    student, redirect = _require_web_role(request, db, UserRole.STUDENT.value)
    if redirect:
        return redirect

    values = dict(complaint_title=complaint_title, subject=subject, complaint_text=complaint_text)
    # Automatically attach student's identity
    payload_data = dict(
        student_name=student.full_name,
        student_id=student.student_id,
        email=student.email,
        class_or_program=student.program,
        subject=subject,
        complaint_title=complaint_title,
        complaint_text=complaint_text,
    )

    try:
        complaint = svc.create_complaint(db, ComplaintCreate(**payload_data), user_id=student.id)
    except ValidationError as exc:
        errors = _pydantic_messages(exc)
    except ComplaintValidationError as exc:
        errors = exc.errors
    else:
        return templates.TemplateResponse(request, "student_complaint_form.html", {
            "current_user": student,
            "student": student,
            "values": {},
            "errors": [],
            "submitted": complaint.complaint_number,
        })

    return templates.TemplateResponse(request, "student_complaint_form.html", {
        "current_user": student,
        "student": student,
        "values": values,
        "errors": errors,
        "submitted": None,
    }, status_code=422)


@router.get("/student/complaints/{cid}")
def student_complaint_detail_page(cid: int, request: Request, db: Session = Depends(get_db)):
    student, redirect = _require_web_role(request, db, UserRole.STUDENT.value)
    if redirect:
        return redirect

    # IDOR protection: will raise 403 if complaint doesn't belong to student
    complaint = svc.get_student_complaint(db, cid, student)
    timeline = svc.build_student_timeline(complaint)

    return templates.TemplateResponse(request, "student_complaint_detail.html", {
        "current_user": student,
        "student": student,
        "c": complaint,
        "a": complaint.analysis,
        "timeline": timeline,
    })


@router.get("/student/profile")
def student_profile_page(request: Request, db: Session = Depends(get_db)):
    student, redirect = _require_web_role(request, db, UserRole.STUDENT.value)
    if redirect:
        return redirect
    stats = svc.get_student_stats(db, student)
    return templates.TemplateResponse(request, "profile.html", {
        "current_user": student,
        "stats": stats,
    })


# ---------------- Employee Portal Pages ----------------
@router.get("/employee/dashboard")
def employee_dashboard_page(request: Request, db: Session = Depends(get_db)):
    employee, redirect = _require_web_role(request, db, UserRole.EMPLOYEE.value)
    if redirect:
        return redirect

    complaints = svc.get_employee_complaints(db, employee)
    stats = svc.get_employee_stats(db, employee)
    return templates.TemplateResponse(request, "employee_dashboard.html", {
        "current_user": employee,
        "employee": employee,
        "complaints": complaints,
        "stats": stats,
    })


@router.get("/employee/complaints")
def employee_complaints_page(
    request: Request,
    status: str = "",
    priority: str = "",
    q: str = "",
    db: Session = Depends(get_db),
):
    employee, redirect = _require_web_role(request, db, UserRole.EMPLOYEE.value)
    if redirect:
        return redirect

    complaints = svc.get_employee_complaints(db, employee)
    stats = svc.get_employee_stats(db, employee)
    if status:
        complaints = [c for c in complaints if c.status == status]
    if priority:
        complaints = [c for c in complaints if c.analysis and c.analysis.priority == priority]
    if q:
        ql = q.lower()
        complaints = [c for c in complaints if ql in c.title.lower() or ql in c.complaint_text.lower() or ql in c.complaint_number.lower()]

    return templates.TemplateResponse(request, "employee_complaints.html", {
        "current_user": employee,
        "employee": employee,
        "complaints": complaints,
        "stats": stats,
        "f": dict(status=status, priority=priority, q=q),
    })


@router.get("/employee/profile")
def employee_profile_page(request: Request, db: Session = Depends(get_db)):
    employee, redirect = _require_web_role(request, db, UserRole.EMPLOYEE.value)
    if redirect:
        return redirect
    stats = svc.get_employee_stats(db, employee)
    return templates.TemplateResponse(request, "profile.html", {
        "current_user": employee,
        "stats": stats,
    })


@router.get("/employee/complaints/{cid}")
def employee_complaint_detail_page(cid: int, request: Request, db: Session = Depends(get_db)):
    employee, redirect = _require_web_role(request, db, UserRole.EMPLOYEE.value)
    if redirect:
        return redirect

    c = svc.get_complaint(db, cid)
    return templates.TemplateResponse(request, "employee_complaint_detail.html", {
        "current_user": employee,
        "employee": employee,
        "c": c,
        "a": c.analysis,
    })


@router.post("/employee/complaints/{cid}/update")
def employee_complaint_update_submit(
    cid: int,
    request: Request,
    status: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    employee, redirect = _require_web_role(request, db, UserRole.EMPLOYEE.value)
    if redirect:
        return redirect

    c = svc.get_complaint(db, cid)
    if status and status in ("IN_PROGRESS", "WAITING_FOR_STUDENT", "RESOLVED"):
        svc.update_status(db, c, StatusUpdate(status=status, note=note or None), employee.username)
    if note:
        svc.update_complaint(db, c, ComplaintUpdate(internal_notes=note.strip()), employee.username)
    return RedirectResponse(f"/employee/complaints/{cid}", status_code=303)


# ---------------- Professor Portal Pages ----------------
@router.get("/professor/dashboard")
def professor_dashboard_page(request: Request, db: Session = Depends(get_db)):
    professor, redirect = _require_web_role(request, db, UserRole.PROFESSOR.value)
    if redirect:
        return redirect

    complaints = svc.get_professor_complaints(db, professor)
    stats = svc.get_professor_stats(db, professor)
    return templates.TemplateResponse(request, "professor_dashboard.html", {
        "current_user": professor,
        "professor": professor,
        "complaints": complaints,
        "stats": stats,
    })


@router.get("/professor/complaints")
def professor_complaints_page(
    request: Request,
    status: str = "",
    priority: str = "",
    q: str = "",
    db: Session = Depends(get_db),
):
    professor, redirect = _require_web_role(request, db, UserRole.PROFESSOR.value)
    if redirect:
        return redirect

    complaints = svc.get_professor_complaints(db, professor)
    stats = svc.get_professor_stats(db, professor)
    if status:
        complaints = [c for c in complaints if c.status == status]
    if priority:
        complaints = [c for c in complaints if c.analysis and c.analysis.priority == priority]
    if q:
        ql = q.lower()
        complaints = [c for c in complaints if ql in c.title.lower() or ql in c.complaint_text.lower() or ql in c.complaint_number.lower()]

    return templates.TemplateResponse(request, "professor_complaints.html", {
        "current_user": professor,
        "professor": professor,
        "complaints": complaints,
        "stats": stats,
        "f": dict(status=status, priority=priority, q=q),
    })


@router.get("/professor/profile")
def professor_profile_page(request: Request, db: Session = Depends(get_db)):
    professor, redirect = _require_web_role(request, db, UserRole.PROFESSOR.value)
    if redirect:
        return redirect
    stats = svc.get_professor_stats(db, professor)
    return templates.TemplateResponse(request, "profile.html", {
        "current_user": professor,
        "stats": stats,
    })


@router.get("/professor/complaints/{cid}")
def professor_complaint_detail_page(cid: int, request: Request, db: Session = Depends(get_db)):
    professor, redirect = _require_web_role(request, db, UserRole.PROFESSOR.value)
    if redirect:
        return redirect

    c = svc.get_complaint(db, cid)
    return templates.TemplateResponse(request, "professor_complaint_detail.html", {
        "current_user": professor,
        "professor": professor,
        "c": c,
        "a": c.analysis,
    })


@router.post("/professor/complaints/{cid}/update")
def professor_complaint_update_submit(
    cid: int,
    request: Request,
    status: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    professor, redirect = _require_web_role(request, db, UserRole.PROFESSOR.value)
    if redirect:
        return redirect

    c = svc.get_complaint(db, cid)
    if status and status in ("UNDER_REVIEW", "IN_PROGRESS", "WAITING_FOR_STUDENT", "RESOLVED"):
        svc.update_status(db, c, StatusUpdate(status=status, note=note or None), professor.username)
    if note:
        svc.update_complaint(db, c, ComplaintUpdate(internal_notes=note.strip()), professor.username)
    return RedirectResponse(f"/professor/complaints/{cid}", status_code=303)


# ---------------- Administrator Portal Pages ----------------
@router.get("/admin")
@router.get("/admin/dashboard")
def admin_dashboard_page(
    request: Request,
    q: str = "",
    priority: str = "",
    category: str = "",
    department: str = "",
    status: str = "",
    review: str = "",
    db: Session = Depends(get_db),
):
    admin, redirect = _require_web_role(request, db, UserRole.ADMIN.value)
    if redirect:
        return redirect

    errors: list[str] = []
    try:
        filters = svc.ComplaintFilters(
            q=q or None,
            priority=Priority.parse(priority),
            category=category or None,
            department=department or None,
            status=status or None,
            requires_human_review=True if review == "1" else None,
            sort="priority",
            limit=200,
        )
        items, total = svc.list_complaints(db, filters)
    except ComplaintValidationError as exc:
        items, total, errors = [], 0, exc.errors

    return templates.TemplateResponse(request, "dashboard.html", {
        "current_user": admin,
        "admin": admin,
        "stats": svc.get_dashboard_stats(db),
        "complaints": items,
        "total": total,
        "errors": errors,
        "f": dict(q=q, priority=priority, category=category, department=department, status=status, review=review),
        **_admin_ctx(),
    })


@router.get("/admin/complaints")
def admin_complaints_redirect():
    return RedirectResponse("/admin", status_code=303)


@router.get("/admin/users")
def admin_users_page(request: Request, db: Session = Depends(get_db)):
    admin, redirect = _require_web_role(request, db, UserRole.ADMIN.value)
    if redirect:
        return redirect

    users = db.query(User).order_by(User.id).all()
    return templates.TemplateResponse(request, "admin_users.html", {
        "current_user": admin,
        "admin": admin,
        "users": users,
    })


@router.get("/admin/departments")
def admin_departments_page(request: Request, db: Session = Depends(get_db)):
    admin, redirect = _require_web_role(request, db, UserRole.ADMIN.value)
    if redirect:
        return redirect

    dept_names = _admin_ctx()["departments"]
    dept_stats = []
    for d in dept_names:
        c_list = db.query(Complaint).join(Complaint.analysis).filter(Complaint.is_deleted.is_(False), Complaint.analysis.has(assigned_department=d)).all()
        total = len(c_list)
        pending = sum(1 for c in c_list if c.status not in (ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value))
        resolved = sum(1 for c in c_list if c.status in (ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value))
        dept_stats.append({"name": d, "total": total, "pending": pending, "resolved": resolved})

    return templates.TemplateResponse(request, "admin_departments.html", {
        "current_user": admin,
        "admin": admin,
        "dept_stats": dept_stats,
    })


@router.get("/admin/reports")
def admin_reports_page(request: Request, db: Session = Depends(get_db)):
    admin, redirect = _require_web_role(request, db, UserRole.ADMIN.value)
    if redirect:
        return redirect

    stats = svc.get_dashboard_stats(db)
    return templates.TemplateResponse(request, "admin_reports.html", {
        "current_user": admin,
        "admin": admin,
        "stats": stats,
    })


@router.get("/admin/settings")
def admin_settings_page(request: Request, db: Session = Depends(get_db)):
    admin, redirect = _require_web_role(request, db, UserRole.ADMIN.value)
    if redirect:
        return redirect

    return templates.TemplateResponse(request, "admin_settings.html", {
        "current_user": admin,
        "admin": admin,
        "settings": get_settings(),
    })


def _admin_detail(request, db, cid, admin, errors=None, saved=False, code=200):
    complaint = svc.get_complaint(db, cid)
    return templates.TemplateResponse(request, "complaint_detail.html", {
        "current_user": admin,
        "c": complaint,
        "a": complaint.analysis,
        "errors": errors or [],
        "saved": saved,
        "admin": admin,
        "duplicate": db.get(type(complaint), complaint.duplicate_of_id) if complaint.duplicate_of_id else None,
        "threshold": get_settings().low_confidence_threshold,
        **_admin_ctx(),
    }, status_code=code)


@router.get("/admin/complaints/{cid}")
def admin_detail_page(cid: int, request: Request, saved: int = 0, db: Session = Depends(get_db)):
    admin, redirect = _require_web_role(request, db, UserRole.ADMIN.value)
    if redirect:
        return redirect
    return _admin_detail(request, db, cid, admin, saved=bool(saved))


@router.post("/admin/complaints/{cid}", dependencies=[Depends(verify_same_origin)])
def admin_save_complaint(
    cid: int,
    request: Request,
    category: str = Form(""),
    subcategory: str = Form(""),
    department: str = Form(""),
    priority: str = Form(""),
    status: str = Form(""),
    draft_response: str = Form(""),
    approved: str = Form(""),
    internal_notes: str = Form(""),
    db: Session = Depends(get_db),
):
    admin, redirect = _require_web_role(request, db, UserRole.ADMIN.value)
    if redirect:
        return redirect

    c = svc.get_complaint(db, cid)
    try:
        if c.analysis:
            svc.update_assignment(
                db, c,
                AssignmentUpdate(
                    category=category or None,
                    subcategory=subcategory or None,
                    department=department or None,
                    priority=Priority.parse(priority),
                ),
                admin.username,
            )
            if draft_response.strip():
                svc.update_response(
                    db, c,
                    ResponseUpdate(draft_response=draft_response, approved=bool(approved)),
                    admin.username,
                )
        if status:
            svc.update_status(db, c, StatusUpdate(status=status), admin.username)
        svc.update_complaint(db, c, ComplaintUpdate(internal_notes=internal_notes.strip() or None), admin.username)
    except ValidationError as exc:
        return _admin_detail(request, db, cid, admin, errors=_pydantic_messages(exc), code=422)
    except ComplaintValidationError as exc:
        return _admin_detail(request, db, cid, admin, errors=exc.errors, code=422)

    return RedirectResponse(f"/admin/complaints/{cid}?saved=1", status_code=303)


@router.post("/admin/complaints/{cid}/analyze", dependencies=[Depends(verify_same_origin)])
def admin_retry_analysis(cid: int, request: Request, db: Session = Depends(get_db)):
    admin, redirect = _require_web_role(request, db, UserRole.ADMIN.value)
    if redirect:
        return redirect
    svc.reanalyze(db, svc.get_complaint(db, cid), admin.username)
    return RedirectResponse(f"/admin/complaints/{cid}?saved=1", status_code=303)


# ---------------- Legacy / Public Fallback Form ----------------
@router.get("/submit")
def legacy_form(request: Request, db: Session = Depends(get_db)):
    user = _get_web_user(request, db)
    if user and user.role == UserRole.STUDENT.value:
        return RedirectResponse("/student/complaints/new", status_code=303)
    return templates.TemplateResponse(request, "complaint_form.html", {
        "current_user": user,
        "settings": get_settings(),
        "values": {},
        "errors": [],
    })


@router.post("/submit")
def legacy_submit(
    request: Request,
    student_name: str = Form(""),
    student_id: str = Form(""),
    email: str = Form(""),
    class_or_program: str = Form(""),
    subject: str = Form(""),
    complaint_title: str = Form(""),
    complaint_text: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _get_web_user(request, db)
    values = dict(
        student_name=student_name,
        student_id=student_id,
        email=email,
        class_or_program=class_or_program,
        subject=subject,
        complaint_title=complaint_title,
        complaint_text=complaint_text,
    )
    user_id = user.id if user else None
    try:
        complaint = svc.create_complaint(db, ComplaintCreate(**values), user_id=user_id)
    except ValidationError as exc:
        errors = _pydantic_messages(exc)
    except ComplaintValidationError as exc:
        errors = exc.errors
    else:
        return templates.TemplateResponse(request, "complaint_form.html", {
            "current_user": user,
            "settings": get_settings(),
            "values": {},
            "errors": [],
            "submitted": complaint.complaint_number,
        })

    return templates.TemplateResponse(request, "complaint_form.html", {
        "current_user": user,
        "settings": get_settings(),
        "values": values,
        "errors": errors,
    }, status_code=422)
