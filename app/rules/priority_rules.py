"""Configurable, deterministic priority rules (config/priority_rules.json)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from app.core.config import load_json_config
from app.models.enums import Priority


@dataclass
class RulePriority:
    priority: Priority
    reason: str
    escalated: bool  # True when a HIGH pattern matched (usable as a floor)
    matched_rule: Optional[str] = None


class PriorityRules:
    def __init__(self, data: dict | None = None):
        data = data or load_json_config("priority_rules")
        self.default = Priority.parse(data.get("default_priority"), Priority.MEDIUM)
        self.base = {k: Priority.parse(v, self.default) for k, v in data.get("category_base", {}).items()}
        self.high = [(p["id"], re.compile(p["regex"], re.I), p["reason"]) for p in data.get("high_patterns", [])]
        self.low = [(p["id"], re.compile(p["regex"], re.I), p["reason"]) for p in data.get("low_patterns", [])]

    def evaluate(self, text: str, category: str) -> RulePriority:
        base = self.base.get(category, self.default)
        for rule_id, rx, reason in self.high:
            if rx.search(text or ""):
                return RulePriority(max(base, Priority.HIGH, key=lambda p: p.rank), reason, True, rule_id)
        if base.rank <= Priority.MEDIUM.rank:
            for rule_id, rx, reason in self.low:
                if rx.search(text or ""):
                    return RulePriority(Priority.LOW, reason, False, rule_id)
        return RulePriority(base, f"Typical priority for '{category}' complaints; no urgency indicators were found.", False)


@lru_cache
def get_priority_rules() -> PriorityRules:
    return PriorityRules()
