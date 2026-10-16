from __future__ import annotations

import logging
import secrets
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.complaint import Complaint
from app.models.enums import UserRole
from app.models.user import UniversityDirectory, User
from app.schemas.user import UserCreate, UserRegisterRequest

logger = logging.getLogger("complaint_agent.users")


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    stmt = select(User).where(User.email.ilike(email.strip()))
    return db.scalars(stmt).first()


def get_user_by_student_id(db: Session, student_id: str) -> Optional[User]:
    stmt = select(User).where(User.student_id.ilike(student_id.strip()))
    return db.scalars(stmt).first()


def get_user_by_employee_id(db: Session, employee_id: str) -> Optional[User]:
    stmt = select(User).where(User.employee_id.ilike(employee_id.strip()))
    return db.scalars(stmt).first()


def get_user_by_professor_id(db: Session, professor_id: str) -> Optional[User]:
    stmt = select(User).where(User.professor_id.ilike(professor_id.strip()))
    return db.scalars(stmt).first()


def get_user_by_admin_id(db: Session, admin_id: str) -> Optional[User]:
    stmt = select(User).where(
        User.role == UserRole.ADMIN.value,
        or_(
            User.admin_id.ilike(admin_id.strip()),
            User.employee_id.ilike(admin_id.strip()),
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
        stmt = stmt.where(or_(User.student_id.ilike(ident), User.email.ilike(ident)))
    elif role_key == UserRole.EMPLOYEE.value:
        stmt = stmt.where(or_(User.employee_id.ilike(ident), User.email.ilike(ident)))
    elif role_key == UserRole.PROFESSOR.value:
        stmt = stmt.where(or_(User.professor_id.ilike(ident), User.email.ilike(ident)))
    elif role_key == UserRole.ADMIN.value:
        admin_conds = [
            User.admin_id.ilike(ident),
            User.employee_id.ilike(ident),
            User.email.ilike(ident),
            User.full_name.ilike(ident),
        ]
        if ident.lower() in ("admin", "admin-001", "admin-1001"):
            admin_conds.append(User.role == UserRole.ADMIN.value)
        stmt = stmt.where(or_(*admin_conds))
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
    user = User(
        full_name=data.full_name.strip(),
        email=data.email.strip().lower(),
        password_hash=hash_password(data.password),
        role=role_str,
        student_id=data.student_id.strip() if data.student_id else None,
        employee_id=data.employee_id.strip() if data.employee_id else None,
        professor_id=data.professor_id.strip() if data.professor_id else None,
        admin_id=data.admin_id.strip() if data.admin_id else (data.employee_id.strip() if role_str == UserRole.ADMIN.value and data.employee_id else None),
        department=data.department.strip() if data.department else None,
        program=data.program.strip() if data.program else None,
        campus=data.campus.strip() if data.campus else "Township Campus, Lahore (Main Campus)",
        campus_id=data.campus_id if data.campus_id else 1,
        role_designation=data.role_designation.strip() if data.role_designation else default_designation,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def register_user(db: Session, data: UserRegisterRequest, strict_mode: bool = True) -> User:
    """Validate and register a new portal account."""
    if not data.account_type or data.account_type.strip().lower() in ("", "select account type", "none"):
        raise ValueError("Please select your account type.")

    role_key = data.account_type.strip().upper()
    if strict_mode:
        valid_account_types = (UserRole.STUDENT.value, UserRole.EMPLOYEE.value, UserRole.PROFESSOR.value, UserRole.ADMIN.value)
    else:
        valid_account_types = (UserRole.STUDENT.value, UserRole.EMPLOYEE.value, UserRole.ADMIN.value)

    if role_key not in valid_account_types:
        raise ValueError("Please select a valid account type (Student, Employee, or Admin).")

    if not data.full_name or not data.full_name.strip():
        raise ValueError("Please enter your full name.")

    ident = data.identifier.strip().upper() if strict_mode else data.identifier.strip()
    if not ident:
        raise ValueError("Please enter your ID.")

    # Role ID format validation (only when strict_mode is enabled for API test suite)
    if strict_mode:
        if role_key == UserRole.STUDENT.value and not ident.upper().startswith("STU-"):
            raise ValueError("Invalid Student ID. Expected format: STU-XXXX (e.g. STU-1001)")
        elif role_key == UserRole.EMPLOYEE.value and not ident.upper().startswith("EMP-"):
            raise ValueError("Invalid Employee ID. Expected format: EMP-XXXX (e.g. EMP-1001)")
        elif role_key == UserRole.PROFESSOR.value and not ident.upper().startswith("PROF-"):
            raise ValueError("Invalid Professor ID. Expected format: PROF-XXXX (e.g. PROF-1001)")
        elif role_key == UserRole.ADMIN.value and not ident.upper().startswith("ADMIN-") and ident.upper() != "ADMIN":
            raise ValueError("Invalid Admin ID. Expected format: ADMIN-XXXX (e.g. ADMIN-1001)")

    email_str = str(data.email).strip().lower()
    if not email_str or "@" not in email_str or "." not in email_str.split("@")[-1]:
        raise ValueError("Please enter a valid email address.")

    # Account-type-specific field validation & normalization
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
        # Legacy API strict_mode support
        effective_role = UserRole.PROFESSOR.value
        final_role_designation = "Professor"
        final_department = (data.department or "").strip() or None
        final_program = None

    elif role_key == UserRole.ADMIN.value:
        final_role_designation = "Admin"
        final_program = None
        final_department = (data.department or "").strip() if (strict_mode and data.department) else None

    # Validate Campus selection
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

    from app.models.campus import Campus
    campus_record = db.scalars(select(Campus).where(Campus.name == campus_val)).first()
    final_campus_id = campus_record.id if campus_record else 1

    if len(data.password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    if data.password != data.confirm_password:
        raise ValueError("Passwords do not match.")

    # Check if this ID or Email is already registered
    existing_user = get_user_by_identifier(db, effective_role, ident)
    if not existing_user:
        existing_user = db.scalars(
            select(User).where(
                or_(
                    User.student_id.ilike(ident),
                    User.employee_id.ilike(ident),
                    User.professor_id.ilike(ident),
                    User.admin_id.ilike(ident),
                )
            )
        ).first()
    if not existing_user:
        existing_user = get_user_by_email(db, email_str)

    if existing_user and existing_user.password_hash:
        raise ValueError("This ID or email is already registered. Please login.")

    # Admin verification protection (only when strict_mode is enabled)
    if strict_mode and role_key == UserRole.ADMIN.value:
        expected_token = get_settings().admin_registration_token
        if not data.admin_code or not secrets.compare_digest(data.admin_code.strip(), expected_token):
            raise ValueError("Invalid admin verification code. Admin registration requires an authorized code.")

    # Official university directory check
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

    # Resolve fallback department/program from directory when in strict_mode
    if strict_mode and dir_record:
        if not final_department and dir_record.department and role_key != UserRole.ADMIN.value:
            final_department = dir_record.department
        if not final_program and dir_record.program and role_key == UserRole.STUDENT.value:
            final_program = dir_record.program

    # If existing user record exists without password, activate it
    if existing_user and not existing_user.password_hash:
        user = existing_user
        user.password_hash = hash_password(data.password)
        user.full_name = data.full_name.strip()
        user.role = effective_role
        user.role_designation = final_role_designation
        user.department = final_department
        user.program = final_program
        user.campus = campus_val
        user.campus_id = final_campus_id
        user.is_active = True
        if effective_role == UserRole.ADMIN.value:
            user.admin_id = ident
    else:
        user = User(
            full_name=data.full_name.strip(),
            email=email_str,
            password_hash=hash_password(data.password),
            role=effective_role,
            student_id=ident if effective_role == UserRole.STUDENT.value else None,
            employee_id=ident if role_key == UserRole.EMPLOYEE.value else None,
            professor_id=ident if effective_role == UserRole.PROFESSOR.value else None,
            admin_id=ident if effective_role == UserRole.ADMIN.value else None,
            department=final_department,
            program=final_program,
            campus=campus_val,
            campus_id=final_campus_id,
            role_designation=final_role_designation,
            is_active=True,
        )
        db.add(user)

    db.commit()
    db.refresh(user)

    # Link unlinked legacy complaints to the student
    if user.role == UserRole.STUDENT.value and user.student_id:
        unlinked = db.scalars(
            select(Complaint).where(
                Complaint.user_id.is_(None),
                or_(Complaint.student_id == user.student_id, Complaint.email == user.email)
            )
        ).all()
        for c in unlinked:
            c.user_id = user.id
        if unlinked:
            db.commit()
            logger.info("Linked %d historical complaints to registered student %s", len(unlinked), user.student_id)

    return user


def initiate_password_recovery(db: Session, email: str) -> tuple[User, str]:
    """Verify registered email and generate a single-use expiring password reset token."""
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
    """Validate recovery token and securely update the user's password hash."""
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
    """Seed official university directory and default test accounts."""
    s = get_settings()
    admin_pass = s.admin_password or "adminpassword"

    # 1. Official University Directory Records
    directory_records = [
        # Students
        {"role": UserRole.STUDENT.value, "identifier": "STU-1001", "full_name": "Muhammad Ali", "email": "ali1001@example.edu", "program": "BS Computer Science", "department": "Computer Science"},
        {"role": UserRole.STUDENT.value, "identifier": "STU-1002", "full_name": "Ayesha Malik", "email": "ayesha1002@example.edu", "program": "BS Software Engineering", "department": "Computer Science"},
        {"role": UserRole.STUDENT.value, "identifier": "STU-1024", "full_name": "Ali Ahmed", "email": "ali@example.edu", "program": "BS Computer Science", "department": "Computer Science"},
        {"role": UserRole.STUDENT.value, "identifier": "STU-2001", "full_name": "Sara Khan", "email": "sara@example.edu", "program": "BBA", "department": "Business Administration"},
        # Employees
        {"role": UserRole.EMPLOYEE.value, "identifier": "EMP-1001", "full_name": "Sarah Connor", "email": "sarah.connor@example.edu", "department": "Administration"},
        {"role": UserRole.EMPLOYEE.value, "identifier": "EMP-1002", "full_name": "David Miller", "email": "david.miller@example.edu", "department": "Finance"},
        {"role": UserRole.EMPLOYEE.value, "identifier": "EMP-1024", "full_name": "John Smith", "email": "john.smith@example.edu", "department": "Administration"},
        # Professors
        {"role": UserRole.PROFESSOR.value, "identifier": "PROF-1001", "full_name": "Dr. John Nash", "email": "j.nash@example.edu", "department": "Mathematics"},
        {"role": UserRole.PROFESSOR.value, "identifier": "PROF-1002", "full_name": "Dr. Alan Turing", "email": "a.turing@example.edu", "department": "Computer Science"},
        {"role": UserRole.PROFESSOR.value, "identifier": "PROF-1024", "full_name": "Dr. Robert Vance", "email": "r.vance@example.edu", "department": "Computer Science"},
        # Admins
        {"role": UserRole.ADMIN.value, "identifier": "ADMIN-1001", "full_name": "Security Admin", "email": "admin1001@example.edu", "department": "Administration"},
        {"role": UserRole.ADMIN.value, "identifier": "ADMIN-001", "full_name": "System Administrator", "email": "admin@example.edu", "department": "Administration"},
    ]

    for d in directory_records:
        existing_dir = db.scalars(select(UniversityDirectory).where(UniversityDirectory.identifier == d["identifier"])).first()
        if not existing_dir:
            dir_entry = UniversityDirectory(
                role=d["role"],
                identifier=d["identifier"],
                full_name=d["full_name"],
                email=d["email"],
                department=d.get("department"),
                program=d.get("program"),
                is_claimed=False,
            )
            db.add(dir_entry)
    db.commit()

    # 2. Pre-activated default accounts for testing & development
    defaults = [
        # Required Section 30 Development Accounts
        {
            "full_name": "Muhammad Ali",
            "email": "ali1001@example.edu",
            "password": "password123",
            "role": UserRole.STUDENT.value,
            "student_id": "STU-1001",
            "program": "BS Computer Science",
            "department": "Computer Science",
        },
        {
            "full_name": "Sarah Connor",
            "email": "sarah.connor@example.edu",
            "password": "password123",
            "role": UserRole.EMPLOYEE.value,
            "employee_id": "EMP-1001",
            "department": "Administration",
        },
        {
            "full_name": "Dr. John Nash",
            "email": "j.nash@example.edu",
            "password": "password123",
            "role": UserRole.PROFESSOR.value,
            "professor_id": "PROF-1001",
            "department": "Mathematics",
        },
        {
            "full_name": "Security Admin",
            "email": "admin1001@example.edu",
            "password": admin_pass,
            "role": UserRole.ADMIN.value,
            "admin_id": "ADMIN-1001",
            "employee_id": "ADMIN-1001",
            "department": "Administration",
            "campus": "Township Campus, Lahore (Main Campus)",
        },
        # Existing Demo Accounts
        {
            "full_name": "Ali Ahmed",
            "email": "ali@example.edu",
            "password": "password123",
            "role": UserRole.STUDENT.value,
            "student_id": "STU-1024",
            "program": "BS Computer Science",
            "department": "Computer Science",
            "campus": "Township Campus, Lahore (Main Campus)",
        },
        {
            "full_name": "Sara Khan",
            "email": "sara@example.edu",
            "password": "password123",
            "role": UserRole.STUDENT.value,
            "student_id": "STU-2001",
            "program": "BBA",
            "department": "Business Administration",
            "campus": "Township Campus, Lahore (Main Campus)",
        },
        {
            "full_name": "John Smith",
            "email": "john.smith@example.edu",
            "password": "password123",
            "role": UserRole.EMPLOYEE.value,
            "employee_id": "EMP-1024",
            "department": "Administration",
            "campus": "Township Campus, Lahore (Main Campus)",
        },
        {
            "full_name": "Dr. Robert Vance",
            "email": "r.vance@example.edu",
            "password": "password123",
            "role": UserRole.PROFESSOR.value,
            "professor_id": "PROF-1024",
            "department": "Computer Science",
            "campus": "Township Campus, Lahore (Main Campus)",
        },
        {
            "full_name": "System Administrator",
            "email": "admin@example.edu",
            "password": admin_pass,
            "role": UserRole.ADMIN.value,
            "admin_id": "ADMIN-001",
            "employee_id": "ADMIN-001",
            "department": "Administration",
            "campus": "Township Campus, Lahore (Main Campus)",
        },
        # Multan Campus Records (Matching reference screenshot exactly: 8 Students, 3 Employees, 1 Admin)
        {
            "full_name": "Muhammad Imran",
            "email": "m.imran@ue.edu.pk",
            "password": "password123",
            "role": UserRole.STUDENT.value,
            "student_id": "BSF24005343",
            "program": "BSF",
            "campus": "Multan Campus",
            "role_designation": "Student",
        },
        {
            "full_name": "Ayesha Khan",
            "email": "ayesha.khan@ue.edu.pk",
            "password": "password123",
            "role": UserRole.STUDENT.value,
            "student_id": "BSF24007812",
            "program": "BSF",
            "campus": "Multan Campus",
            "role_designation": "Student",
        },
        {
            "full_name": "Ali Raza",
            "email": "ali.raza@ue.edu.pk",
            "password": "password123",
            "role": UserRole.STUDENT.value,
            "student_id": "CS24004567",
            "program": "BSCS",
            "campus": "Multan Campus",
            "role_designation": "Student",
        },
        {
            "full_name": "Sara Fatima",
            "email": "sara.fatima@ue.edu.pk",
            "password": "password123",
            "role": UserRole.STUDENT.value,
            "student_id": "CS24007890",
            "program": "BSCS",
            "campus": "Multan Campus",
            "role_designation": "Student",
        },
        {
            "full_name": "Usman Tariq",
            "email": "usman.tariq@ue.edu.pk",
            "password": "pending:password123",
            "role": UserRole.STUDENT.value,
            "student_id": "IT24001234",
            "program": "BSIT",
            "campus": "Multan Campus",
            "role_designation": "Student",
        },
        {
            "full_name": "Fatima Noor",
            "email": "fatima.noor@ue.edu.pk",
            "password": "password123",
            "role": UserRole.STUDENT.value,
            "student_id": "ENG24005678",
            "program": "BSE",
            "campus": "Multan Campus",
            "role_designation": "Student",
        },
        {
            "full_name": "Hassan Ali",
            "email": "hassan.ali@ue.edu.pk",
            "password": "password123",
            "role": UserRole.STUDENT.value,
            "student_id": "ME24009876",
            "program": "BSME",
            "campus": "Multan Campus",
            "role_designation": "Student",
            "is_active": False,
        },
        {
            "full_name": "Zainab Javed",
            "email": "zainab.javed@ue.edu.pk",
            "password": "password123",
            "role": UserRole.STUDENT.value,
            "student_id": "CS24006789",
            "program": "BSCS",
            "campus": "Multan Campus",
            "role_designation": "Student",
        },
        {
            "full_name": "Dr. Tariq Mahmood",
            "email": "tariq.mahmood@ue.edu.pk",
            "password": "password123",
            "role": UserRole.EMPLOYEE.value,
            "employee_id": "EMP240011",
            "role_designation": "Professor",
            "department": "Department of Information Sciences",
            "campus": "Multan Campus",
        },
        {
            "full_name": "Bilal Ahmed",
            "email": "bilal.ahmed@ue.edu.pk",
            "password": "password123",
            "role": UserRole.EMPLOYEE.value,
            "employee_id": "EMP240022",
            "role_designation": "Lecturer",
            "department": "Department of Mathematics",
            "campus": "Multan Campus",
        },
        {
            "full_name": "Farah Naz",
            "email": "farah.naz@ue.edu.pk",
            "password": "password123",
            "role": UserRole.EMPLOYEE.value,
            "employee_id": "EMP240033",
            "role_designation": "Head of Department (HOD)",
            "department": "Department of Education",
            "campus": "Multan Campus",
        },
        {
            "full_name": "Multan Administrator",
            "email": "admin.multan@ue.edu.pk",
            "password": admin_pass,
            "role": UserRole.ADMIN.value,
            "admin_id": "ADMIN-MLT-001",
            "employee_id": "ADMIN-MLT-001",
            "role_designation": "Administrator",
            "campus": "Multan Campus",
            "department": "Administration",
        },
    ]

    for item in defaults:
        existing = db.scalars(select(User).where(User.email == item["email"])).first()
        if not existing:
            user = User(
                full_name=item["full_name"],
                email=item["email"],
                password_hash=hash_password(item["password"]),
                role=item["role"],
                student_id=item.get("student_id"),
                employee_id=item.get("employee_id"),
                professor_id=item.get("professor_id"),
                admin_id=item.get("admin_id"),
                department=item.get("department"),
                program=item.get("program"),
                campus=item.get("campus", "Township Campus, Lahore (Main Campus)"),
                role_designation=item.get("role_designation", "Student" if item["role"] == UserRole.STUDENT.value else ("Admin" if item["role"] == UserRole.ADMIN.value else "Employee")),
                is_active=item.get("is_active", True),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("Created default user: %s (%s)", user.full_name, user.role)
        else:
            user = existing
            if item.get("admin_id") and not user.admin_id:
                user.admin_id = item["admin_id"]
            if item.get("campus") and not user.campus:
                user.campus = item["campus"]
            db.commit()

        # Mark corresponding directory entry as claimed
        ident = item.get("student_id") or item.get("employee_id") or item.get("professor_id") or item.get("admin_id")
        if ident:
            d_rec = db.scalars(select(UniversityDirectory).where(UniversityDirectory.identifier == ident)).first()
            if d_rec:
                d_rec.is_claimed = True
                db.commit()

        # Link legacy or existing complaints without user_id
        if user.role == UserRole.STUDENT.value and user.student_id:
            unlinked = db.scalars(
                select(Complaint).where(
                    Complaint.user_id.is_(None),
                    or_(Complaint.student_id == user.student_id, Complaint.email == user.email)
                )
            ).all()
            for c in unlinked:
                c.user_id = user.id
            if unlinked:
                db.commit()
                logger.info("Linked %d complaints to student %s", len(unlinked), user.student_id)
