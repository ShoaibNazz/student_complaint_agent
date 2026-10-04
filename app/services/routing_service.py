"""Department routing driven by config/routing.json and config/departments.json."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import load_json_config

logger = logging.getLogger("complaint_agent.routing")


@dataclass
class RoutingDecision:
    department: str
    reason: str


class RoutingService:
    def __init__(self, routing: dict | None = None, departments: dict | None = None):
        routing = routing or load_json_config("routing")
        departments = departments or load_json_config("departments")
        self.department_names = [d["name"] for d in departments["departments"]]
        self.default = routing.get("default_department", "Administration Office")
        self.category_map: dict[str, str] = routing.get("category_to_department", {})
        self.overrides: dict[str, str] = routing.get("subcategory_overrides", {})

    def route(self, category: str, subcategory: str | None = None, ai_department: str | None = None,
              ai_reason: str | None = None) -> RoutingDecision:
        dept = self.overrides.get(f"{category}::{subcategory}") or self.category_map.get(category)
        if not dept and ai_department in self.department_names:
            dept = ai_department
        dept = dept or self.default
        if dept not in self.department_names:
            logger.warning("Department '%s' is not listed in departments.json", dept)
        if ai_reason and ai_department == dept:
            reason = ai_reason
        else:
            reason = f"Complaints categorised as '{category}'" + (f" / '{subcategory}'" if subcategory and subcategory != "General" else "") + f" are handled by the {dept}."
        return RoutingDecision(dept, reason)


@lru_cache
def get_routing_service() -> RoutingService:
    return RoutingService()
