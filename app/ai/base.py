"""Provider-neutral AI interface. Business logic depends only on this abstraction."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    name: str = "base"
    model_name: str = "unknown"

    @abstractmethod
    def analyze_complaint(self, complaint_text: str, context: dict[str, Any] | None = None, *,
                          strict_json: bool = False) -> str:
        """Return the model's RAW text reply (expected: one JSON object).

        `context` holds non-identifying hints: title, subject, program, safety_signals, repeated.
        Parsing/validation is done by the ComplaintAnalyzer so every provider behaves identically.
        Raise app.core.exceptions.AIProviderError when the provider is unavailable or times out.
        """
