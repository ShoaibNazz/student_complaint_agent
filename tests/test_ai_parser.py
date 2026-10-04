import json

import pytest

from app.ai.anthropic_provider import AnthropicProvider
from app.ai.base import AIProvider
from app.ai.mock_provider import MockAIProvider
from app.ai.parser import parse_ai_response
from app.ai.prompts import build_system_prompt, build_user_prompt
from app.core.config import Settings
from app.core.exceptions import AIParseError, AIProviderError
from app.services.analysis_service import ComplaintAnalyzer

VALID = {
    "summary": "The student reports missing marks.", "category": "Academic", "subcategory": "Assessment Marks",
    "category_confidence": 0.94, "priority": "medium", "priority_score": 0.65, "priority_reason": "Delayed record.",
    "department": "Examination Department", "routing_reason": "Marks are handled there.",
    "requires_human_review": False, "human_review_reason": None, "suggested_action": "Verify the record.",
    "draft_response": "Dear Student,\n\nWe have received your complaint.\n\nRegards,\nTeam", "tags": ["Marks", "math"],
}


def test_parse_plain_fenced_and_chatty_output():
    raw = json.dumps(VALID)
    assert parse_ai_response(raw).priority.value == "MEDIUM"
    assert parse_ai_response(f"```json\n{raw}\n```").category == "Academic"
    assert parse_ai_response(f"Here is the analysis:\n{raw}\nHope that helps!").tags == ["marks", "math"]


def test_parse_repairs_trailing_commas_and_percent_scores():
    raw = json.dumps(VALID).replace('"category_confidence": 0.94', '"category_confidence": "94%"')[:-1] + ",}"
    assert parse_ai_response(raw).category_confidence == pytest.approx(0.94)


@pytest.mark.parametrize("raw", ["", "no json at all", '{"summary": "x"', "[1,2,3]", '{"summary": "x"}'])
def test_malformed_or_incomplete_json_raises(raw):
    with pytest.raises(AIParseError):
        parse_ai_response(raw)


def test_invalid_priority_rejected():
    with pytest.raises(AIParseError):
        parse_ai_response(json.dumps({**VALID, "priority": "URGENT!!"}))


class FlakyProvider(AIProvider):
    name, model_name = "flaky", "flaky"

    def __init__(self, bad_replies):
        self.bad, self.calls, self.strict_flags = bad_replies, 0, []

    def analyze_complaint(self, complaint_text, context=None, *, strict_json=False):
        self.calls += 1
        self.strict_flags.append(strict_json)
        return self.bad.pop(0) if self.bad else json.dumps(VALID)


def test_malformed_json_is_retried_then_succeeds():
    provider = FlakyProvider(["{not json", "still garbage"])
    out = ComplaintAnalyzer(provider, settings=Settings(ai_retry_delay=0)).analyze(title="t", text="marks are missing from the portal")
    assert provider.calls == 3 and provider.strict_flags == [False, True, True] and not out.failed


def test_retries_exhausted_raises_parse_error():
    provider = FlakyProvider(["x"] * 10)
    with pytest.raises(AIParseError):
        ComplaintAnalyzer(provider, settings=Settings(ai_retry_delay=0)).analyze(title="t", text="marks are missing")
    assert provider.calls == 3


def test_provider_failure_raises_provider_error():
    class Down(AIProvider):
        def analyze_complaint(self, *a, **k):
            raise AIProviderError("timeout")
    with pytest.raises(AIProviderError):
        ComplaintAnalyzer(Down(), settings=Settings(ai_retry_delay=0, ai_max_retries=1)).analyze(title="t", text="marks missing")


def test_unsafe_ai_draft_is_replaced_and_unknown_category_normalised():
    bad = {**VALID, "category": "Made Up Category", "draft_response": "Dear Student, the teacher is guilty and we promise a refund."}
    out = ComplaintAnalyzer(FlakyProvider([json.dumps(bad)]), settings=Settings()).analyze(title="t", text="something strange happened here")
    assert out.result.category == "Other" and "guilty" not in out.result.draft_response.lower()
    assert out.result.requires_human_review  # confidence capped -> low-confidence review


def test_mock_output_is_valid_json_for_schema():
    raw = MockAIProvider().analyze_complaint("The bus was late again", {"title": "Bus"})
    assert parse_ai_response(raw).category == "Transport"


def test_anthropic_provider_with_fake_client_and_privacy():
    captured = {}

    class Block:
        type, text = "text", json.dumps(VALID)

    class Messages:
        def create(self, **kw):
            captured.update(kw)
            return type("R", (), {"content": [Block()]})()

    provider = AnthropicProvider("key", "test-model", client=type("C", (), {"messages": Messages()})())
    raw = provider.analyze_complaint("Marks missing", {"title": "Marks", "safety_signals": []})
    assert parse_ai_response(raw).category == "Academic"
    assert captured["model"] == "test-model" and "NOT the final decision maker" in captured["system"]
    assert "<complaint>" in captured["messages"][0]["content"]


def test_anthropic_provider_wraps_sdk_errors():
    class Boom:
        class messages:
            @staticmethod
            def create(**kw):
                raise TimeoutError("secret details")
    with pytest.raises(AIProviderError) as e:
        AnthropicProvider("key", "m", client=Boom()).analyze_complaint("x")
    assert "secret" not in str(e.value)
    with pytest.raises(AIProviderError):
        AnthropicProvider("", "m")


def test_prompts_contain_required_rules():
    system = build_system_prompt()
    for phrase in ("Never determine guilt", "Never invent facts", "Return ONLY one valid JSON object", "Harassment / Bullying"):
        assert phrase in system
    assert "Ignore" not in build_user_prompt("hi", {"title": "t"})
