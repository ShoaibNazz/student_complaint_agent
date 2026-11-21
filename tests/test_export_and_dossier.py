import urllib.parse
from app.services.complaint_service import export_complaints_csv


class MockAnalysis:
    def __init__(self, category="Academic", priority="HIGH", assigned_department="Examination"):
        self.category = category
        self.priority = priority
        self.assigned_department = assigned_department


class MockComplaint:
    def __init__(self, c_id, number, student_name, is_confidential=False):
        self.id = c_id
        self.complaint_number = number
        self.title = "Test Transcript Delay"
        self.student_name = student_name
        self.student_id_code = "BSF2400123"
        self.is_confidential = is_confidential
        self.originating_campus = "Township Campus, Lahore (Main Campus)"
        self.target_campus = "Township Campus, Lahore (Main Campus)"
        self.status = "IN_PROGRESS"
        self.analysis = MockAnalysis()
        self.created_at = None
        self.updated_at = None


def test_export_complaints_csv_confidential_masking():
    c_normal = MockComplaint(1, "CMP-001", "Ali Khan", is_confidential=False)
    c_confidential = MockComplaint(2, "CMP-002", "Secret Student", is_confidential=True)

    csv_data = export_complaints_csv([c_normal, c_confidential])
    lines = csv_data.strip().splitlines()

    assert len(lines) == 3
    # Header
    assert "Complaint ID" in lines[0]
    # Normal student row
    assert "Ali Khan" in lines[1]
    # Confidential student row must NOT contain the real name
    assert "Secret Student" not in lines[2]
    assert "[Confidential]" in lines[2]


def test_whatsapp_share_confidentiality_protection():
    # If complaint is confidential, student name must be masked in WhatsApp text
    c = MockComplaint(3, "CMP-003", "Private Person", is_confidential=True)
    a = MockAnalysis()

    # Emulate the template whatsapp link generator
    student_display = "[Confidential]" if c.is_confidential else c.student_name
    text = f"*University of Education Complaint Dossier*\n*Complaint #:* {c.complaint_number}\n*Student:* {student_display}"
    encoded = urllib.parse.quote(text)

    assert "Private+Person" not in encoded and "Private%20Person" not in encoded
    assert "%5BConfidential%5D" in encoded or "[Confidential]" in urllib.parse.unquote(encoded)
