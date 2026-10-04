from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    STUDENT = "STUDENT"
    EMPLOYEE = "EMPLOYEE"
    PROFESSOR = "PROFESSOR"
    ADMIN = "ADMIN"


class ComplaintStatus(str, Enum):
    NEW = "NEW"
    UNDER_REVIEW = "UNDER_REVIEW"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_STUDENT = "WAITING_FOR_STUDENT"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


OPEN_STATUSES = (
    ComplaintStatus.NEW, ComplaintStatus.UNDER_REVIEW, ComplaintStatus.ASSIGNED,
    ComplaintStatus.IN_PROGRESS, ComplaintStatus.WAITING_FOR_STUDENT,
)
FINISHED_STATUSES = (ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED, ComplaintStatus.REJECTED)

VALID_STATUS_TRANSITIONS: dict[ComplaintStatus, set[ComplaintStatus]] = {
    ComplaintStatus.NEW: {ComplaintStatus.UNDER_REVIEW, ComplaintStatus.ASSIGNED, ComplaintStatus.REJECTED},
    ComplaintStatus.UNDER_REVIEW: {ComplaintStatus.ASSIGNED, ComplaintStatus.IN_PROGRESS, ComplaintStatus.WAITING_FOR_STUDENT, ComplaintStatus.REJECTED},
    ComplaintStatus.ASSIGNED: {ComplaintStatus.IN_PROGRESS, ComplaintStatus.UNDER_REVIEW, ComplaintStatus.WAITING_FOR_STUDENT, ComplaintStatus.RESOLVED},
    ComplaintStatus.IN_PROGRESS: {ComplaintStatus.WAITING_FOR_STUDENT, ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED, ComplaintStatus.UNDER_REVIEW},
    ComplaintStatus.WAITING_FOR_STUDENT: {ComplaintStatus.IN_PROGRESS, ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED},
    ComplaintStatus.RESOLVED: {ComplaintStatus.CLOSED, ComplaintStatus.IN_PROGRESS},
    ComplaintStatus.CLOSED: {ComplaintStatus.IN_PROGRESS, ComplaintStatus.UNDER_REVIEW},
    ComplaintStatus.REJECTED: {ComplaintStatus.UNDER_REVIEW},
}



class AnalysisStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return _RANK[self.value]

    @classmethod
    def parse(cls, value: "str | Priority | None", default: "Priority | None" = None) -> "Priority | None":
        if isinstance(value, Priority):
            return value
        try:
            return cls(str(value).strip().upper())
        except ValueError:
            return default


_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def max_priority(*items: Priority | None) -> Priority:
    present = [p for p in items if p is not None]
    return max(present, key=lambda p: p.rank) if present else Priority.LOW
