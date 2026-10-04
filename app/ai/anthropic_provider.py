"""Anthropic Claude provider. Only complaint text (no names/emails/IDs) is sent."""
from __future__ import annotations

import logging
from typing import Any

from app.ai.base import AIProvider
from app.ai.prompts import build_system_prompt, build_user_prompt
from app.core.exceptions import AIProviderError

logger = logging.getLogger("complaint_agent.ai")


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model_name: str, timeout: float = 30.0, client: Any = None):
        if not api_key and client is None:
            raise AIProviderError("ANTHROPIC_API_KEY is not configured.")
        self.model_name = model_name
        if client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise AIProviderError("The 'anthropic' package is not installed (pip install anthropic).") from exc
            client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=0)
        self._client = client
        self._system = build_system_prompt()

    def analyze_complaint(self, complaint_text: str, context: dict[str, Any] | None = None, *,
                          strict_json: bool = False) -> str:
        try:
            response = self._client.messages.create(
                model=self.model_name,
                max_tokens=1800,
                system=self._system,
                messages=[{"role": "user", "content": build_user_prompt(complaint_text, context, strict_json)}],
            )
        except Exception as exc:  # network, timeout, auth, rate limit ...
            logger.warning("Anthropic request failed: %s", type(exc).__name__)
            raise AIProviderError(f"Anthropic request failed ({type(exc).__name__}).") from exc
        parts = [b.text for b in getattr(response, "content", []) if getattr(b, "type", "") == "text"]
        return "".join(parts)
