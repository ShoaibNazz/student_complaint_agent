import pytest

from app.ai.base import AIProvider
from app.ai.factory import set_provider_override
from app.core.exceptions import AIProviderError
from app.models.complaint import Complaint
from app.schemas.complaint import ComplaintCreate
from app.services import complaint_service
from tests.conftest import payload


def test_create_complaint_returns_receipt_only(client):
    r = client.post("/api/complaints", json=payload())
    assert r.status_code == 201
    body = r.json()
    assert body["complaint_number"].startswith("CMP-") and len(body["complaint_number"]) == 15
    assert body["message"] == "Your complaint has been received."
    assert "analysis" not in body  # public endpoint never exposes AI analysis


def test_admin_sees_analysis(client):
    cid = client.post("/api/complaints", json=payload()).json()["id"]
    data = client.get(f"/api/complaints/{cid}").json()
    a = data["analysis"]
    assert data["analysis_status"] == "COMPLETED" and data["status"] == "NEW"
    assert a["category"] == "Academic" and a["subcategory"] == "Assessment Marks"
    assert a["assigned_department"] == "Examination Department"
    assert a["priority"] == "MEDIUM" and a["requires_human_review"] is False
    assert a["draft_response"].startswith("Dear Ali,")  # personalised locally
    assert [h["action"] for h in data["history"]][:2] == ["Complaint created", "AI analysis completed"]


@pytest.mark.parametrize("text", ["", "   ", "help", "not good"])
def test_empty_or_too_short_rejected_with_message(client, text):
    r = client.post("/api/complaints", json=payload(complaint_text=text))
    assert r.status_code == 422


def test_invalid_email_rejected(client):
    assert client.post("/api/complaints", json=payload(email="not-an-email")).status_code == 422


def test_spam_is_saved_but_flagged(client):
    spam = "buy now " * 30
    cid = client.post("/api/complaints", json=payload(complaint_text=spam)).json()["id"]
    a = client.get(f"/api/complaints/{cid}").json()["analysis"]
    assert a["requires_human_review"] is True and "spam" in a["human_review_reason"].lower()


def test_original_text_never_overwritten(client):
    original = payload()["complaint_text"]
    cid = client.post("/api/complaints", json=payload()).json()["id"]
    client.put(f"/api/complaints/{cid}/response", json={"draft_response": "Edited reply text", "approved": True})
    client.put(f"/api/complaints/{cid}", json={"internal_notes": "called teacher", "complaint_text": "HACKED"})
    client.post(f"/api/complaints/{cid}/analyze")
    data = client.get(f"/api/complaints/{cid}").json()
    assert data["complaint_text"] == original


def test_edit_response_status_assignment_are_audited(client):
    cid = client.post("/api/complaints", json=payload()).json()["id"]
    assert client.put(f"/api/complaints/{cid}/response", json={"draft_response": "Edited reply", "approved": True}).status_code == 200
    assert client.put(f"/api/complaints/{cid}/status", json={"status": "IN_PROGRESS"}).status_code == 200
    r = client.put(f"/api/complaints/{cid}/assignment", json={"department": "Academic Department", "priority": "HIGH"})
    assert r.status_code == 200
    data = client.get(f"/api/complaints/{cid}").json()
    assert data["analysis"]["draft_response"] == "Edited reply" and data["analysis"]["response_approved"] is True
    assert data["analysis"]["original_draft_response"].startswith("Dear Ali")
    actions = [h["action"] for h in data["history"]]
    for expected in ("Response edited", "Status changed", "Department changed", "Priority changed"):
        assert expected in actions


def test_invalid_assignment_and_status(client):
    cid = client.post("/api/complaints", json=payload()).json()["id"]
    assert client.put(f"/api/complaints/{cid}/assignment", json={"department": "Nope"}).status_code == 422
    assert client.put(f"/api/complaints/{cid}/status", json={"status": "WHATEVER"}).status_code == 422


def test_ai_never_closes_complaint(client):
    cid = client.post("/api/complaints", json=payload()).json()["id"]
    assert client.get(f"/api/complaints/{cid}").json()["status"] == "NEW"


def test_missing_complaint_404(client):
    assert client.get("/api/complaints/999").status_code == 404
    assert client.put("/api/complaints/999/status", json={"status": "CLOSED"}).status_code == 404


def test_soft_delete_hides_complaint(client, db):
    cid = client.post("/api/complaints", json=payload()).json()["id"]
    assert client.delete(f"/api/complaints/{cid}").status_code == 204
    assert client.get(f"/api/complaints/{cid}").status_code == 404
    assert client.get("/api/complaints").json()["total"] == 0


def test_filters_and_search(client):
    client.post("/api/complaints", json=payload())
    client.post("/api/complaints", json=payload(student_id="S2", email="b@x.edu", complaint_title="AC broken",
                complaint_text="The AC in Room 203 has not been working for four days."))
    client.post("/api/complaints", json=payload(student_id="S3", email="c@x.edu", complaint_title="Threat",
                complaint_text="A student threatened to attack me after class."))
    assert client.get("/api/complaints?priority=CRITICAL").json()["total"] == 1
    assert client.get("/api/complaints?category=Academic").json()["total"] == 1
    assert client.get("/api/complaints?department=Examination").json()["total"] == 1
    assert client.get("/api/complaints?status=OPEN").json()["total"] == 3
    assert client.get("/api/complaints?status=RESOLVED").json()["total"] == 0
    assert client.get("/api/complaints?q=room 203").json()["total"] == 1
    assert client.get("/api/complaints?q=100%25").json()["total"] == 0  # wildcard chars are escaped
    assert client.get("/api/complaints?status=BOGUS").status_code == 422
    first = client.get("/api/complaints?sort=priority").json()["items"][0]
    assert first["analysis"]["priority"] == "CRITICAL"


def test_dashboard_and_config_endpoints(client):
    client.post("/api/complaints", json=payload(complaint_text="A student threatened to attack me after class."))
    s = client.get("/api/dashboard/stats").json()
    assert s["total"] == 1 and s["critical"] == 1 and s["requires_human_review"] == 1 and s["pending"] == 1
    assert len(client.get("/api/categories").json()) == 20
    assert any(d["name"] == "IT Department" for d in client.get("/api/departments").json())
    assert client.get("/docs").status_code == 200 and client.get("/redoc").status_code == 200


def test_database_storage(db):
    c = complaint_service.create_complaint(db, ComplaintCreate(**payload()))
    stored = db.get(Complaint, c.id)
    assert stored.analysis.category == "Academic" and stored.complaint_number == f"CMP-{stored.created_at.year}-{c.id:06d}"
    assert len(stored.history) >= 3


class DownProvider(AIProvider):
    name, model_name = "down", "down"

    def __init__(self):
        self.calls = 0

    def analyze_complaint(self, complaint_text, context=None, *, strict_json=False):
        self.calls += 1
        raise AIProviderError("service unavailable")


def test_ai_failure_keeps_complaint_and_allows_retry(client):
    provider = DownProvider()
    set_provider_override(provider)
    r = client.post("/api/complaints", json=payload())
    assert r.status_code == 201 and provider.calls == 3  # 1 try + 2 retries
    cid = r.json()["id"]
    data = client.get(f"/api/complaints/{cid}").json()
    assert data["analysis_status"] == "FAILED"
    assert data["analysis"]["requires_human_review"] is True and data["analysis"]["ai_model_used"] == "rules-fallback"
    assert "AI analysis failed" in [h["action"] for h in data["history"]]
    set_provider_override(None)  # provider recovers
    data = client.post(f"/api/complaints/{cid}/analyze").json()
    assert data["analysis_status"] == "COMPLETED" and data["analysis"]["ai_model_used"].startswith("mock")


def test_web_pages(client):
    assert client.get("/submit").status_code == 200
    r = client.post("/submit", data={"student_name": "<script>alert(1)</script>", "student_id": "S9",
                    "complaint_title": "Title <b>x</b>", "complaint_text": "The AC in Room 203 has not been working for four days."})
    assert r.status_code == 200 and "Your complaint has been received." in r.text and "CMP-" in r.text
    page = client.get("/admin")
    assert page.status_code == 200 and "<script>alert(1)</script>" not in page.text  # XSS escaped
    assert "&lt;script&gt;" in page.text
    assert client.get("/admin/complaints/1").status_code == 200
    bad = client.post("/submit", data={"student_name": "A", "complaint_title": "abc", "complaint_text": "short"})
    assert bad.status_code == 422 and "too short" in bad.text
    form = {"category": "Facilities / Maintenance", "subcategory": "Cleanliness", "department": "IT Department",
            "priority": "HIGH", "status": "ASSIGNED", "draft_response": "Dear Student, edited.", "approved": "1",
            "internal_notes": "note"}
    assert client.post("/admin/complaints/1", data=form, follow_redirects=False).status_code == 303
    assert client.post("/admin/complaints/1/analyze", follow_redirects=False).status_code == 303


def test_admin_auth_enforced_when_password_set(client, monkeypatch):
    from app.core import security
    from app.core.config import Settings
    monkeypatch.setattr(security, "get_settings", lambda: Settings(admin_password="s3cret"))
    assert client.get("/api/complaints").status_code == 401
    assert client.get("/api/complaints", auth=("admin", "wrong")).status_code == 401
    assert client.get("/api/complaints", auth=("admin", "s3cret")).status_code == 200
    assert client.post("/api/complaints", json=payload()).status_code == 201  # students can still submit


def test_same_origin_csrf_handling(client):
    data = {
        "student_name": "Test Student",
        "complaint_title": "AC broken in room 101",
        "complaint_text": "The air conditioning in room 101 has not been working properly.",
    }
    # Public submit works regardless of origin (e.g. embedded portals, loopback, privacy modes)
    r = client.post("/submit", data=data, headers={"Origin": "http://localhost:8000", "Host": "127.0.0.1:8000"})
    assert r.status_code == 200 and "Your complaint has been received." in r.text

    r = client.post("/submit", data=data, headers={"Origin": "null", "Host": "127.0.0.1:8000"})
    assert r.status_code == 200 and "Your complaint has been received." in r.text

    r = client.post("/submit", data=data, headers={"Origin": "http://external-portal.edu", "Host": "127.0.0.1:8000"})
    assert r.status_code == 200 and "Your complaint has been received." in r.text

    # Admin routes enforce CSRF protection
    form = {"category": "Facilities / Maintenance", "subcategory": "Cleanliness", "department": "IT Department",
            "priority": "HIGH", "status": "ASSIGNED", "draft_response": "Dear Student, edited.", "approved": "1",
            "internal_notes": "note"}
    # Admin allows loopback
    r_admin_ok = client.post("/admin/complaints/1", data=form, follow_redirects=False,
                             headers={"Origin": "http://localhost:8000", "Host": "127.0.0.1:8000"})
    assert r_admin_ok.status_code == 303

    # Admin rejects external malicious origin
    r_admin_bad = client.post("/admin/complaints/1", data=form, follow_redirects=False,
                              headers={"Origin": "http://evil.com", "Host": "127.0.0.1:8000"})
    assert r_admin_bad.status_code == 403

