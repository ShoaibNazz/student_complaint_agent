"""Provider registry. Add OpenAI/Gemini/local models by registering a factory."""
from __future__ import annotations

import logging
from typing import Callable

from app.ai.base import AIProvider
from app.ai.mock_provider import MockAIProvider
from app.core.config import Settings, get_settings
from app.core.exceptions import AIProviderError

logger = logging.getLogger("complaint_agent.ai")

_override: AIProvider | None = None  # used by tests


def _anthropic(settings: Settings) -> AIProvider:
    if not settings.anthropic_api_key:
        logger.warning("AI_PROVIDER=anthropic but ANTHROPIC_API_KEY is empty - using the mock provider.")
        return MockAIProvider()
    from app.ai.anthropic_provider import AnthropicProvider
    return AnthropicProvider(settings.anthropic_api_key, settings.model_name, settings.ai_timeout_seconds)


REGISTRY: dict[str, Callable[[Settings], AIProvider]] = {
    "mock": lambda s: MockAIProvider(),
    "anthropic": _anthropic,
}


def register_provider(name: str, factory: Callable[[Settings], AIProvider]) -> None:
    REGISTRY[name.lower()] = factory


def set_provider_override(provider: AIProvider | None) -> None:
    global _override
    _override = provider


def get_provider(settings: Settings | None = None) -> AIProvider:
    if _override is not None:
        return _override
    settings = settings or get_settings()
    factory = REGISTRY.get(settings.ai_provider)
    if factory is None:
        raise AIProviderError(f"AI provider '{settings.ai_provider}' is not available. Registered: {', '.join(REGISTRY)}.")
    return factory(settings)
