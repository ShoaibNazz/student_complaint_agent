"""Application-specific exceptions."""
from __future__ import annotations


class AppError(Exception):
    """Base class for expected application errors."""


class ComplaintNotFound(AppError):
    def __init__(self, complaint_id: int | str):
        super().__init__(f"Complaint {complaint_id} was not found.")
        self.complaint_id = complaint_id


class ComplaintValidationError(AppError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class AIProviderError(AppError):
    """The AI provider is unavailable, timed out, or returned an error."""


class AIParseError(AppError):
    """The AI response was not valid JSON matching the required schema."""
