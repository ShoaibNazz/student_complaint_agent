from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base

if TYPE_CHECKING:
    from app.models.user import Employee


# Many-to-Many associative/junction table resolving Department <-> Campus relationship (M:N)
department_campuses = Table(
    "department_campuses",
    Base.metadata,
    Column(
        "department_id",
        Integer,
        ForeignKey("departments.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "campus_id",
        Integer,
        ForeignKey("campuses.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    ),
)


class Campus(Base):
    """University campus constituent entity."""
    __tablename__ = "campuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(40), unique=True, nullable=True, index=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    departments: Mapped[list["DepartmentRecord"]] = relationship(
        "DepartmentRecord",
        secondary=department_campuses,
        back_populates="campuses",
        lazy="selectin",
    )


class DepartmentRecord(Base):
    """Academic and administrative department entity."""
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(40), unique=True, nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    campuses: Mapped[list[Campus]] = relationship(
        "Campus",
        secondary=department_campuses,
        back_populates="departments",
        lazy="selectin",
    )
    employees: Mapped[list["Employee"]] = relationship(
        "Employee", back_populates="department", cascade="all, delete-orphan"
    )

    @property
    def campuses_served(self) -> str:
        """Dynamically computes campuses served from the relational M:N junction."""
        if not self.campuses:
            return "All Campuses"
        return ", ".join(c.name for c in self.campuses)
