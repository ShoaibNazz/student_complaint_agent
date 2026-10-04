from app.core.config import Settings
from app.schemas.complaint import ComplaintCreate
from app.services import complaint_service
from app.services.duplicate_service import find_possible_duplicate, lexical_similarity
from tests.conftest import payload


def test_similarity_scores():
    assert lexical_similarity("my marks are missing", "My marks are missing!") > 0.95
    assert lexical_similarity("my marks are missing", "the bus driver was rude") < 0.3


def test_duplicate_flagged_not_deleted_and_escalated(db):
    first = complaint_service.create_complaint(db, ComplaintCreate(**payload()))
    second = complaint_service.create_complaint(db, ComplaintCreate(**payload(
        complaint_title="Assignment marks not uploaded!", complaint_text=payload()["complaint_text"] + " Please help.")))
    assert not first.possible_duplicate
    assert second.possible_duplicate and second.duplicate_of_id == first.id
    assert second.analysis.priority == "HIGH" and "unresolved" in second.analysis.priority_reason
    assert any(h.action == "Possible duplicate flagged" for h in second.history)
    assert complaint_service.get_complaint(db, first.id)  # original untouched


def test_different_student_or_topic_is_not_duplicate(db):
    complaint_service.create_complaint(db, ComplaintCreate(**payload()))
    other_student = complaint_service.create_complaint(db, ComplaintCreate(**payload(student_id="OTHER", email="o@x.edu")))
    other_topic = complaint_service.create_complaint(db, ComplaintCreate(**payload(
        complaint_title="Bus", complaint_text="The university bus on route five arrives very late every morning.")))
    assert not other_student.possible_duplicate and not other_topic.possible_duplicate


def test_threshold_and_missing_identity(db):
    c = complaint_service.create_complaint(db, ComplaintCreate(**payload()))
    strict = Settings(duplicate_threshold=1.01)
    args = dict(student_id="STU-1024", email=None, title=c.title, text=c.complaint_text)
    assert find_possible_duplicate(db, settings=Settings(), **args) is not None
    assert find_possible_duplicate(db, settings=strict, **args) is None
    assert find_possible_duplicate(db, student_id=None, email=None, title=c.title, text=c.complaint_text) is None
