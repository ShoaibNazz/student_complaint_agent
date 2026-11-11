from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.enums import UserRole
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.campus import Campus, DepartmentRecord
    from app.models.complaint import Complaint


class User(Base):
    """Central authentication and identity entity for all portal actors."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.STUDENT.value, index=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    campus_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campuses.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    avatar_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # 1:1 Relational Profiles
    student_profile: Mapped[Optional["Student"]] = relationship(
        "Student", back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="joined"
    )
    employee_profile: Mapped[Optional["Employee"]] = relationship(
        "Employee", back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="joined"
    )
    admin_profile: Mapped[Optional["Admin"]] = relationship(
        "Admin", back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="joined"
    )

    # Foreign key references
    campus_rel: Mapped[Optional["Campus"]] = relationship(
        "Campus", foreign_keys=[campus_id], lazy="joined"
    )
    complaints: Mapped[list["Complaint"]] = relationship(
        "Complaint", back_populates="user", cascade="all, delete-orphan"
    )

    # ---- Backward-Compatible Hybrid Properties ----
    @hybrid_property
    def student_id(self) -> Optional[str]:
        return self.student_profile.student_id if self.student_profile else None

    @student_id.setter
    def student_id(self, val: Optional[str]) -> None:
        if self.student_profile:
            self.student_profile.student_id = val or ""
        elif val:
            self.student_profile = Student(user=self, student_id=val)

    @student_id.expression
    def student_id(cls):
        return (
            select(Student.student_id)
            .where(Student.user_id == cls.id)
            .correlate_except(Student)
            .scalar_subquery()
        )

    @hybrid_property
    def employee_id(self) -> Optional[str]:
        return self.employee_profile.employee_id if self.employee_profile else None

    @employee_id.setter
    def employee_id(self, val: Optional[str]) -> None:
        if self.employee_profile:
            self.employee_profile.employee_id = val or ""
        elif val:
            self.employee_profile = Employee(user=self, employee_id=val)

    @employee_id.expression
    def employee_id(cls):
        return (
            select(Employee.employee_id)
            .where(Employee.user_id == cls.id)
            .correlate_except(Employee)
            .scalar_subquery()
        )

    @hybrid_property
    def professor_id(self) -> Optional[str]:
        if self.employee_profile and self.employee_profile.is_faculty:
            return self.employee_profile.employee_id
        return self.employee_profile.employee_id if self.employee_profile else None

    @professor_id.setter
    def professor_id(self, val: Optional[str]) -> None:
        if self.employee_profile:
            self.employee_profile.employee_id = val or ""
            self.employee_profile.is_faculty = True
        elif val:
            self.employee_profile = Employee(user=self, employee_id=val, is_faculty=True, role_designation="Professor")

    @professor_id.expression
    def professor_id(cls):
        return (
            select(Employee.employee_id)
            .where(Employee.user_id == cls.id)
            .correlate_except(Employee)
            .scalar_subquery()
        )

    @hybrid_property
    def admin_id(self) -> Optional[str]:
        return self.admin_profile.admin_id if self.admin_profile else None

    @admin_id.setter
    def admin_id(self, val: Optional[str]) -> None:
        if self.admin_profile:
            self.admin_profile.admin_id = val or ""
        elif val:
            self.admin_profile = Admin(user=self, admin_id=val)

    @admin_id.expression
    def admin_id(cls):
        return (
            select(Admin.admin_id)
            .where(Admin.user_id == cls.id)
            .correlate_except(Admin)
            .scalar_subquery()
        )

    @hybrid_property
    def campus(self) -> Optional[str]:
        return self.campus_rel.name if self.campus_rel else None

    @campus.setter
    def campus(self, val: Optional[str]) -> None:
        # Campus string assignment will be normalized in services by setting campus_id
        pass

    @campus.expression
    def campus(cls):
        from app.models.campus import Campus
        return (
            select(Campus.name)
            .where(Campus.id == cls.campus_id)
            .correlate_except(Campus)
            .scalar_subquery()
        )

    @hybrid_property
    def department(self) -> Optional[str]:
        if self.employee_profile and self.employee_profile.department:
            return self.employee_profile.department.name
        return None

    @department.setter
    def department(self, val: Optional[str]) -> None:
        pass

    @department.expression
    def department(cls):
        from app.models.campus import DepartmentRecord
        return (
            select(DepartmentRecord.name)
            .select_from(Employee)
            .join(DepartmentRecord, Employee.department_id == DepartmentRecord.id)
            .where(Employee.user_id == cls.id)
            .correlate_except(Employee, DepartmentRecord)
            .scalar_subquery()
        )

    @hybrid_property
    def program(self) -> Optional[str]:
        return self.student_profile.program if self.student_profile else None

    @program.setter
    def program(self, val: Optional[str]) -> None:
        if self.student_profile:
            self.student_profile.program = val
        elif val:
            self.student_profile = Student(user=self, student_id="", program=val)

    @program.expression
    def program(cls):
        return (
            select(Student.program)
            .where(Student.user_id == cls.id)
            .correlate_except(Student)
            .scalar_subquery()
        )

    @hybrid_property
    def role_designation(self) -> Optional[str]:
        if self.employee_profile:
            return self.employee_profile.role_designation
        if self.admin_profile:
            return self.admin_profile.designation
        if self.role == UserRole.STUDENT.value:
            return "Student"
        return "User"

    @role_designation.setter
    def role_designation(self, val: Optional[str]) -> None:
        if self.employee_profile:
            self.employee_profile.role_designation = val or "Employee"
        elif self.admin_profile:
            self.admin_profile.designation = val or "System Administrator"

    @role_designation.expression
    def role_designation(cls):
        return (
            select(Employee.role_designation)
            .where(Employee.user_id == cls.id)
            .correlate_except(Employee)
            .scalar_subquery()
        )

    @property
    def identifier(self) -> str:
        if self.role == UserRole.STUDENT.value:
            return self.student_id or self.email
        if self.role == UserRole.EMPLOYEE.value:
            return self.employee_id or self.email
        if self.role == UserRole.PROFESSOR.value:
            return self.professor_id or self.employee_id or self.email
        return self.admin_id or self.employee_id or "ADMIN-001"

    @property
    def username(self) -> str:
        return self.identifier


class Student(Base):
    """1:1 Relational profile for enrolled students."""
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    student_id: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    program: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    batch_year: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="student_profile")


class Employee(Base):
    """1:1 Relational profile for university employees, staff, and faculty."""
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    employee_id: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    role_designation: Mapped[str] = mapped_column(String(120), default="Employee", nullable=False)
    is_faculty: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="employee_profile")
    department: Mapped[Optional["DepartmentRecord"]] = relationship("DepartmentRecord", back_populates="employees")


class Admin(Base):
    """1:1 Relational profile for portal administrators."""
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    admin_id: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    designation: Mapped[str] = mapped_column(String(120), default="System Administrator", nullable=False)
    permission_level: Mapped[str] = mapped_column(String(40), default="SUPER_ADMIN", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="admin_profile")


class UniversityDirectory(Base):
    """Official university roster of provisioned IDs before or after self-registration."""
    __tablename__ = "university_directory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    identifier: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    department: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    program: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    campus_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campuses.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    campus: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    role_designation: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_claimed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
