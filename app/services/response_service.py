"""Safe, neutral draft-response templates and guardrails for AI-written drafts."""
from __future__ import annotations

import re

SIGNATURE = "Regards,\nStudent Complaint Management Team"

BANNED_PHRASES = (
    "guilty", "liable", "liability", "negligen", "our fault", "we admit", "we apologize for our",
    "we apologise for our", "we guarantee", "guaranteed", "we promise", "will be fired", "will be punished",
    "will be suspended", "will be expelled", "will be resolved", "definitely will", "compensation",
)


def standard_draft(issue: str, department: str) -> str:
    return (
        "Dear Student,\n\nThank you for contacting us.\n\n"
        f"We have received your complaint regarding {issue}.\n\n"
        f"Your complaint has been forwarded to the {department} for review. The concerned team will examine "
        "the matter and take the appropriate action. We will update you through the official channels as the "
        "review progresses.\n\nWe appreciate your patience while this matter is reviewed.\n\n" + SIGNATURE
    )


def sensitive_draft(department: str) -> str:
    return (
        "Dear Student,\n\nThank you for bringing this matter to our attention. We take reports of this nature "
        f"seriously, and your report has been referred to the {department} for prompt and confidential review "
        "by appropriately trained staff. No conclusions have been reached at this stage.\n\n"
        "A member of the team will follow up with you through official channels. If you or anyone else is in "
        "immediate danger, please contact campus security or local emergency services straight away.\n\n" + SIGNATURE
    )


def is_draft_safe(draft: str) -> bool:
    low = (draft or "").lower()
    return bool(low.strip()) and not any(p in low for p in BANNED_PHRASES)


def first_name(student_name: str | None) -> str | None:
    parts = (student_name or "").split()
    return parts[0] if parts else None


def personalize(draft: str, student_name: str | None) -> str:
    """Names are never sent to the AI; the greeting is personalised locally."""
    name = first_name(student_name)
    if not name:
        return draft
    return re.sub(r"^\s*Dear\s+(Student|Sir/Madam)\s*,", f"Dear {name},", draft, count=1, flags=re.I)
