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
    RESOLVED_AWAITING_CONFIRMATION = "RESOLVED_AWAITING_CONFIRMATION"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"
    REJECTED = "REJECTED"


OPEN_STATUSES = (
    ComplaintStatus.NEW,
    ComplaintStatus.UNDER_REVIEW,
    ComplaintStatus.ASSIGNED,
    ComplaintStatus.IN_PROGRESS,
    ComplaintStatus.WAITING_FOR_STUDENT,
    ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION,
    ComplaintStatus.REOPENED,
)
FINISHED_STATUSES = (ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED, ComplaintStatus.REJECTED)

VALID_STATUS_TRANSITIONS: dict[ComplaintStatus, set[ComplaintStatus]] = {
    ComplaintStatus.NEW: {ComplaintStatus.UNDER_REVIEW, ComplaintStatus.ASSIGNED, ComplaintStatus.REJECTED},
    ComplaintStatus.UNDER_REVIEW: {ComplaintStatus.ASSIGNED, ComplaintStatus.IN_PROGRESS, ComplaintStatus.WAITING_FOR_STUDENT, ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION, ComplaintStatus.RESOLVED, ComplaintStatus.REJECTED},
    ComplaintStatus.ASSIGNED: {ComplaintStatus.IN_PROGRESS, ComplaintStatus.UNDER_REVIEW, ComplaintStatus.WAITING_FOR_STUDENT, ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION, ComplaintStatus.RESOLVED},
    ComplaintStatus.IN_PROGRESS: {ComplaintStatus.WAITING_FOR_STUDENT, ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION, ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED, ComplaintStatus.UNDER_REVIEW},
    ComplaintStatus.WAITING_FOR_STUDENT: {ComplaintStatus.IN_PROGRESS, ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION, ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED},
    ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION: {ComplaintStatus.CLOSED, ComplaintStatus.RESOLVED, ComplaintStatus.REOPENED, ComplaintStatus.IN_PROGRESS},
    ComplaintStatus.RESOLVED: {ComplaintStatus.CLOSED, ComplaintStatus.IN_PROGRESS, ComplaintStatus.REOPENED},
    ComplaintStatus.CLOSED: {ComplaintStatus.IN_PROGRESS, ComplaintStatus.UNDER_REVIEW, ComplaintStatus.REOPENED},
    ComplaintStatus.REOPENED: {ComplaintStatus.UNDER_REVIEW, ComplaintStatus.ASSIGNED, ComplaintStatus.IN_PROGRESS, ComplaintStatus.RESOLVED_AWAITING_CONFIRMATION, ComplaintStatus.RESOLVED},
    ComplaintStatus.REJECTED: {ComplaintStatus.UNDER_REVIEW},
}


class RequestCategory(str, Enum):
    LEAVE = "Leave Application"
    TIMETABLE_ADJUSTMENT = "Timetable Adjustment"
    WORKLOAD_CHANGE = "Workload Change"
    PROMOTION_SERVICE = "Promotion / Service Matter"
    RESOURCE_REQUEST = "Resource Request"
    ADMINISTRATIVE_ASSISTANCE = "Administrative Assistance"
    OTHER = "Other Institutional Matter"


class RequestStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class NotificationType(str, Enum):
    COMPLAINT_ASSIGNED = "COMPLAINT_ASSIGNED"
    COMPLAINT_STATUS_UPDATE = "COMPLAINT_STATUS_UPDATE"
    RESOLUTION_AWAITING_CONFIRMATION = "RESOLUTION_AWAITING_CONFIRMATION"
    COMPLAINT_REOPENED = "COMPLAINT_REOPENED"
    COMPLAINT_FORWARDED = "COMPLAINT_FORWARDED"
    REQUEST_STATUS_UPDATE = "REQUEST_STATUS_UPDATE"


class DeliveryStatus(str, Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"


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
