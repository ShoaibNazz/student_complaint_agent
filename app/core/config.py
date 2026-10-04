"""Central configuration: environment settings, JSON config loading, logging."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def _get(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return default if value is None else value.strip()


def _bool(name: str, default: bool) -> bool:
    value = _get(name)
    return default if value == "" else value.lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(_get(name) or default)
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(_get(name) or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Student Complaint Agent"
    database_url: str = f"sqlite:///{(BASE_DIR / 'complaints.db').as_posix()}"
    log_level: str = "INFO"
    config_dir: Path = BASE_DIR / "config"

    ai_provider: str = "mock"
    anthropic_api_key: str = field(default="", repr=False)
    model_name: str = "claude-sonnet-5-5"
    ai_timeout_seconds: float = 30.0
    ai_max_retries: int = 2
    ai_retry_delay: float = 1.0

    low_confidence_threshold: float = 0.60
    duplicate_threshold: float = 0.72
    duplicate_window_days: int = 14
    require_student_id: bool = False
    require_email: bool = False
    max_complaint_length: int = 5000

    admin_username: str = "admin"
    admin_password: str = field(default="", repr=False)
    secret_key: str = field(default="supersecret-complaint-agent-token-key-2026", repr=False)
    admin_registration_token: str = field(default="ADMIN-SECRET-2026", repr=False)

    @classmethod
    def from_env(cls) -> "Settings":
        d = cls()
        return cls(
            database_url=_get("DATABASE_URL", d.database_url),
            log_level=_get("LOG_LEVEL", d.log_level).upper(),
            config_dir=Path(_get("CONFIG_DIR", str(d.config_dir))),
            ai_provider=_get("AI_PROVIDER", d.ai_provider).lower(),
            anthropic_api_key=_get("ANTHROPIC_API_KEY"),
            model_name=_get("MODEL_NAME", d.model_name),
            ai_timeout_seconds=_float("AI_TIMEOUT_SECONDS", d.ai_timeout_seconds),
            ai_max_retries=_int("AI_MAX_RETRIES", d.ai_max_retries),
            ai_retry_delay=_float("AI_RETRY_DELAY", d.ai_retry_delay),
            low_confidence_threshold=_float("LOW_CONFIDENCE_THRESHOLD", d.low_confidence_threshold),
            duplicate_threshold=_float("DUPLICATE_THRESHOLD", d.duplicate_threshold),
            duplicate_window_days=_int("DUPLICATE_WINDOW_DAYS", d.duplicate_window_days),
            require_student_id=_bool("REQUIRE_STUDENT_ID", d.require_student_id),
            require_email=_bool("REQUIRE_EMAIL", d.require_email),
            admin_username=_get("ADMIN_USERNAME", d.admin_username),
            admin_password=_get("ADMIN_PASSWORD"),
            secret_key=_get("SECRET_KEY", d.secret_key),
            admin_registration_token=_get("ADMIN_REGISTRATION_TOKEN", d.admin_registration_token),
        )



@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()


def load_json_config(name: str) -> dict[str, Any]:
    """Load config/<name>.json (editable by institutions without touching code)."""
    path = get_settings().config_dir / f"{name}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def setup_logging(level: str | None = None) -> None:
    logging.basicConfig(
        level=getattr(logging, (level or get_settings().log_level), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
