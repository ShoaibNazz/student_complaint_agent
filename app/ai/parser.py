"""Tolerant parsing + strict Pydantic validation of model output."""
from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.core.exceptions import AIParseError
from app.schemas.analysis import AIAnalysisResult

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def _extract_object(raw: str) -> str:
    text = _FENCE.sub("", raw.strip()).strip()
    start = text.find("{")
    if start == -1:
        raise AIParseError("The AI response did not contain a JSON object.")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise AIParseError("The AI response contained an unterminated JSON object.")


def parse_ai_response(raw: str) -> AIAnalysisResult:
    if not raw or not raw.strip():
        raise AIParseError("The AI response was empty.")
    candidate = _extract_object(raw)
    candidate = candidate.replace("\u201c", '"').replace("\u201d", '"')
    for attempt in (candidate, _TRAILING_COMMA.sub(r"\1", candidate)):
        try:
            data = json.loads(attempt)
            break
        except json.JSONDecodeError as exc:
            last = exc
    else:
        raise AIParseError(f"The AI response was not valid JSON ({last.msg}).")
    if not isinstance(data, dict):
        raise AIParseError("The AI response JSON was not an object.")
    try:
        return AIAnalysisResult.model_validate(data)
    except ValidationError as exc:
        fields = sorted({str(e["loc"][0]) if e["loc"] else "?" for e in exc.errors()})
        raise AIParseError(f"The AI response failed schema validation (fields: {', '.join(fields)}).") from exc
