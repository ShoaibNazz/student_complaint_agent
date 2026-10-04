from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: str
    student_id: Optional[str] = None
    employee_id: Optional[str] = None
    professor_id: Optional[str] = None
    admin_id: Optional[str] = None
    department: Optional[str] = None
    program: Optional[str] = None
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    role: UserRole = UserRole.STUDENT
    student_id: Optional[str] = Field(default=None, max_length=60)
    employee_id: Optional[str] = Field(default=None, max_length=60)
    professor_id: Optional[str] = Field(default=None, max_length=60)
    admin_id: Optional[str] = Field(default=None, max_length=60)
    department: Optional[str] = Field(default=None, max_length=120)
    program: Optional[str] = Field(default=None, max_length=120)


class UserRegisterRequest(BaseModel):
    account_type: str = Field(description="STUDENT, EMPLOYEE, PROFESSOR, or ADMIN")
    identifier: str = Field(min_length=2, max_length=60, description="Role ID e.g. STU-1001, EMP-1001, etc.")
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    confirm_password: str = Field(min_length=6, max_length=100)
    department: Optional[str] = Field(default=None, max_length=120)
    program: Optional[str] = Field(default=None, max_length=120)
    admin_code: Optional[str] = Field(default=None, description="Required for ADMIN account registration")


class RegisterResponse(BaseModel):
    message: str = "Registration successful. You can now login."
    user: UserOut


class LoginRequest(BaseModel):
    account_type: str = Field(description="STUDENT, EMPLOYEE, PROFESSOR, or ADMIN")
    identifier: str = Field(description="Student ID, Employee ID, Professor ID, or Admin ID/Username")
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
