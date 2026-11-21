from __future__ import annotations

import logging
import secrets
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.campus import Campus, DepartmentRecord
from app.models.complaint import Complaint
from app.models.enums import UserRole
from app.models.user import Admin, Employee, HigherAuthorityProfile, Student, UniversityDirectory, User
from app.schemas.user import UserCreate, UserRegisterRequest

logger = logging.getLogger("complaint_agent.users")


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    stmt = select(User).where(User.email.ilike(email.strip()))
    return db.scalars(stmt).first()


def get_user_by_student_id(db: Session, student_id: str) -> Optional[User]:
    stmt = (
        select(User)
        .join(Student, User.id == Student.user_id)
        .where(Student.student_id.ilike(student_id.strip()))
    )
    return db.scalars(stmt).first()


def get_user_by_employee_id(db: Session, employee_id: str) -> Optional[User]:
    stmt = (
        select(User)
        .join(Employee, User.id == Employee.user_id)
        .where(Employee.employee_id.ilike(employee_id.strip()))
    )
    return db.scalars(stmt).first()


def get_user_by_professor_id(db: Session, professor_id: str) -> Optional[User]:
    stmt = (
        select(User)
        .join(Employee, User.id == Employee.user_id)
        .where(Employee.employee_id.ilike(professor_id.strip()))
    )
    return db.scalars(stmt).first()


def get_user_by_admin_id(db: Session, admin_id: str) -> Optional[User]:
    stmt = (
        select(User)
        .outerjoin(Admin, User.id == Admin.user_id)
        .outerjoin(Employee, User.id == Employee.user_id)
        .where(
            User.role == UserRole.ADMIN.value,
            or_(
                Admin.admin_id.ilike(admin_id.strip()),
                Employee.employee_id.ilike(admin_id.strip()),
            ),
        )
    )
    return db.scalars(stmt).first()


def get_user_by_identifier(db: Session, role: str, identifier: str) -> Optional[User]:
    role_key = role.strip().upper()
    ident = identifier.strip()
    if not ident:
        return None
    stmt = select(User).where(User.role == role_key)
    if role_key == UserRole.STUDENT.value:
        stmt = stmt.outerjoin(Student, User.id == Student.user_id).where(
            or_(Student.student_id.ilike(ident), User.email.ilike(ident))
        )
    elif role_key in (UserRole.EMPLOYEE.value, UserRole.PROFESSOR.value):
        stmt = stmt.outerjoin(Employee, User.id == Employee.user_id).where(
            or_(Employee.employee_id.ilike(ident), User.email.ilike(ident))
        )
    elif role_key == UserRole.ADMIN.value:
        stmt = stmt.outerjoin(Admin, User.id == Admin.user_id).outerjoin(Employee, User.id == Employee.user_id)
        admin_conds = [
            Admin.admin_id.ilike(ident),
            Employee.employee_id.ilike(ident),
            User.email.ilike(ident),
            User.full_name.ilike(ident),
        ]
        if ident.lower() in ("admin", "admin-001", "admin-1001"):
            admin_conds.append(User.role == UserRole.ADMIN.value)
        stmt = stmt.where(or_(*admin_conds))
    elif role_key == UserRole.HIGHER_AUTHORITY.value:
        stmt = stmt.outerjoin(HigherAuthorityProfile, User.id == HigherAuthorityProfile.user_id).where(
            or_(
                HigherAuthorityProfile.authority_id.ilike(ident),
                HigherAuthorityProfile.authority_name.ilike(ident),
                User.email.ilike(ident),
                User.full_name.ilike(ident),
            )
        )
    else:
        return None
    return db.scalars(stmt).first()


def get_directory_entry(db: Session, identifier: str) -> Optional[UniversityDirectory]:
    stmt = select(UniversityDirectory).where(UniversityDirectory.identifier.ilike(identifier.strip()))
    return db.scalars(stmt).first()


DEGREE_PROGRAMS: list[str] = [
    # Undergraduate Programs (BS / B.Ed / BBA / BFA)
    "BS Computer Science",
    "BS Information Technology",
    "BS Software Engineering",
    "BS Mathematics",
    "BS Physics",
    "BS Chemistry",
    "BS Botany",
    "BS Zoology",
    "BS English",
    "BS Urdu",
    "BS Islamic Studies",
    "BS Economics",
    "BS Economics and Finance",
    "BS Business Analytics",
    "BBA (Bachelor of Business Administration)",
    "B.Ed. (Hons)",
    "B.Ed. (Hons) Special Education",
    "B.Ed. (Hons) Educational Leadership & Management",
    "B.Ed. Secondary (1.5 Years)",
    "BS Physical Education and Sports Sciences",
    "BFA Painting & Graphic Design",
    "BS History",
    # Graduate Programs (MS / MPhil / MBA)
    "MS Computer Science",
    "MS Information Technology",
    "MS Mathematics",
    "MS Physics",
    "MS Chemistry",
    "MS Botany",
    "MS Zoology",
    "MPhil Education",
    "MPhil Educational Leadership and Policy Studies",
    "MPhil Special Education",
    "MPhil English (Linguistics)",
    "MPhil Urdu",
    "MPhil Economics",
    "MPhil Islamic Studies",
    "MBA (Master of Business Administration)",
    "MS Management Sciences",
    # Postgraduate Programs (PhD)
    "PhD Computer Science",
    "PhD Education",
    "PhD Educational Leadership and Policy Studies",
    "PhD Special Education",
    "PhD Mathematics",
    "PhD Physics",
    "PhD Chemistry",
    "PhD Botany",
    "PhD Zoology",
    "PhD English (Linguistics)",
    "PhD Urdu",
    "PhD Economics",
    "PhD Management Sciences",
    "PhD Islamic Studies",
]

EMPLOYEE_ROLES: list[str] = [
    "Lecturer",
    "Assistant Professor",
    "Associate Professor",
    "Professor",
    "Head of Department (HOD)",
    "Principal / Campus Director",
    "Director of Division",
    "Dean",
    "Registrar / Administrative Officer",
    "Controller of Examinations",
    "Treasurer / Accounts Officer",
    "Directorate of Student Affairs Officer",
    "Directorate of IT Officer",
    "Librarian",
    "Transport Officer",
    "Hostel Warden",
    "Security Officer",
]


def create_user(db: Session, data: UserCreate) -> User:
    role_str = data.role.value if isinstance(data.role, UserRole) else str(data.role)
    default_designation = (
        "Admin" if role_str == UserRole.ADMIN.value
        else ("Professor" if role_str == UserRole.PROFESSOR.value
              else ("Student" if role_str == UserRole.STUDENT.value else "Employee"))
    )

    final_campus_id = data.campus_id
    if not final_campus_id and data.campus:
        campus_rec = db.scalars(select(Campus).where(Campus.name == data.campus.strip())).first()
        if campus_rec:
            final_campus_id = campus_rec.id

    user = User(
        full_name=data.full_name.strip(),
        email=data.email.strip().lower(),
        password_hash=hash_password(data.password),
        role=role_str,
        campus_id=final_campus_id,
        is_active=True,
    )
    db.add(user)
    db.flush()

    if role_str == UserRole.STUDENT.value:
        stu = Student(
            user_id=user.id,
            student_id=data.student_id.strip() if data.student_id else "",
            program=data.program.strip() if data.program else None,
        )
        db.add(stu)
    elif role_str in (UserRole.EMPLOYEE.value, UserRole.PROFESSOR.value):
        dept_rec = None
        if data.department:
            dept_rec = db.scalars(select(DepartmentRecord).where(DepartmentRecord.name == data.department.strip())).first()
        emp = Employee(
            user_id=user.id,
            employee_id=(data.employee_id or data.professor_id or "").strip(),
            department_id=dept_rec.id if dept_rec else None,
            role_designation=(data.role_designation or default_designation).strip(),
            is_faculty=(role_str == UserRole.PROFESSOR.value),
        )
        db.add(emp)
    elif role_str == UserRole.ADMIN.value:
        adm = Admin(
            user_id=user.id,
            admin_id=(data.admin_id or data.employee_id or "ADMIN-001").strip(),
            designation=(data.role_designation or "System Administrator").strip(),
            permission_level="SUPER_ADMIN",
        )
        db.add(adm)
    elif role_str == UserRole.HIGHER_AUTHORITY.value:
        auth_name = (data.authority_name or data.department or "Higher Authority").strip()
        auth = HigherAuthorityProfile(
            user_id=user.id,
            authority_id=(data.authority_id or data.employee_id or (f"AUTH-{user.id:04d}" if user.id else "AUTH-001")).strip(),
            authority_name=auth_name,
            designation=(data.role_designation or auth_name).strip(),
        )
        db.add(auth)

    db.commit()
    db.refresh(user)
    return user


def register_user(db: Session, data: UserRegisterRequest, strict_mode: bool = True) -> User:
    """Validate and register a new portal account using the normalized relational schema."""
    if not data.account_type or data.account_type.strip().lower() in ("", "select account type", "none"):
        raise ValueError("Please select your account type.")

    role_key = data.account_type.strip().upper()
    if strict_mode:
        valid_account_types = (UserRole.STUDENT.value, UserRole.EMPLOYEE.value, UserRole.PROFESSOR.value, UserRole.ADMIN.value, UserRole.HIGHER_AUTHORITY.value)
    else:
        valid_account_types = (UserRole.STUDENT.value, UserRole.EMPLOYEE.value, UserRole.ADMIN.value, UserRole.HIGHER_AUTHORITY.value)

    if role_key not in valid_account_types:
        raise ValueError("Please select a valid account type (Student, Employee, Admin, or Higher Authority).")

    if not data.full_name or not data.full_name.strip():
        raise ValueError("Please enter your full name.")

    ident = data.identifier.strip().upper() if strict_mode else data.identifier.strip()
    if not ident:
        raise ValueError("Please enter your ID.")

    if strict_mode:
        if role_key == UserRole.STUDENT.value and not ident.upper().startswith("STU-"):
            raise ValueError("Invalid Student ID. Expected format: STU-XXXX (e.g. STU-1001)")
        elif role_key == UserRole.EMPLOYEE.value and not ident.upper().startswith("EMP-"):
            raise ValueError("Invalid Employee ID. Expected format: EMP-XXXX (e.g. EMP-1001)")
        elif role_key == UserRole.PROFESSOR.value and not ident.upper().startswith("PROF-"):
            raise ValueError("Invalid Professor ID. Expected format: PROF-XXXX (e.g. PROF-1001)")
        elif role_key == UserRole.ADMIN.value and not ident.upper().startswith("ADMIN-") and ident.upper() != "ADMIN":
            raise ValueError("Invalid Admin ID. Expected format: ADMIN-XXXX (e.g. ADMIN-1001)")
        elif role_key == UserRole.HIGHER_AUTHORITY.value:
            if len(ident) < 2:
                raise ValueError("Please enter a valid Authority ID (e.g. AUTH-1001).")

    email_str = str(data.email).strip().lower()
    if not email_str or "@" not in email_str or "." not in email_str.split("@")[-1]:
        raise ValueError("Please enter a valid email address.")

    from app.services.routing_service import get_routing_service
    valid_departments = get_routing_service().department_names

    effective_role = role_key
    final_program: Optional[str] = None
    final_department: Optional[str] = None
    final_role_designation: Optional[str] = None

    if role_key == UserRole.STUDENT.value:
        prog_val = (data.program or "").strip()
        if not strict_mode:
            if not prog_val:
                raise ValueError("Please select your Degree/Program.")
            if prog_val not in DEGREE_PROGRAMS:
                raise ValueError("Please select a valid Degree/Program from the list.")
        final_program = prog_val or None
        final_department = None
        final_role_designation = "Student"

    elif role_key == UserRole.EMPLOYEE.value:
        emp_role = (data.role_designation or "").strip()
        emp_dept = (data.department or "").strip()
        if not strict_mode:
            if not emp_role or emp_role not in EMPLOYEE_ROLES:
                raise ValueError("Please select a valid employee Role.")
            if not emp_dept or emp_dept not in valid_departments:
                raise ValueError("Please select a valid Department.")
        final_role_designation = emp_role or "Employee"
        final_department = emp_dept or None
        final_program = None
        if emp_role == "Professor":
            effective_role = UserRole.PROFESSOR.value

    elif role_key == UserRole.PROFESSOR.value:
        effective_role = UserRole.PROFESSOR.value
        final_role_designation = "Professor"
        final_department = (data.department or "").strip() or None
        final_program = None

    elif role_key == UserRole.ADMIN.value:
        final_role_designation = "Admin"
        final_program = None
        final_department = (data.department or "").strip() if (strict_mode and data.department) else None

    elif role_key == UserRole.HIGHER_AUTHORITY.value:
        effective_role = UserRole.HIGHER_AUTHORITY.value
        auth_name = (data.authority_name or data.department or "").strip()
        if not auth_name:
            raise ValueError("Please select your Designated Higher Authority / Office.")
        final_role_designation = auth_name
        final_department = auth_name
        final_program = None

    from app.services.complaint_service import get_campus_names
    valid_campuses = get_campus_names()
    campus_val = (data.campus or "").strip()
    if not campus_val:
        if strict_mode:
            campus_val = "Township Campus, Lahore (Main Campus)"
        else:
            raise ValueError("Please select your Campus.")
    elif campus_val not in valid_campuses:
        raise ValueError("Please select a valid Campus from the list.")

    campus_record = db.scalars(select(Campus).where(Campus.name == campus_val)).first()
    final_campus_id = campus_record.id if campus_record else None

    if len(data.password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    if data.password != data.confirm_password:
        raise ValueError("Passwords do not match.")

    # Check existing user
    existing_user = get_user_by_identifier(db, effective_role, ident)
    if not existing_user:
        existing_user = get_user_by_email(db, email_str)

    if existing_user and existing_user.password_hash:
        raise ValueError("This ID or email is already registered. Please login.")

    if strict_mode and role_key == UserRole.ADMIN.value:
        expected_token = get_settings().admin_registration_token
        if not data.admin_code or not secrets.compare_digest(data.admin_code.strip(), expected_token):
            raise ValueError("Invalid admin verification code. Admin registration requires an authorized code.")

    # Directory verification
    dir_record = get_directory_entry(db, ident)
    if dir_record:
        if strict_mode and dir_record.role != role_key:
            raise ValueError(f"This ID is registered as a {dir_record.role.title()}, not {role_key.title()}.")
        if strict_mode:
            email_match = dir_record.email.lower() == email_str
            name_match = dir_record.full_name.lower() == data.full_name.strip().lower()
            if not (email_match or name_match):
                raise ValueError("The provided name or email does not match official university records for this ID.")
        dir_record.is_claimed = True
        dir_record.campus = campus_val
        dir_record.campus_id = final_campus_id
    else:
        existing_dir_email = db.scalars(select(UniversityDirectory).where(UniversityDirectory.email.ilike(email_str))).first()
        if not existing_dir_email:
            new_dir = UniversityDirectory(
                role=effective_role,
                identifier=ident,
                full_name=data.full_name.strip(),
                email=email_str,
                department=final_department,
                program=final_program,
                campus=campus_val,
                campus_id=final_campus_id,
                role_designation=final_role_designation,
                is_claimed=True,
            )
            db.add(new_dir)

    if strict_mode and dir_record:
        if not final_department and dir_record.department and role_key != UserRole.ADMIN.value:
            final_department = dir_record.department
        if not final_program and dir_record.program and role_key == UserRole.STUDENT.value:
            final_program = dir_record.program

    if existing_user and not existing_user.password_hash:
        user = existing_user
        user.password_hash = hash_password(data.password)
        user.full_name = data.full_name.strip()
        user.role = effective_role
        user.campus_id = final_campus_id
        user.is_active = True
    else:
        user = User(
            full_name=data.full_name.strip(),
            email=email_str,
            password_hash=hash_password(data.password),
            role=effective_role,
            campus_id=final_campus_id,
            is_active=True,
        )
        db.add(user)

    db.flush()

    # Relational 1:1 subtype profile setup
    if effective_role == UserRole.STUDENT.value:
        if not user.student_profile:
            user.student_profile = Student(user_id=user.id, student_id=ident, program=final_program)
            db.add(user.student_profile)
        else:
            user.student_profile.student_id = ident
            user.student_profile.program = final_program
    elif effective_role in (UserRole.EMPLOYEE.value, UserRole.PROFESSOR.value):
        dept_rec = None
        if final_department:
            dept_rec = db.scalars(select(DepartmentRecord).where(DepartmentRecord.name == final_department)).first()
        if not user.employee_profile:
            user.employee_profile = Employee(
                user_id=user.id,
                employee_id=ident,
                department_id=dept_rec.id if dept_rec else None,
                role_designation=final_role_designation or "Employee",
                is_faculty=(effective_role == UserRole.PROFESSOR.value),
            )
            db.add(user.employee_profile)
        else:
            user.employee_profile.employee_id = ident
            user.employee_profile.department_id = dept_rec.id if dept_rec else None
            user.employee_profile.role_designation = final_role_designation or "Employee"
            user.employee_profile.is_faculty = (effective_role == UserRole.PROFESSOR.value)
    elif effective_role == UserRole.ADMIN.value:
        if not user.admin_profile:
            user.admin_profile = Admin(
                user_id=user.id,
                admin_id=ident,
                designation=final_role_designation or "System Administrator",
                permission_level="SUPER_ADMIN",
            )
            db.add(user.admin_profile)
        else:
            user.admin_profile.admin_id = ident
            user.admin_profile.designation = final_role_designation or "System Administrator"
    elif effective_role == UserRole.HIGHER_AUTHORITY.value:
        if not user.authority_profile:
            user.authority_profile = HigherAuthorityProfile(
                user_id=user.id,
                authority_id=ident,
                authority_name=final_department or "Higher Authority",
                designation=final_role_designation or "Higher Authority",
            )
            db.add(user.authority_profile)
        else:
            user.authority_profile.authority_id = ident
            user.authority_profile.authority_name = final_department or "Higher Authority"
            user.authority_profile.designation = final_role_designation or "Higher Authority"

    db.commit()
    db.refresh(user)

    if user.role == UserRole.STUDENT.value and user.student_id:
        unlinked = db.scalars(
            select(Complaint).where(
                Complaint.user_id.is_(None),
                or_(Complaint.student_id_code == user.student_id, Complaint.email == user.email),
            )
        ).all()
        for c in unlinked:
            c.user_id = user.id
            if user.student_profile:
                c.student_profile_id = user.student_profile.id
        if unlinked:
            db.commit()
            logger.info("Linked %d historical complaints to registered student %s", len(unlinked), user.student_id)

    return user


def initiate_password_recovery(db: Session, email: str) -> tuple[User, str]:
    from app.core.security import create_access_token

    email_clean = (email or "").strip().lower()
    if not email_clean or "@" not in email_clean or "." not in email_clean.split("@")[-1]:
        raise ValueError("Please enter a valid registered email address.")

    user = get_user_by_email(db, email_clean)
    if not user or not user.is_active:
        raise ValueError("No registered account found with that email address.")

    token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "purpose": "password_reset",
            "fp": (user.password_hash or "")[:12],
        },
        expires_in_seconds=1800,
    )
    return user, token


def complete_password_reset(
    db: Session,
    token: str,
    new_password: str,
    confirm_password: str,
) -> User:
    from app.core.security import decode_access_token

    if not token or not token.strip():
        raise ValueError("Invalid or expired password recovery session. Please try again.")

    payload = decode_access_token(token.strip())
    if not payload or payload.get("purpose") != "password_reset":
        raise ValueError("Your password recovery link has expired or is invalid. Please request a new one.")

    user = get_user_by_id(db, int(payload["sub"]))
    if not user or not user.is_active:
        raise ValueError("Account not found.")

    if (user.password_hash or "")[:12] != payload.get("fp"):
        raise ValueError("This password recovery token has already been used.")

    if not new_password or len(new_password) < 6:
        raise ValueError("New password must be at least 6 characters.")

    if new_password != confirm_password:
        raise ValueError("New passwords do not match.")

    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user


def init_default_users(db: Session) -> None:
    """Empty implementation to guarantee all newly created tables remain completely empty."""
    logger.info("Database initialized without dummy/seed accounts as instructed.")
    return


def save_user_avatar(upload_file, user_id: int) -> Optional[str]:
    import uuid
    from pathlib import Path
    from app.core.config import BASE_DIR
    from app.services.complaint_service import _is_valid_image_header, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_MIME_TYPES

    if upload_file is None:
        return None

    raw_filename = (getattr(upload_file, "filename", None) or "").strip()
    if not raw_filename:
        return None

    file_obj = getattr(upload_file, "file", None)
    if file_obj is not None:
        file_obj.seek(0)
        content = file_obj.read()
    else:
        content = b""

    if not content:
        raise ValueError("Uploaded profile picture file is empty.")

    ext = Path(raw_filename).suffix.lower()
    raw_content_type = (getattr(upload_file, "content_type", None) or "").lower().strip()
    content_type = raw_content_type.split(";")[0].strip() if raw_content_type else ""

    if ext not in ALLOWED_IMAGE_EXTENSIONS or (
        content_type and content_type not in ALLOWED_IMAGE_MIME_TYPES and content_type != "application/octet-stream"
    ):
        raise ValueError("Unsupported image format. Allowed formats: PNG, JPG, JPEG, WEBP.")

    if len(content) > 500 * 1024:
        raise ValueError("Profile image exceeds the maximum allowed size of 500 KB.")

    if not _is_valid_image_header(content, ext):
        raise ValueError("Invalid or corrupted image file. Please upload a valid PNG, JPG, JPEG, or WEBP image.")

    upload_dir = Path(BASE_DIR) / "app" / "static" / "uploads" / "avatars"
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = f"avatar_{user_id}_{uuid.uuid4().hex[:12]}{ext}"
    dest_path = upload_dir / safe_filename
    dest_path.write_bytes(content)

    return f"/static/uploads/avatars/{safe_filename}"


def update_user_profile(
    db: Session,
    user: User,
    full_name: str,
    email: str,
    identifier: Optional[str] = None,
    campus: Optional[str] = None,
    program: Optional[str] = None,
    role_designation: Optional[str] = None,
    department: Optional[str] = None,
    new_password: Optional[str] = None,
    confirm_password: Optional[str] = None,
    avatar: Optional[Any] = None,
    remove_avatar: bool = False,
) -> User:
    name_clean = (full_name or "").strip()
    if not name_clean:
        raise ValueError("Full Name cannot be empty.")

    email_clean = (email or "").strip().lower()
    if not email_clean or "@" not in email_clean or "." not in email_clean.split("@")[-1]:
        raise ValueError("Please provide a valid email address.")

    other_email = db.scalars(
        select(User).where(User.id != user.id, User.email.ilike(email_clean))
    ).first()
    if other_email:
        raise ValueError("This email address is already in use by another account.")

    ident_clean = (identifier or "").strip()
    if not ident_clean:
        ident_clean = user.identifier

    other_ident = db.scalars(
        select(User).where(
            User.id != user.id,
            or_(
                User.student_id.ilike(ident_clean),
                User.employee_id.ilike(ident_clean),
                User.professor_id.ilike(ident_clean),
                User.admin_id.ilike(ident_clean),
            ),
        )
    ).first()
    if other_ident:
        raise ValueError(f"The ID '{ident_clean}' is already registered to another user.")

    campus_clean = (campus or "").strip()
    final_campus_id = user.campus_id
    if campus_clean:
        from app.services.complaint_service import get_campus_names
        valid_campuses = get_campus_names()
        if campus_clean in valid_campuses:
            campus_rec = db.scalars(select(Campus).where(Campus.name == campus_clean)).first()
            if campus_rec:
                final_campus_id = campus_rec.id
                user.campus_id = campus_rec.id

    user.full_name = name_clean
    user.email = email_clean

    old_identifier = user.identifier
    role_key = (user.role or "").upper()

    if role_key == UserRole.STUDENT.value:
        if not user.student_profile:
            user.student_profile = Student(user_id=user.id, student_id=ident_clean, program=program.strip() if program else None)
            db.add(user.student_profile)
        else:
            user.student_profile.student_id = ident_clean
            if program is not None:
                user.student_profile.program = program.strip() or None
    elif role_key in (UserRole.EMPLOYEE.value, UserRole.PROFESSOR.value):
        dept_id = None
        if department is not None and department.strip():
            dept_rec = db.scalars(select(DepartmentRecord).where(DepartmentRecord.name == department.strip())).first()
            if dept_rec:
                dept_id = dept_rec.id
        if not user.employee_profile:
            user.employee_profile = Employee(
                user_id=user.id,
                employee_id=ident_clean,
                department_id=dept_id,
                role_designation=(role_designation.strip() if role_designation else "Employee"),
                is_faculty=(role_key == UserRole.PROFESSOR.value),
            )
            db.add(user.employee_profile)
        else:
            user.employee_profile.employee_id = ident_clean
            if role_designation is not None:
                user.employee_profile.role_designation = role_designation.strip() or "Employee"
            if department is not None:
                user.employee_profile.department_id = dept_id
            user.employee_profile.is_faculty = (role_key == UserRole.PROFESSOR.value)
    elif role_key == UserRole.ADMIN.value:
        if not user.admin_profile:
            user.admin_profile = Admin(
                user_id=user.id,
                admin_id=ident_clean,
                designation="System Administrator",
                permission_level="SUPER_ADMIN",
            )
            db.add(user.admin_profile)
        else:
            user.admin_profile.admin_id = ident_clean
    elif role_key == UserRole.HIGHER_AUTHORITY.value:
        if not user.authority_profile:
            user.authority_profile = HigherAuthorityProfile(
                user_id=user.id,
                authority_id=ident_clean,
                authority_name=department.strip() if department and department.strip() else (user.department or "Higher Authority"),
                designation=role_designation.strip() if role_designation and role_designation.strip() else "Higher Authority",
            )
            db.add(user.authority_profile)
        else:
            user.authority_profile.authority_id = ident_clean
            if department is not None and department.strip():
                user.authority_profile.authority_name = department.strip()
            if role_designation is not None and role_designation.strip():
                user.authority_profile.designation = role_designation.strip()

    new_pw = (new_password or "").strip()
    conf_pw = (confirm_password or "").strip()
    if new_pw or conf_pw:
        if len(new_pw) < 6:
            raise ValueError("New password must be at least 6 characters.")
        if new_pw != conf_pw:
            raise ValueError("New passwords do not match.")
        user.password_hash = hash_password(new_pw)

    dir_entry = db.scalars(
        select(UniversityDirectory).where(
            or_(
                UniversityDirectory.identifier.ilike(old_identifier),
                UniversityDirectory.email.ilike(user.email),
                UniversityDirectory.identifier.ilike(ident_clean),
            )
        )
    ).first()
    if dir_entry:
        dir_entry.full_name = user.full_name
        dir_entry.email = user.email
        dir_entry.identifier = ident_clean
        dir_entry.campus = user.campus
        dir_entry.campus_id = final_campus_id
        if user.program:
            dir_entry.program = user.program
        if user.department:
            dir_entry.department = user.department
        if user.role_designation:
            dir_entry.role_designation = user.role_designation

    user_complaints = db.scalars(
        select(Complaint).where(Complaint.user_id == user.id)
    ).all()
    for c in user_complaints:
        c.student_name = user.full_name
        c.email = user.email
        if role_key == UserRole.STUDENT.value:
            c.student_id = user.student_id

    if remove_avatar and user.avatar_path:
        from pathlib import Path
        from app.core.config import BASE_DIR
        old_file = Path(BASE_DIR) / "app" / user.avatar_path.lstrip("/")
        if old_file.exists():
            try:
                old_file.unlink()
            except Exception:
                pass
        user.avatar_path = None

    if avatar is not None and getattr(avatar, "filename", None):
        new_avatar_path = save_user_avatar(avatar, user.id)
        if new_avatar_path:
            if user.avatar_path and user.avatar_path != new_avatar_path:
                from pathlib import Path
                from app.core.config import BASE_DIR
                old_file = Path(BASE_DIR) / "app" / user.avatar_path.lstrip("/")
                if old_file.exists():
                    try:
                        old_file.unlink()
                    except Exception:
                        pass
            user.avatar_path = new_avatar_path

    db.commit()
    db.refresh(user)
    logger.info("Updated profile for user ID %s (%s, %s)", user.id, user.full_name, user.identifier)
    return user
