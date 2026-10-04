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


def create_user(db: Session, data: UserCreate) -> User:
    role_str = data.role.value if isinstance(data.role, UserRole) else str(data.role)
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
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def register_user(db: Session, data: UserRegisterRequest) -> User:
    """Validate and register a new portal account with identity verification."""
    if not data.account_type or data.account_type.strip().lower() in ("", "select account type", "none"):
        raise ValueError("Please select your account type.")

    role_key = data.account_type.strip().upper()
    if role_key not in (UserRole.STUDENT.value, UserRole.EMPLOYEE.value, UserRole.PROFESSOR.value, UserRole.ADMIN.value):
        raise ValueError("Please select your account type.")

    ident = data.identifier.strip().upper()
    if not ident:
        raise ValueError(f"Please enter your {role_key.title()} ID.")

    # Role ID format validation
    if role_key == UserRole.STUDENT.value and not ident.startswith("STU-"):
        raise ValueError("Invalid Student ID. Expected format: STU-XXXX (e.g. STU-1001)")
    elif role_key == UserRole.EMPLOYEE.value and not ident.startswith("EMP-"):
        raise ValueError("Invalid Employee ID. Expected format: EMP-XXXX (e.g. EMP-1001)")
    elif role_key == UserRole.PROFESSOR.value and not ident.startswith("PROF-"):
        raise ValueError("Invalid Professor ID. Expected format: PROF-XXXX (e.g. PROF-1001)")
    elif role_key == UserRole.ADMIN.value and not ident.startswith("ADMIN-") and ident != "ADMIN":
        raise ValueError("Invalid Admin ID. Expected format: ADMIN-XXXX (e.g. ADMIN-1001)")

    if not data.full_name or not data.full_name.strip():
        raise ValueError("Please enter your name.")

    email_str = str(data.email).strip().lower()
    if not email_str or "@" not in email_str:
        raise ValueError("Please enter a valid email address.")

    if len(data.password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    if data.password != data.confirm_password:
        raise ValueError("Passwords do not match.")

    # Check if this ID or Email is already registered
    existing_user = get_user_by_identifier(db, role_key, ident)
    if not existing_user:
        existing_user = get_user_by_email(db, email_str)

    if existing_user and existing_user.password_hash:
        raise ValueError("This ID is already registered. Please login.")

    # Admin verification protection: requires admin verification code
    if role_key == UserRole.ADMIN.value:
        expected_token = get_settings().admin_registration_token
        if not data.admin_code or not secrets.compare_digest(data.admin_code.strip(), expected_token):
            raise ValueError("Invalid admin verification code. Admin registration requires an authorized code.")

    # Official university directory check
    dir_record = get_directory_entry(db, ident)
    if dir_record:
        if dir_record.role != role_key:
            raise ValueError(f"This ID is registered as a {dir_record.role.title()}, not {role_key.title()}.")
        # Anti-impersonation check: verify that provided email or name matches university record
        email_match = dir_record.email.lower() == email_str
        name_match = dir_record.full_name.lower() == data.full_name.strip().lower()
        if not (email_match or name_match):
            raise ValueError("The provided name or email does not match official university records for this ID.")
        dir_record.is_claimed = True
    else:
        # Create directory record for uncatalogued new registration
        new_dir = UniversityDirectory(
            role=role_key,
            identifier=ident,
            full_name=data.full_name.strip(),
            email=email_str,
            department=data.department.strip() if data.department else None,
            program=data.program.strip() if data.program else None,
            is_claimed=True,
        )
        db.add(new_dir)

    # If existing user record exists without password, activate it
    if existing_user and not existing_user.password_hash:
        user = existing_user
        user.password_hash = hash_password(data.password)
        user.full_name = data.full_name.strip()
        user.is_active = True
        if role_key == UserRole.ADMIN.value:
            user.admin_id = ident
    else:
        user = User(
            full_name=data.full_name.strip(),
            email=email_str,
            password_hash=hash_password(data.password),
            role=role_key,
            student_id=ident if role_key == UserRole.STUDENT.value else None,
            employee_id=ident if role_key in (UserRole.EMPLOYEE.value, UserRole.ADMIN.value) else None,
            professor_id=ident if role_key == UserRole.PROFESSOR.value else None,
            admin_id=ident if role_key == UserRole.ADMIN.value else None,
            department=data.department.strip() if data.department else (dir_record.department if dir_record else None),
            program=data.program.strip() if data.program else (dir_record.program if dir_record else None),
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
        },
        {
            "full_name": "Sara Khan",
            "email": "sara@example.edu",
            "password": "password123",
            "role": UserRole.STUDENT.value,
            "student_id": "STU-2001",
            "program": "BBA",
            "department": "Business Administration",
        },
        {
            "full_name": "John Smith",
            "email": "john.smith@example.edu",
            "password": "password123",
            "role": UserRole.EMPLOYEE.value,
            "employee_id": "EMP-1024",
            "department": "Administration",
        },
        {
            "full_name": "Dr. Robert Vance",
            "email": "r.vance@example.edu",
            "password": "password123",
            "role": UserRole.PROFESSOR.value,
            "professor_id": "PROF-1024",
            "department": "Computer Science",
        },
        {
            "full_name": "System Administrator",
            "email": "admin@example.edu",
            "password": admin_pass,
            "role": UserRole.ADMIN.value,
            "admin_id": "ADMIN-001",
            "employee_id": "ADMIN-001",
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
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("Created default user: %s (%s)", user.full_name, user.role)
        else:
            user = existing
            if item.get("admin_id") and not user.admin_id:
                user.admin_id = item["admin_id"]
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
