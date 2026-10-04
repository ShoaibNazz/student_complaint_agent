"""Combine AI priority with deterministic safety/priority rules. Rules can only raise urgency."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import Priority, max_priority
from app.rules.priority_rules import PriorityRules, get_priority_rules
from app.rules.safety_rules import SafetyAssessment

BANDS = {
    Priority.LOW: (0.0, 0.39, 0.25),
    Priority.MEDIUM: (0.40, 0.69, 0.55),
    Priority.HIGH: (0.70, 0.89, 0.80),
    Priority.CRITICAL: (0.90, 1.0, 0.95),
}


@dataclass
class PriorityDecision:
    priority: Priority
    score: float
    reason: str


def band_score(priority: Priority, score: float | None) -> float:
    lo, hi, mid = BANDS[priority]
    if score is None:
        return mid
    return round(min(max(score, lo), hi), 2)


def resolve_priority(*, ai_priority: Priority, ai_score: float | None, ai_reason: str, category: str, text: str,
                     safety: SafetyAssessment, repeated_unresolved: bool = False,
                     rules: PriorityRules | None = None) -> PriorityDecision:
    rules = rules or get_priority_rules()
    floors: list[tuple[Priority, str]] = []
    if safety.max_severity:
        floors.append((safety.max_severity, "Safety rule signal: " + "; ".join(safety.labels) + "."))
    rule = rules.evaluate(text, category)
    if rule.escalated:
        floors.append((rule.priority, rule.reason))
    if repeated_unresolved:
        floors.append((Priority.HIGH, "A very similar earlier complaint from the same student is still unresolved."))

    final = max_priority(ai_priority, *[p for p, _ in floors])
    if final == ai_priority:
        return PriorityDecision(final, band_score(final, ai_score), ai_reason)
    reasons = [r for p, r in floors if p == final]
    return PriorityDecision(final, band_score(final, None), f"{' '.join(reasons)} (AI assessed: {ai_priority.value}.)")
