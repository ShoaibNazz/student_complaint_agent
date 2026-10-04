"""ComplaintAnalyzer (pure pipeline) and run_analysis (persistence)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.factory import get_provider
from app.ai.parser import parse_ai_response
from app.core.config import Settings, get_settings
from app.core.exceptions import AIParseError, AIProviderError
from app.models.analysis import ComplaintAnalysis
from app.models.complaint import Complaint
from app.models.enums import AnalysisStatus, Priority
from app.rules.safety_rules import SafetyAssessment, assess_safety
from app.schemas.analysis import AIAnalysisResult
from app.services import response_service
from app.services.category_service import CategoryCatalog, get_catalog
from app.services.history_service import add_history
from app.services.priority_service import resolve_priority
from app.services.routing_service import RoutingService, get_routing_service
from app.utils.text import assess_text_quality
from app.utils.time import utcnow

logger = logging.getLogger("complaint_agent.analysis")

SAFETY_CATEGORIES = {"Security", "Harassment / Bullying", "Discrimination", "Health / Safety"}
LOW_CONFIDENCE_MESSAGE = "Low-confidence AI classification. Manual review recommended."


@dataclass
class AnalysisOutcome:
    result: AIAnalysisResult
    model_used: str
    failed: bool = False
    error: str | None = None


class ComplaintAnalyzer:
    """Hybrid pipeline: safety rules -> AI -> validation -> rule-based post-processing."""

    def __init__(self, provider: AIProvider, catalog: CategoryCatalog | None = None,
                 routing: RoutingService | None = None, settings: Settings | None = None):
        self.provider = provider
        self.catalog = catalog or get_catalog()
        self.routing = routing or get_routing_service()
        self.settings = settings or get_settings()

    # ---- public ----
    def analyze(self, *, title: str, text: str, subject: str | None = None, program: str | None = None,
                student_name: str | None = None, safety: SafetyAssessment | None = None,
                repeated: bool = False, quality_warnings: list[str] | None = None) -> AnalysisOutcome:
        safety = safety or assess_safety(f"{title}\n{text}")
        context = {"title": title, "subject": subject, "program": program,
                   "safety_signals": safety.labels, "repeated": repeated}
        ai = self._call_provider(text, context)
        result = self._finalize(ai, title=title, text=text, student_name=student_name, safety=safety,
                                repeated=repeated, warnings=quality_warnings or [])
        return AnalysisOutcome(result, getattr(self.provider, "model_name", "unknown"))

    def fallback(self, *, title: str, text: str, student_name: str | None, safety: SafetyAssessment,
                 repeated: bool, quality_warnings: list[str], error: str) -> AnalysisOutcome:
        """Rule-only triage used when AI is unavailable. Always routes to human review."""
        ranked = self.catalog.rank(f"{title}. {text}")
        category = ranked[0][0] if ranked else self.catalog.fallback
        category = safety.suggested_category if safety.suggested_category and category not in SAFETY_CATEGORIES else category
        sub = self.catalog.best_subcategory(category, f"{title}. {text}")
        route = self.routing.route(category, sub)
        ai = AIAnalysisResult(
            summary="Automated AI analysis was unavailable. Please read the original complaint.",
            category=category, subcategory=sub, category_confidence=0.0, priority=Priority.MEDIUM,
            priority_score=0.55, priority_reason="AI analysis unavailable; priority set from rules only.",
            department=route.department, routing_reason=route.reason, requires_human_review=True,
            human_review_reason="AI analysis failed; manual triage required.",
            suggested_action=self.catalog.get(category).suggested_action,
            draft_response=response_service.standard_draft("the issue you raised", route.department), tags=[],
        )
        result = self._finalize(ai, title=title, text=text, student_name=student_name, safety=safety,
                                repeated=repeated, warnings=quality_warnings, forced_reason="AI analysis failed; manual triage required.")
        return AnalysisOutcome(result, "rules-fallback", failed=True, error=error)

    # ---- internals ----
    def _call_provider(self, text: str, context: dict) -> AIAnalysisResult:
        attempts = self.settings.ai_max_retries + 1
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                raw = self.provider.analyze_complaint(text, context, strict_json=attempt > 0)
                return parse_ai_response(raw)
            except AIParseError as exc:
                last = exc
                logger.warning("AI response invalid (attempt %d/%d): %s", attempt + 1, attempts, exc)
            except AIProviderError as exc:
                last = exc
                logger.warning("AI provider error (attempt %d/%d): %s", attempt + 1, attempts, exc)
                if attempt + 1 < attempts and self.settings.ai_retry_delay > 0:
                    time.sleep(self.settings.ai_retry_delay * (attempt + 1))
        assert last is not None
        raise last

    def _finalize(self, ai: AIAnalysisResult, *, title: str, text: str, student_name: str | None,
                  safety: SafetyAssessment, repeated: bool, warnings: list[str],
                  forced_reason: str | None = None) -> AIAnalysisResult:
        combined = f"{title}. {text}"
        category = self.catalog.normalize(ai.category)
        confidence = ai.category_confidence
        if category is None:
            category, confidence = self.catalog.fallback, min(confidence, 0.4)
            subcategory = "General"
        else:
            subcategory = ai.subcategory or self.catalog.best_subcategory(category, combined)
        if (safety.suggested_category and category not in SAFETY_CATEGORIES
                and safety.suggested_category in self.catalog.names):
            category = safety.suggested_category
            subcategory = self.catalog.best_subcategory(category, combined)

        decision = resolve_priority(ai_priority=ai.priority, ai_score=ai.priority_score, ai_reason=ai.priority_reason,
                                    category=category, text=combined, safety=safety, repeated_unresolved=repeated)
        route = self.routing.route(category, subcategory, ai.department, ai.routing_reason)

        reasons: list[str] = []
        if forced_reason:
            reasons.append(forced_reason)
        reasons.extend(safety.reasons)
        if ai.requires_human_review:
            reasons.append(ai.human_review_reason or "The AI flagged this complaint for human review.")
        if warnings:
            reasons.append("Possible spam or repeated text (" + ", ".join(warnings) + "); verify the complaint is genuine.")
        if decision.priority == Priority.CRITICAL:
            reasons.append("Critical priority: urgent human review required. The system makes no emergency decisions.")
        if confidence < self.settings.low_confidence_threshold and not forced_reason:
            reasons.append(LOW_CONFIDENCE_MESSAGE)
        reasons = list(dict.fromkeys(reasons))

        sensitive = category in SAFETY_CATEGORIES or safety.requires_human_review
        draft = ai.draft_response
        if not response_service.is_draft_safe(draft):
            draft = (response_service.sensitive_draft(route.department) if sensitive
                     else response_service.standard_draft("the issue you raised", route.department))
        draft = response_service.personalize(draft, student_name)

        action = ai.suggested_action
        if decision.priority == Priority.CRITICAL:
            action = "URGENT: refer to a trained human reviewer immediately. " + action

        return ai.model_copy(update=dict(
            category=category, subcategory=subcategory, category_confidence=round(confidence, 2),
            priority=decision.priority, priority_score=decision.score, priority_reason=decision.reason,
            department=route.department, routing_reason=route.reason,
            requires_human_review=bool(reasons), human_review_reason=" ".join(reasons) or None,
            suggested_action=action, draft_response=draft,
        ))


def run_analysis(db: Session, complaint: Complaint, *, performed_by: str = "AI",
                 analyzer: ComplaintAnalyzer | None = None) -> ComplaintAnalysis:
    """Analyse a saved complaint and persist the result. The complaint is never lost on AI failure."""
    settings = get_settings()
    safety = assess_safety(f"{complaint.title}\n{complaint.complaint_text}")
    quality = assess_text_quality(complaint.complaint_text)
    repeated = False
    if complaint.possible_duplicate and complaint.duplicate_of_id:
        other = db.get(Complaint, complaint.duplicate_of_id)
        repeated = bool(other and other.status not in ("RESOLVED", "CLOSED", "REJECTED"))
    logger.info("Analysis started complaint=%s", complaint.complaint_number)
    kwargs = dict(title=complaint.title, text=complaint.complaint_text, student_name=complaint.student_name,
                  safety=safety, repeated=repeated, quality_warnings=quality.warnings)
    try:
        analyzer = analyzer or ComplaintAnalyzer(get_provider(settings), settings=settings)
        outcome = analyzer.analyze(subject=complaint.subject, program=complaint.class_or_program, **kwargs)
        complaint.analysis_status = AnalysisStatus.COMPLETED.value
    except Exception as exc:  # AIProviderError, AIParseError, or unexpected - never lose the complaint
        logger.error("Analysis error complaint=%s type=%s", complaint.complaint_number, type(exc).__name__)
        fallback_analyzer = analyzer or ComplaintAnalyzer(_NullProvider(), settings=settings)
        outcome = fallback_analyzer.fallback(error=f"{type(exc).__name__}: {str(exc)[:200]}", **kwargs)
        complaint.analysis_status = AnalysisStatus.FAILED.value

    r = outcome.result
    existing = complaint.analysis
    previous = f"{existing.category}/{existing.priority}/{existing.assigned_department}" if existing else None
    fields = dict(
        summary=r.summary, category=r.category, subcategory=r.subcategory, category_confidence=r.category_confidence,
        priority=r.priority.value, priority_score=r.priority_score, priority_reason=r.priority_reason,
        assigned_department=r.department, routing_reason=r.routing_reason,
        requires_human_review=r.requires_human_review, human_review_reason=r.human_review_reason,
        suggested_action=r.suggested_action, draft_response=r.draft_response,
        original_draft_response=r.draft_response, response_approved=False, tags=r.tags,
        ai_model_used=outcome.model_used, analysis_error=outcome.error, analyzed_at=utcnow(),
    )
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
    else:
        complaint.analysis = ComplaintAnalysis(**fields)
    new_value = f"{r.category}/{r.priority.value}/{r.department}"
    if outcome.failed:
        add_history(db, complaint.id, "AI analysis failed", previous, "Rule-based fallback applied", performed_by)
    else:
        add_history(db, complaint.id, "AI analysis completed", previous, new_value, performed_by)
    add_history(db, complaint.id, "Department assigned", None, r.department, performed_by)
    db.commit()
    logger.info("Analysis %s complaint=%s priority=%s department=%s review=%s",
                "failed" if outcome.failed else "completed", complaint.complaint_number, r.priority.value,
                r.department, r.requires_human_review)
    return complaint.analysis


class _NullProvider(AIProvider):
    name = "none"
    model_name = "none"

    def analyze_complaint(self, complaint_text, context=None, *, strict_json=False) -> str:  # pragma: no cover
        raise AIProviderError("No AI provider available.")
