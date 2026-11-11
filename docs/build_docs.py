"""Generate professional DOCX and PDF database documentation."""
from __future__ import annotations

import os
from pathlib import Path

# --- 1. Generate DOCX ---
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

doc = docx.Document()
for s in doc.sections:
    s.top_margin = Inches(1)
    s.bottom_margin = Inches(1)
    s.left_margin = Inches(1)
    s.right_margin = Inches(1)

NAVY = RGBColor(0, 31, 84)
SECONDARY = RGBColor(0, 43, 122)
TEXT_DARK = RGBColor(15, 23, 42)
MUTED = RGBColor(100, 116, 139)

tp = doc.add_paragraph()
tp.paragraph_format.space_before = Pt(0)
tp.paragraph_format.space_after = Pt(4)
tr = tp.add_run("University Complaint Management Portal")
tr.font.name = "Arial"
tr.font.size = Pt(22)
tr.font.bold = True
tr.font.color.rgb = NAVY

sp = doc.add_paragraph()
sp.paragraph_format.space_after = Pt(16)
sr = sp.add_run("Relational Database Design, Data Dictionary & 3NF Normalization Specification")
sr.font.name = "Arial"
sr.font.size = Pt(12)
sr.font.color.rgb = MUTED

def docx_h1(text: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    r.font.name = "Arial"
    r.font.size = Pt(14)
    r.font.bold = True
    r.font.color.rgb = NAVY
    return p

def docx_h2(text: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(text)
    r.font.name = "Arial"
    r.font.size = Pt(11)
    r.font.bold = True
    r.font.color.rgb = SECONDARY
    return p

def docx_p(text: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    r = p.add_run(text)
    r.font.name = "Arial"
    r.font.size = Pt(9.5)
    r.font.color.rgb = TEXT_DARK
    return p

def docx_bullet(text: str):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text)
    r.font.name = "Arial"
    r.font.size = Pt(9.5)
    r.font.color.rgb = TEXT_DARK
    return p

docx_h1("1. Executive Overview")
docx_p("The University Complaint Management Portal is an enterprise grievance handling, AI classification, automated triage, and stage-based workflow system designed for higher education institutions. This document delineates the architectural design, normalization justification, data dictionary, relational constraints, and referential integrity mechanisms implemented across the portal MySQL relational database.")
docx_bullet("Primary Database Technology: MySQL 8.0+ (InnoDB Engine, utf8mb4_unicode_ci)")
docx_bullet("Total Relational Entities: 18 Normalized Tables (Zero legacy SQLite dependencies)")
docx_bullet("Foreign Key Constraints: 38 Foreign Keys enforcing referential integrity")
docx_bullet("Normalization Standard: 3NF Certified (1NF atomic, 2NF full dependency, 3NF role subtyping)")
docx_bullet("Data State: Clean installation schema with strictly zero dummy or seed records")

docx_h1("2. Database Normalization (1NF, 2NF, 3NF)")
docx_h2("First Normal Form (1NF)")
docx_p("First Normal Form dictates that all column values must be atomic (indivisible) and there must be no repeating groups. The previous legacy schema stored served campuses as a denormalized comma-delimited string (e.g. 'Township, Multan'). In the new schema, this anti-pattern is completely eliminated through the department_campuses associative table, ensuring true 1NF atomicity.")

docx_h2("Second Normal Form (2NF)")
docx_p("Second Normal Form requires 1NF compliance and that all non-key attributes are fully functionally dependent on the entire primary key. In all single-column primary key tables, partial dependencies are mathematically impossible. In the composite junction table department_campuses, the primary key is (department_id, campus_id) with zero dependent non-key attributes.")

docx_h2("Third Normal Form (3NF)")
docx_p("Third Normal Form requires 2NF compliance and the elimination of transitive dependencies (non-key columns depending on other non-key columns). In the redesigned schema, student academic attributes (program, batch_year), employee employment details (department_id, role_designation, is_faculty), and administrator credentials (admin_id, permission_level) are separated into normalized 1:1 subtype tables referencing users(id) via UNIQUE foreign keys.")

docx_h1("3. Relational Cardinality & Integrity Summary")
card_table = doc.add_table(rows=1, cols=5)
card_table.alignment = WD_TABLE_ALIGNMENT.CENTER
headers = ["Primary Entity", "Foreign Entity", "Cardinality", "Foreign Key Column", "Cascade Action"]
for i, h in enumerate(headers):
    cell = card_table.rows[0].cells[i]
    cell.text = h
    shd = parse_xml(r'<w:shd {} w:fill="001F54"/>'.format(nsdecls("w")))
    cell._tc.get_or_add_tcPr().append(shd)
    p = cell.paragraphs[0]
    p.runs[0].font.name = "Arial"
    p.runs[0].font.size = Pt(8.5)
    p.runs[0].font.bold = True
    p.runs[0].font.color.rgb = RGBColor(255, 255, 255)

card_rows = [
    ("users", "students", "1:1", "user_id (UNIQUE)", "CASCADE"),
    ("users", "employees", "1:1", "user_id (UNIQUE)", "CASCADE"),
    ("users", "admins", "1:1", "user_id (UNIQUE)", "CASCADE"),
    ("complaints", "complaint_analyses", "1:1", "complaint_id (UNIQUE)", "CASCADE"),
    ("complaints", "complaint_feedback", "1:1", "complaint_id (UNIQUE)", "CASCADE"),
    ("departments", "department_campuses", "1:M (M:N)", "department_id (PK, FK)", "CASCADE"),
    ("campuses", "department_campuses", "1:M (M:N)", "campus_id (PK, FK)", "CASCADE"),
    ("campuses", "users", "1:M", "campus_id", "SET NULL"),
    ("departments", "employees", "1:M", "department_id", "SET NULL"),
    ("users", "complaints", "1:M", "user_id", "SET NULL"),
    ("complaints", "complaint_status_history", "1:M", "complaint_id", "CASCADE"),
    ("complaints", "complaint_assignments", "1:M", "complaint_id", "CASCADE"),
    ("complaints", "complaint_forwardings", "1:M", "complaint_id", "CASCADE"),
    ("users", "employee_requests", "1:M", "user_id", "CASCADE"),
    ("employee_requests", "request_approvals", "1:M", "request_id", "CASCADE"),
    ("users", "notifications", "1:M", "recipient_user_id", "SET NULL"),
    ("users", "audit_logs", "1:M", "user_id", "SET NULL"),
]

for row in card_rows:
    cells = card_table.add_row().cells
    for i, val in enumerate(row):
        cells[i].text = val
        p = cells[i].paragraphs[0]
        p.runs[0].font.name = "Arial"
        p.runs[0].font.size = Pt(8.0)
        p.runs[0].font.color.rgb = TEXT_DARK

docx_h1("4. Table Catalog & Data Dictionary Overview")
docx_p("The database comprises 18 normalized tables: campuses, departments, department_campuses, users, students, employees, admins, complaints, complaint_analyses, complaint_status_history, complaint_assignments, complaint_feedback, complaint_forwardings, notifications, employee_requests, request_approvals, audit_logs, and university_directory.")
docx_p("Every table is created with InnoDB engine, utf8mb4 encoding, explicit Primary Keys, Foreign Keys, cascading rules, and secondary indexes on query-intensive columns.")

doc.save("docs/DATABASE_DOCUMENTATION.docx")
print("DOCX created successfully at docs/DATABASE_DOCUMENTATION.docx")


# --- 2. Generate PDF ---
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

pdf_path = "docs/DATABASE_DOCUMENTATION.pdf"
pdf_doc = SimpleDocTemplate(
    pdf_path,
    pagesize=letter,
    leftMargin=0.75 * inch,
    rightMargin=0.75 * inch,
    topMargin=0.75 * inch,
    bottomMargin=0.75 * inch,
)

styles = getSampleStyleSheet()
NAVY_C = colors.HexColor("#001F54")
SECONDARY_C = colors.HexColor("#002B7A")
DARK_C = colors.HexColor("#0F172A")
MUTED_C = colors.HexColor("#64748B")
LIGHT_BG_C = colors.HexColor("#F8FAFC")

t_style = ParagraphStyle("T", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=NAVY_C, spaceAfter=4)
s_style = ParagraphStyle("S", parent=styles["Normal"], fontName="Helvetica", fontSize=10, leading=14, textColor=MUTED_C, spaceAfter=12)
h1_s = ParagraphStyle("H1S", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=NAVY_C, spaceBefore=12, spaceAfter=4)
h2_s = ParagraphStyle("H2S", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=SECONDARY_C, spaceBefore=8, spaceAfter=3)
b_s = ParagraphStyle("BS", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=12, textColor=DARK_C, spaceAfter=5)
bl_s = ParagraphStyle("BLS", parent=b_s, leftIndent=12, spaceAfter=3)
th_s = ParagraphStyle("THS", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.white)
tc_s = ParagraphStyle("TCS", parent=styles["Normal"], fontName="Helvetica", fontSize=7.0, leading=9, textColor=DARK_C)
tcb_s = ParagraphStyle("TCBS", parent=tc_s, fontName="Helvetica-Bold")

story = [
    Paragraph("University Complaint Management Portal", t_style),
    Paragraph("Relational Database Design, Data Dictionary & 3NF Normalization Specification", s_style),
    HRFlowable(width="100%", thickness=1.5, color=NAVY_C, spaceAfter=10),
    Paragraph("1. Executive Overview", h1_s),
    Paragraph("The University Complaint Management Portal provides an enterprise-grade grievance handling, AI classification, automated triage, and stage-based workflow system for higher education institutions. This document delineates the architectural design, normalization justification, data dictionary, relational constraints, and referential integrity mechanisms implemented across the portal MySQL relational database.", b_s),
    Paragraph("&bull; <b>Primary Database Technology:</b> MySQL 8.0+ (InnoDB Engine, utf8mb4_unicode_ci)", bl_s),
    Paragraph("&bull; <b>Total Relational Entities:</b> 18 Normalized Tables (Zero legacy SQLite dependencies)", bl_s),
    Paragraph("&bull; <b>Foreign Key Constraints:</b> 38 Foreign Keys enforcing referential integrity", bl_s),
    Paragraph("&bull; <b>Normalization Standard:</b> 3NF Certified (1NF atomic, 2NF full dependency, 3NF role subtyping)", bl_s),
    Paragraph("&bull; <b>Data State:</b> Clean installation schema with strictly zero dummy or seed records", bl_s),
    Paragraph("2. Database Normalization (1NF, 2NF, 3NF)", h1_s),
    Paragraph("First Normal Form (1NF)", h2_s),
    Paragraph("First Normal Form dictates that all column values must be atomic (indivisible) and there must be no repeating groups. The previous legacy schema stored served campuses as a denormalized comma-delimited string. In the new schema, this anti-pattern is completely eliminated through the <code>department_campuses</code> associative table, ensuring true 1NF atomicity.", b_s),
    Paragraph("Second Normal Form (2NF)", h2_s),
    Paragraph("Second Normal Form requires 1NF compliance and that all non-key attributes are fully functionally dependent on the entire primary key. In all single-column primary key tables, partial dependencies are mathematically impossible. In the composite junction table <code>department_campuses</code>, the key is <code>(department_id, campus_id)</code> with zero dependent non-key attributes.", b_s),
    Paragraph("Third Normal Form (3NF)", h2_s),
    Paragraph("Third Normal Form requires 2NF compliance and the elimination of transitive dependencies (non-key columns depending on other non-key columns). In the redesigned schema, student academic attributes (<code>program</code>, <code>batch_year</code>), employee employment details (<code>department_id</code>, <code>role_designation</code>, <code>is_faculty</code>), and administrator credentials (<code>admin_id</code>, <code>permission_level</code>) are separated into normalized 1:1 subtype tables referencing <code>users(id)</code> via UNIQUE foreign keys.", b_s),
    Paragraph("3. Relational Cardinality & Integrity Summary", h1_s),
]

t_rows = [[
    Paragraph("Primary Entity", th_s),
    Paragraph("Foreign Entity", th_s),
    Paragraph("Cardinality", th_s),
    Paragraph("Foreign Key Column", th_s),
    Paragraph("Cascade Action", th_s),
]]
for p_e, f_e, cd, fk_c, cas_c in card_rows:
    t_rows.append([
        Paragraph(p_e, tcb_s),
        Paragraph(f_e, tc_s),
        Paragraph(cd, tcb_s),
        Paragraph(fk_c, tc_s),
        Paragraph(cas_c, tc_s),
    ])

tbl = Table(t_rows, colWidths=[1.3*inch, 1.4*inch, 1.0*inch, 1.9*inch, 1.2*inch])
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY_C),
    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG_C]),
    ("TOPPADDING", (0, 0), (-1, -1), 2.5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
]))
story.append(tbl)

story.append(Paragraph("4. Table Catalog & Data Dictionary Overview", h1_s))
story.append(Paragraph(
    "The portal relational database consists of 18 tables: <b>campuses</b>, <b>departments</b>, "
    "<b>department_campuses</b> (M:N associative mapping), <b>users</b> (central identity and authentication credentials), "
    "<b>students</b> (1:1 student profile), <b>employees</b> (1:1 staff and faculty profile), "
    "<b>admins</b> (1:1 administrator privileges), <b>complaints</b> (central grievance filings), "
    "<b>complaint_analyses</b> (1:1 AI classification and draft responses), <b>complaint_status_history</b> (1:M chronological transitions), "
    "<b>complaint_assignments</b> (1:M departmental routing), <b>complaint_feedback</b> (1:1 student confirmation and ratings), "
    "<b>complaint_forwardings</b> (1:M executive escalation trail), <b>notifications</b> (transactional messaging records), "
    "<b>employee_requests</b> (staff administrative applications), <b>request_approvals</b> (1:M stage-based approval trail), "
    "<b>audit_logs</b> (security and access tracking), and <b>university_directory</b> (official identity roster).",
    b_s
))

pdf_doc.build(story)
print("PDF created successfully at docs/DATABASE_DOCUMENTATION.pdf")
