"""Deterministic safety signals evaluated BEFORE any AI call.

These rules only raise urgency and force human review. They never decide guilt,
discipline, or emergency response - humans do that.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.models.enums import Priority


@dataclass(frozen=True)
class SafetyRule:
    rule_id: str
    label: str  # noun phrase used as "Complaint contains <label>."
    severity: Priority
    pattern: re.Pattern
    suggested_category: Optional[str]


def _r(rule_id, label, severity, regex, category):
    return SafetyRule(rule_id, label, severity, re.compile(regex, re.I), category)


C, H = Priority.CRITICAL, Priority.HIGH

RULES: tuple[SafetyRule, ...] = (
    _r("self_harm", "language about suicide or self-harm", C,
       r"\b(suicid\w*|kill(ing)?\s+(my\s*self|myself)|end\s+my\s+life|self[\s-]?harm\w*|hurt(ing)?\s+myself|want\s+to\s+die|cut(ting)?\s+myself)\b",
       "Health / Safety"),
    _r("medical_emergency", "a possible medical emergency", C,
       r"\b(medical\s+emergency|ambulance|unconscious|collapsed|seizure|heart\s+attack|overdos\w*|not\s+breathing)\b",
       "Health / Safety"),
    _r("weapon", "a reference to a weapon", C,
       r"\b(weapon\w*|guns?|knife|knives|pistol\w*|firearm\w*|bomb\w*|explosive\w*)\b", "Security"),
    _r("violence_threat", "language about violence or threats", C,
       r"\b(threat\w*|attack\w*|assault\w*|stab\w*|shoot\w*|kill\w*|beat(ing)?\s+(me|him|her|them)\s+up|violen\w*)\b",
       "Security"),
    _r("sexual_harassment", "an allegation of sexual harassment or assault", C,
       r"\b(sexual\w*|rape\w*|molest\w*|grop\w*|fondl\w*)\b", "Harassment / Bullying"),
    _r("abuse", "an allegation of abuse", C, r"\babus\w*\b", "Harassment / Bullying"),
    _r("fire_hazard", "a reference to a fire or dangerous infrastructure", C,
       r"\b(fire|on\s+fire|smoke|gas\s+leak|short[\s-]?circuit|electric\s+shock|exposed\s+wires?|building\s+collapse|collaps\w+\s+(ceiling|wall|roof))\b",
       "Health / Safety"),
    _r("immediate_danger", "a reference to immediate danger", C,
       r"\b(immediate\s+danger|in\s+danger|life[\s-]?threatening|emergency)\b", "Health / Safety"),
    _r("harassment", "an allegation of harassment or bullying", H,
       r"\b(harass\w*|bull(y|ied|ies|ying)|stalk\w*|inappropriate\s+(comments?|remarks?|messages?|behaviou?r|touch\w*|advances?)|intimidat\w*|blackmail\w*)\b",
       "Harassment / Bullying"),
    _r("discrimination", "an allegation of discrimination", H,
       r"\b(discriminat\w*|racis\w*|racial\w*|sexis\w*)\b|\bbecause\s+of\s+my\s+(religion|caste|gender|race|disability|ethnicity)\b",
       "Discrimination"),
    _r("criminal", "a possible criminal allegation", H,
       r"\b(theft|stolen|steal\w*|extort\w*|bribe\w*|fraud\w*|illegal\w*|drugs?)\b", "Security"),
    _r("safeguarding", "a possible safeguarding concern", H,
       r"\b(safeguarding|grooming|forced\s+me|unsafe\s+at\s+home|being\s+hit|hit\s+me)\b", "Harassment / Bullying"),
)


@dataclass
class SafetyFlag:
    rule_id: str
    label: str
    severity: Priority


@dataclass
class SafetyAssessment:
    flags: list[SafetyFlag] = field(default_factory=list)
    max_severity: Optional[Priority] = None
    suggested_category: Optional[str] = None

    @property
    def requires_human_review(self) -> bool:
        return bool(self.flags)

    @property
    def is_critical(self) -> bool:
        return self.max_severity == Priority.CRITICAL

    @property
    def labels(self) -> list[str]:
        return [f.label for f in self.flags]

    @property
    def reasons(self) -> list[str]:
        out = []
        for f in self.flags:
            msg = f"Complaint contains {f.label}."
            if f.severity == Priority.CRITICAL:
                msg += " Flagged for urgent human review."
            out.append(msg)
        return out


def assess_safety(text: str) -> SafetyAssessment:
    """Return safety signals found in `text`. Signals are cautionary, not conclusions."""
    result = SafetyAssessment()
    for rule in RULES:
        if rule.pattern.search(text or ""):
            result.flags.append(SafetyFlag(rule.rule_id, rule.label, rule.severity))
            if result.max_severity is None or rule.severity.rank > result.max_severity.rank:
                result.max_severity = rule.severity
                result.suggested_category = rule.suggested_category
    return result
