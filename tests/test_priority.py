import pytest

from app.ai.mock_provider import MockAIProvider
from app.core.config import Settings
from app.models.enums import Priority
from app.rules.safety_rules import assess_safety
from app.services.analysis_service import ComplaintAnalyzer
from app.services.priority_service import resolve_priority


def analyze(text, title="Complaint", provider=None, settings=None):
    analyzer = ComplaintAnalyzer(provider or MockAIProvider(), settings=settings or Settings())
    return analyzer.analyze(title=title, text=text, student_name="Test Student").result


EXAMPLES = [
    ("My student portal password is not working and I cannot download my fee voucher.", "IT / Portal / LMS", "MEDIUM", "IT Department", False),
    ("I paid my semester fee but the portal still shows unpaid.", "Fees / Finance", "MEDIUM", "Accounts Department", False),
    ("The AC in Room 203 has not been working for four days.", "Facilities / Maintenance", "LOW", "Administration / Maintenance", False),
    ("My final exam result shows 42 marks, but my teacher told me I received 68.", "Results / Marks", "HIGH", "Examination Department", False),
    ("A student threatened to attack me after class.", "Security", "CRITICAL", "Security / Student Affairs", True),
    ("A teacher is repeatedly making inappropriate comments toward me.", "Harassment / Bullying", "HIGH", "Student Affairs / Designated Safeguarding Officer", True),
    ("My mathematics teacher has not uploaded our assignment marks for the last three weeks and I need them before the final examination.", "Academic", "MEDIUM", "Examination Department", False),
    ("I submitted my assignment two weeks ago but my marks are still missing.", "Academic", "MEDIUM", "Examination Department", False),
]


@pytest.mark.parametrize("text,category,priority,department,review", EXAMPLES)
def test_spec_examples(text, category, priority, department, review):
    r = analyze(text)
    assert (r.category, r.priority.value, r.department, r.requires_human_review) == (category, priority, department, review)
    assert 0 <= r.category_confidence <= 1 and 0 <= r.priority_score <= 1


@pytest.mark.parametrize("text", [
    "I want to kill myself, I cannot cope with exams.", "There is a fire in the chemistry lab corridor.",
    "He showed a knife in the hostel.", "I was sexually harassed by a senior.", "Someone is in immediate danger near the gate.",
])
def test_critical_detection_forces_human_review(text):
    safety = assess_safety(text)
    assert safety.max_severity == Priority.CRITICAL and safety.requires_human_review
    r = analyze(text)
    assert r.priority == Priority.CRITICAL and r.requires_human_review
    assert r.suggested_action.startswith("URGENT")
    assert "guilty" not in r.draft_response.lower()


def test_rules_never_lower_ai_priority_and_can_raise_it():
    safety = assess_safety("A student threatened me")
    d = resolve_priority(ai_priority=Priority.LOW, ai_score=0.2, ai_reason="x", category="Other", text="threatened", safety=safety)
    assert d.priority == Priority.CRITICAL and d.score >= 0.9
    d = resolve_priority(ai_priority=Priority.HIGH, ai_score=0.8, ai_reason="x", category="Other", text="hello there", safety=assess_safety("hello"))
    assert d.priority == Priority.HIGH


def test_repeated_unresolved_raises_to_high():
    d = resolve_priority(ai_priority=Priority.MEDIUM, ai_score=0.5, ai_reason="x", category="Academic", text="marks missing",
                         safety=assess_safety("marks missing"), repeated_unresolved=True)
    assert d.priority == Priority.HIGH


def test_low_confidence_triggers_review():
    r = analyze("Something odd happened yesterday, not sure who to ask about it.")
    assert r.category == "Other" and r.category_confidence < 0.6
    assert r.requires_human_review and "Low-confidence AI classification. Manual review recommended." in r.human_review_reason


def test_confidence_threshold_is_configurable():
    text = "I submitted my assignment two weeks ago but my marks are still missing."
    assert not analyze(text).requires_human_review
    strict = analyze(text, settings=Settings(low_confidence_threshold=0.99))
    assert strict.requires_human_review and "Low-confidence" in strict.human_review_reason


def test_draft_is_neutral_and_safe():
    r = analyze("A teacher is repeatedly making inappropriate comments toward me.")
    low = r.draft_response.lower()
    assert r.draft_response.startswith("Dear Test,") and "guilty" not in low and "no conclusions" in low
    assert r.summary.startswith("The complaint alleges")
