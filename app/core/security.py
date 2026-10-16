"""Authentication helpers (JWT/Session tokens, PBKDF2 password hashing, RBAC) and CSRF protection."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.database import get_db
from app.models.enums import UserRole
from app.models.user import User

logger = logging.getLogger("complaint_agent.security")

_basic = HTTPBasic(auto_error=False, realm="Complaint Admin")
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AdminUser:
    username: str
    role: str = "admin"


# ---------------- Password Hashing (PBKDF2-HMAC-SHA256) ----------------
def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${dk.hex()}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        salt, hash_val = password_hash.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100_000)
        return secrets.compare_digest(dk.hex(), hash_val)
    except Exception:
        return False


# ---------------- Session / Access Tokens ----------------
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def create_access_token(data: dict, expires_in_seconds: int = 86400 * 7) -> str:
    secret_key = get_settings().secret_key
    payload = dict(data)
    payload["exp"] = int(time.time()) + expires_in_seconds
    raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    encoded_payload = _b64url_encode(raw_payload)
    sig = hmac.new(secret_key.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_b64url_encode(sig)}"


def decode_access_token(token: str, secret_key: Optional[str] = None) -> Optional[dict]:
    key = secret_key or get_settings().secret_key
    parts = token.split(".")
    if len(parts) != 2:
        return None
    encoded_payload, encoded_sig = parts
    expected_sig = _b64url_encode(hmac.new(key.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest())
    if not hmac.compare_digest(encoded_sig, expected_sig):
        return None
    try:
        payload = json.loads(_b64url_decode(encoded_payload).decode("utf-8"))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ---------------- Authentication & RBAC ----------------
def authenticate_user(db: Session, account_type: str, identifier: str, password: str) -> Optional[User]:
    if not account_type or not account_type.strip() or account_type.strip().lower() in ("", "select account type", "none"):
        return None
    role_key = account_type.strip().upper()
    ident = identifier.strip()
    if not ident or not password:
        return None

    if role_key == UserRole.STUDENT.value:
        stmt = select(User).where(
            User.role == UserRole.STUDENT.value,
            User.is_active.is_(True),
            or_(User.student_id.ilike(ident), User.email.ilike(ident)),
        )
    elif role_key == UserRole.EMPLOYEE.value:
        stmt = select(User).where(
            User.role.in_([UserRole.EMPLOYEE.value, UserRole.PROFESSOR.value]),
            User.is_active.is_(True),
            or_(User.employee_id.ilike(ident), User.professor_id.ilike(ident), User.email.ilike(ident)),
        )
    elif role_key == UserRole.PROFESSOR.value:
        stmt = select(User).where(
            User.role.in_([UserRole.PROFESSOR.value, UserRole.EMPLOYEE.value]),
            User.is_active.is_(True),
            or_(User.professor_id.ilike(ident), User.employee_id.ilike(ident), User.email.ilike(ident)),
        )
    elif role_key == UserRole.ADMIN.value:
        admin_conds = [
            User.admin_id.ilike(ident),
            User.employee_id.ilike(ident),
            User.email.ilike(ident),
            User.full_name.ilike(ident),
        ]
        if ident.lower() in ("admin", "admin-001", "admin-1001"):
            admin_conds.append(User.role == UserRole.ADMIN.value)
        stmt = select(User).where(
            User.role == UserRole.ADMIN.value,
            User.is_active.is_(True),
            or_(*admin_conds),
        )
    else:
        return None

    user = db.scalars(stmt).first()
    if not user:
        return None

    if verify_password(password, user.password_hash):
        return user

    # Admin fallback against settings password
    s = get_settings()
    if user.role == UserRole.ADMIN.value and s.admin_password and secrets.compare_digest(password, s.admin_password):
        return user

    return None


def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    basic_creds: Optional[HTTPBasicCredentials] = Depends(_basic),
    db: Session = Depends(get_db),
) -> Optional[User]:
    # 1. Bearer header
    token = credentials.credentials if credentials else None

    # 2. Cookie
    if not token:
        token = request.cookies.get("complaint_session")

    if token:
        payload = decode_access_token(token)
        if payload and "sub" in payload:
            user = db.get(User, int(payload["sub"]))
            if user and user.is_active:
                return user

    # 3. HTTP Basic auth fallback
    if basic_creds:
        s = get_settings()
        admin_user = db.scalars(select(User).where(User.role == UserRole.ADMIN.value)).first()
        is_basic_ok = (
            secrets.compare_digest(basic_creds.username.encode(), s.admin_username.encode())
            and (not s.admin_password or secrets.compare_digest(basic_creds.password.encode(), s.admin_password.encode()))
        )
        if is_basic_ok and admin_user:
            return admin_user

    return None


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    basic_creds: Optional[HTTPBasicCredentials] = Depends(_basic),
    db: Session = Depends(get_db),
) -> User:
    user = get_current_user_optional(request, credentials, basic_creds, db)
    if user is not None:
        return user

    # If wrong HTTP Basic auth was sent, prompt / reject with 401
    if basic_creds:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentication required.",
            headers={"WWW-Authenticate": 'Basic realm="Complaint Admin"'},
        )

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required.")


def require_role(*roles: str):
    """Dependency factory for RBAC route protection."""
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden: Insufficient permissions.")
        return user
    return checker


require_student = require_role(UserRole.STUDENT.value)
require_employee = require_role(UserRole.EMPLOYEE.value)
require_professor = require_role(UserRole.PROFESSOR.value)
require_admin = require_role(UserRole.ADMIN.value)


def get_current_admin(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    basic_creds: Optional[HTTPBasicCredentials] = Depends(_basic),
    db: Session = Depends(get_db),
) -> User:
    """Protects admin routes. Checks token, cookie, or Basic auth."""
    # Check Basic Auth explicitly if sent
    if basic_creds:
        s = get_settings()
        is_basic_ok = (
            secrets.compare_digest(basic_creds.username.encode(), s.admin_username.encode())
            and (not s.admin_password or secrets.compare_digest(basic_creds.password.encode(), s.admin_password.encode()))
        )
        if not is_basic_ok:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Authentication required.",
                headers={"WWW-Authenticate": 'Basic realm="Complaint Admin"'},
            )
        admin_user = db.scalars(select(User).where(User.role == UserRole.ADMIN.value)).first()
        if admin_user:
            return admin_user
        # Return fallback AdminUser-compatible instance if db has no admin user
        return User(id=1, full_name="Admin", email="admin@example.edu", password_hash="", role="ADMIN", employee_id="ADMIN-001")

    user = get_current_user_optional(request, credentials, basic_creds, db)
    if not user:
        # Dev fallback if admin password is empty
        s = get_settings()
        if not s.admin_password:
            admin_user = db.scalars(select(User).where(User.role == UserRole.ADMIN.value)).first()
            if admin_user:
                return admin_user
            return User(id=1, full_name="Admin", email="admin@example.edu", password_hash="", role="ADMIN", employee_id="ADMIN-001")

        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentication required.",
            headers={"WWW-Authenticate": 'Basic realm="Complaint Admin"'},
        )

    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden: Only administrators can access this resource.")

    return user


# ---------------- CSRF & Same-Origin Defence ----------------
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "testserver"}


def _normalize_host(netloc: str) -> str:
    netloc = netloc.strip().lower()
    if "://" in netloc:
        netloc = urlparse(netloc).netloc.lower()
    return netloc


def _hosts_match(origin_netloc: str, request_host: str) -> bool:
    origin_netloc = _normalize_host(origin_netloc)
    request_host = _normalize_host(request_host)
    if not origin_netloc or not request_host:
        return False
    if origin_netloc == request_host:
        return True

    o_host, _, o_port = origin_netloc.partition(":")
    r_host, _, r_port = request_host.partition(":")

    if o_host in _LOOPBACK_HOSTS and r_host in _LOOPBACK_HOSTS:
        return True

    if o_host == r_host:
        if not o_port or not r_port or o_port in ("80", "443") or r_port in ("80", "443"):
            return True

    return False


def verify_same_origin(request: Request) -> None:
    """Basic CSRF defence for browser form posts."""
    origin = request.headers.get("origin")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")

    if origin == "null":
        referer = request.headers.get("referer")
        if referer:
            ref_netloc = urlparse(referer).netloc
            if not _hosts_match(ref_netloc, host):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-origin request rejected.")
        else:
            req_host_only = _normalize_host(host).partition(":")[0]
            if not (req_host_only in _LOOPBACK_HOSTS):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-origin request rejected.")
        return

    if origin:
        origin_netloc = urlparse(origin).netloc
        if not _hosts_match(origin_netloc, host):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-origin request rejected.")
        return

    referer = request.headers.get("referer")
    if referer:
        ref_netloc = urlparse(referer).netloc
        if not _hosts_match(ref_netloc, host):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-origin request rejected.")
