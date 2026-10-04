"""Configurable category catalogue (config/categories.json) and keyword scoring."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import load_json_config


def compile_keyword(kw: str) -> re.Pattern:
    """'word' = whole word, 'stem*' = prefix match, multi-word phrases allowed."""
    if kw.endswith("*"):
        return re.compile(r"\b" + re.escape(kw[:-1]) + r"\w*", re.I)
    return re.compile(r"\b" + re.escape(kw) + r"\b", re.I)


@dataclass(frozen=True)
class Category:
    name: str
    description: str
    keywords: tuple[re.Pattern, ...]
    subcategories: dict
    suggested_action: str


class CategoryCatalog:
    def __init__(self, data: dict | None = None):
        data = data or load_json_config("categories")
        self._cats: dict[str, Category] = {}
        for c in data["categories"]:
            self._cats[c["name"]] = Category(
                name=c["name"],
                description=c.get("description", ""),
                keywords=tuple(compile_keyword(k) for k in c.get("keywords", [])),
                subcategories={s: tuple(compile_keyword(k) for k in kws) for s, kws in c.get("subcategories", {}).items()},
                suggested_action=c.get("suggested_action", "Review manually."),
            )
        self.fallback = "Other" if "Other" in self._cats else next(iter(self._cats))

    @property
    def names(self) -> list[str]:
        return list(self._cats)

    def get(self, name: str) -> Category:
        return self._cats[name]

    def subcategory_names(self, category: str) -> list[str]:
        return list(self._cats[category].subcategories) if category in self._cats else []

    def normalize(self, name: str | None) -> str | None:
        """Map a model-supplied name onto a configured category (case-insensitive, tolerant of short forms)."""
        if not name:
            return None
        low = name.strip().lower()
        for cat in self._cats:
            if cat.lower() == low:
                return cat
        for cat in self._cats:
            if cat.lower().startswith(low) and len(low) >= 4:
                return cat
        return None

    def rank(self, text: str) -> list[tuple[str, int]]:
        """Categories ordered by number of distinct keyword matches (config order breaks ties)."""
        scored = [(n, sum(1 for rx in c.keywords if rx.search(text))) for n, c in self._cats.items()]
        return sorted([s for s in scored if s[1] > 0], key=lambda s: -s[1])

    def best_subcategory(self, category: str, text: str) -> str:
        cat = self._cats.get(category)
        if not cat:
            return "General"
        best, best_score = "General", 0
        for sub, kws in cat.subcategories.items():
            score = sum(1 for rx in kws if rx.search(text))
            if score > best_score:
                best, best_score = sub, score
        return best

    def prompt_listing(self) -> str:
        lines = []
        for c in self._cats.values():
            subs = ", ".join(c.subcategories) or "General"
            lines.append(f"- {c.name}: {c.description} (subcategories: {subs})")
        return "\n".join(lines)


@lru_cache
def get_catalog() -> CategoryCatalog:
    return CategoryCatalog()
