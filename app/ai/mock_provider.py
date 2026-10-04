"""Offline, deterministic provider so the whole app runs without any API key."""
from __future__ import annotations

import json
import re
from typing import Any

from app.ai.base import AIProvider
from app.models.enums import Priority
from app.rules.priority_rules import PriorityRules, get_priority_rules
from app.rules.safety_rules import assess_safety
from app.services import response_service
from app.services.category_service import CategoryCatalog, get_catalog
from app.services.priority_service import band_score, resolve_priority
from app.services.routing_service import RoutingService, get_routing_service
from app.utils.text import STOPWORDS, first_sentence, normalize

SENSITIVE = {"Security", "Harassment / Bullying", "Discrimination", "Health / Safety"}


class MockAIProvider(AIProvider):
    name = "mock"
    model_name = "mock-keyword-classifier-v1"

    def __init__(self, catalog: CategoryCatalog | None = None, routing: RoutingService | None = None,
                 rules: PriorityRules | None = None):
        self.catalog = catalog or get_catalog()
        self.routing = routing or get_routing_service()
        self.rules = rules or get_priority_rules()

    def analyze_complaint(self, complaint_text: str, context: dict[str, Any] | None = None, *,
                          strict_json: bool = False) -> str:
        context = context or {}
        title = context.get("title") or ""
        text = f"{title}. {complaint_text}"
        ranked = self.catalog.rank(text)
        if ranked:
            category, top = ranked[0]
            second = ranked[1][1] if len(ranked) > 1 else 0
            confidence = min(0.95, 0.60 + 0.12 * top + 0.08 * (top - second))
        else:
            category, confidence = self.catalog.fallback, 0.35
        sub = self.catalog.best_subcategory(category, text)

        safety = assess_safety(text)
        if safety.suggested_category and category not in SENSITIVE:
            category = safety.suggested_category
            sub = self.catalog.best_subcategory(category, text)
        sensitive = category in SENSITIVE or safety.requires_human_review

        base = self.rules.evaluate(text, category)
        decision = resolve_priority(ai_priority=base.priority, ai_score=None, ai_reason=base.reason,
                                    category=category, text=text, safety=safety, rules=self.rules)
        route = self.routing.route(category, sub)
        verb = "The complaint alleges" if sensitive else "The student reports"
        summary = f'{verb} the following: "{first_sentence(complaint_text, 220)}"'
        issue = "the matter you raised" if sensitive else f'"{title}"' if title else "the issue you raised"
        draft = (response_service.sensitive_draft(route.department) if sensitive
                 else response_service.standard_draft(issue, route.department))
        review = safety.requires_human_review
        tokens = [w for w in normalize(text).split() if len(w) > 3 and w not in STOPWORDS]
        tags = list(dict.fromkeys(tokens))[:6]
        result = {
            "summary": summary,
            "category": category,
            "subcategory": sub,
            "category_confidence": round(confidence, 2),
            "priority": decision.priority.value,
            "priority_score": decision.score,
            "priority_reason": decision.reason,
            "department": route.department,
            "routing_reason": route.reason,
            "requires_human_review": review,
            "human_review_reason": "; ".join(safety.reasons) if review else None,
            "suggested_action": self.catalog.get(category).suggested_action,
            "draft_response": draft,
            "tags": tags,
        }
        return json.dumps(result)
