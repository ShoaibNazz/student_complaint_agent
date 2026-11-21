from datetime import datetime, timedelta, timezone
from app.services.complaint_service import compute_sla_info


class DummyAnalysis:
    def __init__(self, priority="MEDIUM"):
        self.priority = priority


class DummyComplaint:
    def __init__(self, created_at, status="IN_PROGRESS"):
        self.created_at = created_at
        self.status = status


def test_sla_within_deadline():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    c = DummyComplaint(created_at=now - timedelta(hours=5), status="IN_PROGRESS")
    a = DummyAnalysis(priority="MEDIUM")  # 48h SLA
    info = compute_sla_info(c, a)

    assert info["is_breached"] is False
    assert info["is_resolved"] is False
    assert info["remaining_hours"] > 30
    assert "left" in info["badge_text"]


def test_sla_near_deadline_warning():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    c = DummyComplaint(created_at=now - timedelta(hours=40), status="IN_PROGRESS")
    a = DummyAnalysis(priority="MEDIUM")  # 48h SLA -> 8h left
    info = compute_sla_info(c, a)

    assert info["is_breached"] is False
    assert info["remaining_hours"] <= 12
    assert "left" in info["badge_text"]


def test_sla_breached():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    c = DummyComplaint(created_at=now - timedelta(hours=60), status="IN_PROGRESS")
    a = DummyAnalysis(priority="MEDIUM")  # 48h SLA -> 12h breached
    info = compute_sla_info(c, a)

    assert info["is_breached"] is True
    assert "Breached" in info["badge_text"]


def test_sla_resolved():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    c = DummyComplaint(created_at=now - timedelta(hours=50), status="RESOLVED")
    a = DummyAnalysis(priority="HIGH")
    info = compute_sla_info(c, a)

    assert info["is_resolved"] is True
    assert info["badge_text"] == "SLA Met"
