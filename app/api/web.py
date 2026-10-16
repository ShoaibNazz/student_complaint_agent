"""Server-rendered web pages for Student, Employee, Professor, and Admin portals."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import or_
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


def _auth_ctx(**overrides) -> dict:
    from app.services.complaint_service import get_campus_names
    from app.services.user_service import DEGREE_PROGRAMS, EMPLOYEE_ROLES
    ctx = {
        "current_user": None,
        "active_tab": "login",
        "selected_type": "",
        "identifier": "",
        "selected_campus": "",
        "error": None,
        "success_msg": None,
        "values": {},
        "campuses": get_campus_names(),
        "departments": get_routing_service().department_names,
        "degree_programs": DEGREE_PROGRAMS,
        "employee_roles": EMPLOYEE_ROLES,
    }
    ctx.update(overrides)
    return ctx


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

    return templates.TemplateResponse(request, "login.html", _auth_ctx(active_tab="login"))


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

    return templates.TemplateResponse(request, "login.html", _auth_ctx(active_tab="register"))


@router.post("/login")
def handle_login(
    request: Request,
    account_type: str = Form(""),
    identifier: str = Form(""),
    password: str = Form(""),
    campus: str = Form(""),
    db: Session = Depends(get_db),
):
    account_type_clean = (account_type or "").strip()
    campus_clean = (campus or "").strip()

    if not account_type_clean or account_type_clean.lower() in ("select account type", "none"):
        return templates.TemplateResponse(
            request,
            "login.html",
            _auth_ctx(
                active_tab="login",
                selected_type="",
                identifier=identifier,
                selected_campus=campus_clean,
                error="Please select your account type.",
            ),
            status_code=422,
        )

    if not campus_clean or campus_clean.lower() in ("select your registered campus", "select campus", "none"):
        return templates.TemplateResponse(
            request,
            "login.html",
            _auth_ctx(
                active_tab="login",
                selected_type=account_type_clean.upper(),
                identifier=identifier,
                selected_campus="",
                error="Please select your registered campus.",
            ),
            status_code=422,
        )

    if not identifier.strip() or not password:
        return templates.TemplateResponse(
            request,
            "login.html",
            _auth_ctx(
                active_tab="login",
                selected_type=account_type_clean.upper(),
                identifier=identifier,
                selected_campus=campus_clean,
                error="Please enter your ID and password.",
            ),
            status_code=422,
        )

    user = authenticate_user(db, account_type_clean, identifier, password)
    if not user:
        return templates.TemplateResponse(
            request,
            "login.html",
            _auth_ctx(
                active_tab="login",
                selected_type=account_type_clean.upper(),
                identifier=identifier,
                selected_campus=campus_clean,
                error="Incorrect ID or password.",
            ),
            status_code=401,
        )

    # Validate registered campus against user record
    user_campus = (user.campus or "").strip()
    if user_campus:
        if campus_clean.lower() != user_campus.lower():
            return templates.TemplateResponse(
                request,
                "login.html",
                _auth_ctx(
                    active_tab="login",
                    selected_type=account_type_clean.upper(),
                    identifier=identifier,
                    selected_campus=campus_clean,
                    error="The selected campus does not match your registered campus.",
                ),
                status_code=400,
            )
    else:
        from app.services.complaint_service import get_campus_names
        if campus_clean in get_campus_names():
            user.campus = campus_clean
            db.commit()
            db.refresh(user)

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
    campus: str = Form(""),
    role_designation: str = Form(""),
    password: str = Form(""),
    confirm_password: str = Form(""),
    department: str = Form(""),
    program: str = Form(""),
    admin_code: str = Form(""),
    db: Session = Depends(get_db),
):
    from app.schemas.user import UserRegisterRequest
    from app.services.complaint_service import get_campus_names
    from app.services.user_service import register_user

    account_type_clean = (account_type or "").strip()
    acc_upper = account_type_clean.upper()

    clean_role_designation = (role_designation or "").strip()
    clean_department = (department or "").strip()
    clean_program = (program or "").strip()
    clean_campus = (campus or "").strip()

    if acc_upper == UserRole.ADMIN.value:
        clean_role_designation = "Admin"
        clean_department = ""
        clean_program = ""
    elif acc_upper == UserRole.STUDENT.value:
        clean_role_designation = "Student"
        clean_department = ""
    elif acc_upper == UserRole.EMPLOYEE.value:
        clean_program = ""

    confirm_pwd = (confirm_password or "").strip()

    values = dict(
        account_type=acc_upper,
        identifier=identifier,
        full_name=full_name,
        email=email,
        campus=clean_campus,
        role_designation=clean_role_designation,
        department=clean_department,
        program=clean_program,
        admin_code=admin_code,
    )

    if not account_type_clean or account_type_clean.lower() in ("select account type", "none"):
        return templates.TemplateResponse(
            request,
            "login.html",
            _auth_ctx(
                active_tab="register",
                selected_type="",
                identifier=identifier,
                error="Please select your account type.",
                values=values,
            ),
            status_code=422,
        )

    if not clean_campus:
        return templates.TemplateResponse(
            request,
            "login.html",
            _auth_ctx(
                active_tab="register",
                selected_type=acc_upper,
                identifier=identifier,
                error="Please select your Campus.",
                values=values,
            ),
            status_code=422,
        )

    valid_campuses = get_campus_names()
    if clean_campus not in valid_campuses:
        return templates.TemplateResponse(
            request,
            "login.html",
            _auth_ctx(
                active_tab="register",
                selected_type=acc_upper,
                identifier=identifier,
                error="Please select a valid university campus from the list.",
                values=values,
            ),
            status_code=422,
        )

    if not confirm_pwd or confirm_pwd != password:
        return templates.TemplateResponse(
            request,
            "login.html",
            _auth_ctx(
                active_tab="register",
                selected_type=acc_upper,
                identifier=identifier,
                error="Passwords do not match.",
                values=values,
            ),
            status_code=422,
        )

    try:
        req = UserRegisterRequest(
            account_type=acc_upper,
            identifier=identifier.strip(),
            full_name=full_name.strip(),
            email=email.strip(),
            password=password,
            confirm_password=confirm_pwd,
            campus=clean_campus,
            department=clean_department or None,
            program=clean_program or None,
            role_designation=clean_role_designation or None,
            admin_code=admin_code.strip() or None,
        )
        user = register_user(db, req, strict_mode=False)
    except ValidationError as exc:
        msg = "; ".join(e["msg"] for e in exc.errors())
        return templates.TemplateResponse(
            request,
            "login.html",
            _auth_ctx(
                active_tab="register",
                selected_type=acc_upper,
                identifier=identifier,
                error=msg,
                values=values,
            ),
            status_code=422,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "login.html",
            _auth_ctx(
                active_tab="register",
                selected_type=acc_upper,
                identifier=identifier,
                error=str(exc),
                values=values,
            ),
            status_code=422,
        )

    login_type = UserRole.EMPLOYEE.value if user.role in (UserRole.EMPLOYEE.value, UserRole.PROFESSOR.value) else user.role
    return templates.TemplateResponse(
        request,
        "login.html",
        _auth_ctx(
            active_tab="login",
            selected_type=login_type,
            identifier=user.identifier,
            success_msg="Registration successful. You can now login.",
        ),
    )


@router.get("/forgot-password")
def forgot_password_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "login.html", _auth_ctx(active_tab="forgot"))


@router.post("/forgot-password")
def handle_forgot_password(
    request: Request,
    email: str = Form(""),
    db: Session = Depends(get_db),
):
    from app.services.user_service import initiate_password_recovery

    try:
        user, token = initiate_password_recovery(db, email)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "login.html",
            _auth_ctx(
                active_tab="forgot",
                forgot_email=email,
                error=str(exc),
            ),
            status_code=422,
        )

    login_type = UserRole.EMPLOYEE.value if user.role in (UserRole.EMPLOYEE.value, UserRole.PROFESSOR.value) else user.role
    return templates.TemplateResponse(
        request,
        "login.html",
        _auth_ctx(
            active_tab="reset",
            selected_type=login_type,
            identifier=user.email,
            reset_token=token,
            reset_email=user.email,
            success_msg=f"Account verified for {user.email}. Create your new password below.",
        ),
    )


@router.post("/reset-password")
def handle_reset_password(
    request: Request,
    reset_token: str = Form(""),
    reset_email: str = Form(""),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
    db: Session = Depends(get_db),
):
    from app.services.user_service import complete_password_reset

    try:
        user = complete_password_reset(db, reset_token, new_password, confirm_password)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "login.html",
            _auth_ctx(
                active_tab="reset",
                reset_token=reset_token,
                reset_email=reset_email,
                error=str(exc),
            ),
            status_code=422,
        )

    login_type = UserRole.EMPLOYEE.value if user.role in (UserRole.EMPLOYEE.value, UserRole.PROFESSOR.value) else user.role
    return templates.TemplateResponse(
        request,
        "login.html",
        _auth_ctx(
            active_tab="login",
            selected_type=login_type,
            identifier=user.email,
            success_msg="Your password has been reset successfully. You can now login.",
        ),
    )


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


def _complaint_form_ctx(
    user: Optional[User],
    form_action: str = "/submit",
    values: Optional[dict] = None,
    errors: Optional[list[str]] = None,
    field_errors: Optional[dict[str, str]] = None,
    submitted: Optional[str] = None,
) -> dict:
    from app.services.user_service import DEGREE_PROGRAMS, EMPLOYEE_ROLES

    default_values: dict[str, str] = {}
    if user:
        acc_type = (
            UserRole.EMPLOYEE.value
            if user.role in (UserRole.EMPLOYEE.value, UserRole.PROFESSOR.value)
            else user.role
        )
        prog_or_role = (
            user.program
            if user.role == UserRole.STUDENT.value
            else (
                user.role_designation
                or user.department
                or ("Admin" if user.role == UserRole.ADMIN.value else "")
            )
        )
        default_values = {
            "account_type": acc_type or "",
            "student_name": user.full_name or "",
            "student_id": user.identifier or "",
            "email": user.email or "",
            "originating_campus": "",
            "target_campus": "",
            "class_or_program": prog_or_role or "",
            "subject": "",
            "complaint_title": "",
            "complaint_text": "",
        }

    merged_values = dict(default_values)
    if values:
        for k, v in values.items():
            if v is not None:
                merged_values[k] = v

    return {
        "current_user": user,
        "student": user,
        "settings": get_settings(),
        "form_action": form_action,
        "campuses": svc.get_campus_names(),
        "degree_programs": DEGREE_PROGRAMS,
        "employee_roles": EMPLOYEE_ROLES,
        "departments": get_routing_service().department_names,
        "values": merged_values,
        "errors": errors or [],
        "field_errors": field_errors or {},
        "submitted": submitted,
    }


def _handle_web_complaint_post(
    request: Request,
    db: Session,
    user: Optional[User],
    template_name: str,
    form_action: str,
    account_type: str,
    student_name: str,
    student_id: str,
    email: str,
    originating_campus: str,
    target_campus: str,
    class_or_program: str,
    subject: str,
    complaint_title: str,
    complaint_text: str,
    ui_mode: str,
    attachment: Optional[UploadFile],
    enforce_student_identity: bool = False,
) -> Response:
    from app.services.user_service import get_user_by_email, get_user_by_identifier

    wants_json = (
        request.headers.get("x-requested-with", "").lower() == "xmlhttprequest"
        or "application/json" in request.headers.get("accept", "").lower()
    )

    acc_clean = (account_type or "").strip().upper()
    name_clean = (student_name or "").strip()
    id_clean = (student_id or "").strip()
    email_clean = (email or "").strip()
    orig_clean = (originating_campus or "").strip()
    targ_clean = (target_campus or "").strip()
    prog_clean = (class_or_program or "").strip()
    subj_clean = (subject or "").strip()
    title_clean = (complaint_title or "").strip()
    text_clean = (complaint_text or "").strip()

    if enforce_student_identity and user:
        acc_clean = acc_clean or UserRole.STUDENT.value
        name_clean = user.full_name
        id_clean = user.student_id or id_clean
        email_clean = user.email
        prog_clean = prog_clean or (user.program or "")

    values = dict(
        account_type=acc_clean,
        student_name=name_clean,
        student_id=id_clean,
        email=email_clean,
        originating_campus=orig_clean,
        target_campus=targ_clean,
        class_or_program=prog_clean,
        subject=subj_clean,
        complaint_title=title_clean,
        complaint_text=text_clean,
    )

    field_errors: dict[str, str] = {}
    errors: list[str] = []

    campuses = svc.get_campus_names()

    # Validate strict UI fields when submitted from the redesigned form (ui_mode == 'v2')
    if ui_mode == "v2":
        if acc_clean not in (UserRole.STUDENT.value, UserRole.EMPLOYEE.value, UserRole.ADMIN.value):
            field_errors["account_type"] = "Please select your account type."
        if not name_clean:
            field_errors["student_name"] = "Please enter your full name."
        if not id_clean:
            field_errors["student_id"] = "Please enter your Student ID or Employee ID."
        if not email_clean or "@" not in email_clean or "." not in email_clean.split("@")[-1]:
            field_errors["email"] = "Please enter a valid email address."
        if not orig_clean or orig_clean not in campuses:
            field_errors["originating_campus"] = "Please select an originating campus."
        if not targ_clean or targ_clean not in campuses:
            field_errors["target_campus"] = "Please select a target campus."
        if not prog_clean:
            field_errors["class_or_program"] = "Please select your academic program or role."
        if not title_clean or len(title_clean) < 3:
            field_errors["complaint_title"] = "Please enter a short title (at least 3 characters)."
        if not text_clean:
            field_errors["complaint_text"] = "Please describe your complaint in detail."

    # Validate & store attachment if uploaded
    attachment_path: Optional[str] = None
    attachment_name: Optional[str] = None
    if attachment is not None and getattr(attachment, "filename", None):
        try:
            attachment_path, attachment_name = svc.save_complaint_attachment(attachment)
        except ComplaintValidationError as exc:
            field_errors["attachment"] = exc.errors[0]

    if field_errors:
        errors = list(field_errors.values())
        if wants_json:
            return JSONResponse(
                {"ok": False, "errors": errors, "field_errors": field_errors},
                status_code=422,
            )
        return templates.TemplateResponse(
            request,
            template_name,
            _complaint_form_ctx(
                user,
                form_action=form_action,
                values=values,
                errors=errors,
                field_errors=field_errors,
            ),
            status_code=422,
        )

    # Link to authenticated user or matched user in DB
    effective_user_id = user.id if user else None
    if not effective_user_id:
        matched_user = None
        if acc_clean and id_clean:
            matched_user = get_user_by_identifier(db, acc_clean, id_clean)
        if not matched_user and email_clean:
            matched_user = get_user_by_email(db, email_clean)
        if matched_user:
            effective_user_id = matched_user.id

    payload_data = dict(
        student_name=name_clean,
        student_id=id_clean or None,
        email=email_clean or None,
        class_or_program=prog_clean or None,
        subject=subj_clean or (f"{orig_clean} -> {targ_clean}" if orig_clean and targ_clean else None),
        account_type=acc_clean or None,
        originating_campus=orig_clean or None,
        target_campus=targ_clean or None,
        attachment_path=attachment_path,
        attachment_name=attachment_name,
        complaint_title=title_clean,
        complaint_text=text_clean,
    )

    try:
        complaint = svc.create_complaint(db, ComplaintCreate(**payload_data), user_id=effective_user_id)
    except ValidationError as exc:
        for e in exc.errors():
            loc_key = str(e["loc"][-1]) if e.get("loc") else ""
            if loc_key:
                field_errors.setdefault(loc_key, e["msg"])
        errors = _pydantic_messages(exc)
    except ComplaintValidationError as exc:
        errors = exc.errors
        for msg in errors:
            if "short" in msg.lower() or "complaint" in msg.lower():
                field_errors.setdefault("complaint_text", msg)
    else:
        if wants_json:
            return JSONResponse(
                {
                    "ok": True,
                    "id": complaint.id,
                    "complaint_number": complaint.complaint_number,
                    "status": complaint.status,
                    "message": "Your complaint has been received.",
                },
                status_code=201,
            )
        return templates.TemplateResponse(
            request,
            template_name,
            _complaint_form_ctx(
                user,
                form_action=form_action,
                submitted=complaint.complaint_number,
            ),
        )

    if wants_json:
        return JSONResponse(
            {"ok": False, "errors": errors, "field_errors": field_errors},
            status_code=422,
        )
    return templates.TemplateResponse(
        request,
        template_name,
        _complaint_form_ctx(
            user,
            form_action=form_action,
            values=values,
            errors=errors,
            field_errors=field_errors,
        ),
        status_code=422,
    )


@router.get("/student/complaints/new")
def student_complaint_form_page(request: Request, db: Session = Depends(get_db)):
    student, redirect = _require_web_role(request, db, UserRole.STUDENT.value)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        request,
        "student_complaint_form.html",
        _complaint_form_ctx(student, form_action="/student/complaints/new"),
    )


@router.post("/student/complaints/new")
def student_complaint_form_submit(
    request: Request,
    account_type: str = Form("STUDENT"),
    student_name: str = Form(""),
    student_id: str = Form(""),
    email: str = Form(""),
    originating_campus: str = Form(""),
    target_campus: str = Form(""),
    class_or_program: str = Form(""),
    subject: str = Form(""),
    complaint_title: str = Form(""),
    complaint_text: str = Form(""),
    ui_mode: str = Form(""),
    attachment: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
):
    student, redirect = _require_web_role(request, db, UserRole.STUDENT.value)
    if redirect:
        return redirect

    return _handle_web_complaint_post(
        request=request,
        db=db,
        user=student,
        template_name="student_complaint_form.html",
        form_action="/student/complaints/new",
        account_type=account_type,
        student_name=student_name,
        student_id=student_id,
        email=email,
        originating_campus=originating_campus,
        target_campus=target_campus,
        class_or_program=class_or_program,
        subject=subject,
        complaint_title=complaint_title,
        complaint_text=complaint_text,
        ui_mode=ui_mode,
        attachment=attachment,
        enforce_student_identity=True,
    )


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

    c = svc.get_employee_complaint(db, cid, employee)
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

    c = svc.get_employee_complaint(db, cid, employee)
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

    c = svc.get_professor_complaint(db, cid, professor)
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

    c = svc.get_professor_complaint(db, cid, professor)
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
    campus: str = "",
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
            campus=campus or None,
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
        "campuses": svc.get_campus_names(),
        "f": dict(q=q, priority=priority, category=category, department=department, campus=campus, status=status, review=review),
        **_admin_ctx(),
    })


@router.get("/admin/complaints")
def admin_complaints_redirect():
    return RedirectResponse("/admin", status_code=303)


@router.get("/admin/users")
def admin_users_page(
    request: Request,
    tab: str = "students",
    role: str = "",
    campus: str = "",
    q: str = "",
    db: Session = Depends(get_db),
):
    admin, redirect = _require_web_role(request, db, UserRole.ADMIN.value)
    if redirect:
        return redirect

    # 1. Determine authorized campus from authenticated admin account
    # Preserve existing super-admin permissions for System Administrator (ADMIN-001 / ADMIN-1001)
    is_super_admin = bool(
        (admin.admin_id and admin.admin_id.upper() in ("ADMIN-001", "ADMIN", "ADMIN-1001"))
        or (admin.email and admin.email.lower() in ("admin@example.edu", "admin1001@example.edu"))
        or admin.full_name in ("System Administrator", "Security Admin")
    )

    campus_param = (campus or "").strip()
    if is_super_admin and campus_param:
        admin_campus = campus_param
    else:
        admin_campus = (admin.campus or "").strip()
        if not admin_campus:
            # Fallback to Multan Campus for demo accounts without explicit campus
            admin_campus = "Multan Campus"

    # 2. Normalize category tab
    tab_clean = (tab or "").strip().lower()
    if tab_clean not in ("students", "employees", "admins"):
        tab_clean = "students"

    # 3. Server-side campus-isolated base query
    base_query = db.query(User).filter(User.campus == admin_campus)

    # 4. Search filter by name, email, or ID
    q_clean = (q or "").strip()
    if q_clean:
        ql = f"%{q_clean}%"
        base_query = base_query.filter(
            or_(
                User.full_name.ilike(ql),
                User.email.ilike(ql),
                User.student_id.ilike(ql),
                User.employee_id.ilike(ql),
                User.professor_id.ilike(ql),
                User.admin_id.ilike(ql),
            )
        )

    # 5. Calculate category counts for admin's campus
    student_count = base_query.filter(User.role == UserRole.STUDENT.value).count()
    employee_count = base_query.filter(User.role.in_([UserRole.EMPLOYEE.value, UserRole.PROFESSOR.value])).count()
    admin_count = base_query.filter(User.role == UserRole.ADMIN.value).count()
    total_users_count = student_count + employee_count + admin_count

    # 6. Apply Role filter from dropdown if selected
    role_clean = (role or "").strip().upper()
    active_tab = tab_clean
    if role_clean == "STUDENT":
        active_tab = "students"
    elif role_clean in ("EMPLOYEE", "PROFESSOR"):
        active_tab = "employees"
    elif role_clean == "ADMIN":
        active_tab = "admins"

    # 7. Query records for the active category tab
    query = base_query
    if active_tab == "students":
        query = query.filter(User.role == UserRole.STUDENT.value)
    elif active_tab == "employees":
        query = query.filter(User.role.in_([UserRole.EMPLOYEE.value, UserRole.PROFESSOR.value]))
    elif active_tab == "admins":
        query = query.filter(User.role == UserRole.ADMIN.value)

    users = query.order_by(User.id.asc()).all()

    return templates.TemplateResponse(request, "admin_users.html", {
        "current_user": admin,
        "admin": admin,
        "admin_campus": admin_campus,
        "users": users,
        "tab": active_tab,
        "q": q_clean,
        "role": role_clean,
        "student_count": student_count,
        "employee_count": employee_count,
        "admin_count": admin_count,
        "total_users_count": total_users_count,
        "campuses": svc.get_campus_names(),
        "f": dict(role=role_clean, campus=admin_campus, q=q_clean),
    })


@router.get("/admin/departments")
def admin_departments_page(request: Request, campus: str = "", db: Session = Depends(get_db)):
    admin, redirect = _require_web_role(request, db, UserRole.ADMIN.value)
    if redirect:
        return redirect

    dept_names = _admin_ctx()["departments"]
    dept_stats = []
    for d in dept_names:
        query = db.query(Complaint).join(Complaint.analysis).filter(Complaint.is_deleted.is_(False), Complaint.analysis.has(assigned_department=d))
        if campus:
            query = query.filter(or_(Complaint.target_campus == campus, Complaint.originating_campus == campus))
        c_list = query.all()
        total = len(c_list)
        pending = sum(1 for c in c_list if c.status not in (ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value))
        resolved = sum(1 for c in c_list if c.status in (ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value))
        dept_stats.append({"name": d, "total": total, "pending": pending, "resolved": resolved, "campuses": "All Campuses"})

    return templates.TemplateResponse(request, "admin_departments.html", {
        "current_user": admin,
        "admin": admin,
        "dept_stats": dept_stats,
        "campuses": svc.get_campus_names(),
        "selected_campus": campus,
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
    return templates.TemplateResponse(
        request,
        "complaint_form.html",
        _complaint_form_ctx(user, form_action="/submit"),
    )


@router.post("/submit")
def legacy_submit(
    request: Request,
    account_type: str = Form(""),
    student_name: str = Form(""),
    full_name: str = Form(""),
    student_id: str = Form(""),
    email: str = Form(""),
    originating_campus: str = Form(""),
    target_campus: str = Form(""),
    class_or_program: str = Form(""),
    subject: str = Form(""),
    complaint_title: str = Form(""),
    complaint_text: str = Form(""),
    ui_mode: str = Form(""),
    attachment: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
):
    user = _get_web_user(request, db)
    effective_name = student_name or full_name
    return _handle_web_complaint_post(
        request=request,
        db=db,
        user=user,
        template_name="complaint_form.html",
        form_action="/submit",
        account_type=account_type,
        student_name=effective_name,
        student_id=student_id,
        email=email,
        originating_campus=originating_campus,
        target_campus=target_campus,
        class_or_program=class_or_program,
        subject=subject,
        complaint_title=complaint_title,
        complaint_text=complaint_text,
        ui_mode=ui_mode,
        attachment=attachment,
        enforce_student_identity=False,
    )
