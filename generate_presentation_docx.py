"""
Script to generate the comprehensive Presentation & Functional Specification Word Document
for the University of Education Lahore - AI Student Complaint Management System.
"""
import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def set_cell_background(cell, hex_color):
    """Sets the background color of a table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tc_pr.append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Sets inner margins (padding) for a table cell in dxa (1 pt = 20 dxa)."""
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tc_mar.append(node)
    tc_pr.append(tc_mar)


def create_callout_box(doc, title, text, border_color="002B7A", bg_color="F0F4F8"):
    """Creates a beautiful callout/note box."""
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Inches(6.5)

    cell = table.cell(0, 0)
    set_cell_background(cell, bg_color)
    set_cell_margins(cell, top=140, bottom=140, left=200, right=180)

    # Left border styling
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = OxmlElement('w:tcBorders')
    
    left_b = OxmlElement('w:left')
    left_b.set(qn('w:val'), 'single')
    left_b.set(qn('w:sz'), '24')  # 3pt
    left_b.set(qn('w:space'), '0')
    left_b.set(qn('w:color'), border_color)
    tc_borders.append(left_b)

    for side in ['top', 'bottom', 'right']:
        b = OxmlElement(f'w:{side}')
        b.set(qn('w:val'), 'none')
        tc_borders.append(b)
    tc_pr.append(tc_borders)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    run_t = p.add_run(f"📌 {title}\n")
    run_t.bold = True
    run_t.font.name = "Segoe UI"
    run_t.font.size = Pt(10.5)
    run_t.font.color.rgb = RGBColor(0x00, 0x2B, 0x7A)

    run_body = p.add_run(text)
    run_body.font.name = "Segoe UI"
    run_body.font.size = Pt(9.5)
    run_body.font.color.rgb = RGBColor(0x37, 0x41, 0x51)

    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(4)


def add_styled_heading(doc, text, level):
    """Adds a styled heading with brand colors."""
    h = doc.add_heading(text, level=level)
    h.paragraph_format.keep_with_next = True
    run = h.runs[0]
    run.font.name = "Segoe UI Semibold"
    if level == 1:
        run.font.size = Pt(18)
        run.font.color.rgb = RGBColor(0x00, 0x2B, 0x7A)  # Navy Blue
        h.paragraph_format.space_before = Pt(16)
        h.paragraph_format.space_after = Pt(6)
    elif level == 2:
        run.font.size = Pt(14)
        run.font.color.rgb = RGBColor(0x0B, 0x45, 0xA0)  # Accent Blue
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(4)
    elif level == 3:
        run.font.size = Pt(11.5)
        run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)  # Charcoal
        h.paragraph_format.space_before = Pt(8)
        h.paragraph_format.space_after = Pt(2)
    return h


def format_table_headers(table, col_widths, headers, bg_color="002B7A"):
    """Styles table header row."""
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], bg_color)
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=140, right=140)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for r in p.runs:
            r.font.name = "Segoe UI"
            r.font.size = Pt(9.5)
            r.font.bold = True
            r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    for row_idx, row in enumerate(table.rows):
        for col_idx, width in enumerate(col_widths):
            row.cells[col_idx].width = width
            if row_idx > 0:
                set_cell_margins(row.cells[col_idx], top=80, bottom=80, left=120, right=120)
                if row_idx % 2 == 1:
                    set_cell_background(row.cells[col_idx], "F9FAFB")
                else:
                    set_cell_background(row.cells[col_idx], "FFFFFF")
                p = row.cells[col_idx].paragraphs[0]
                for r in p.runs:
                    r.font.name = "Segoe UI"
                    r.font.size = Pt(9)
                    r.font.color.rgb = RGBColor(0x37, 0x41, 0x51)


def build_word_document():
    doc = Document()

    # Page setup - Margins 0.8 inch
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

        # Header & Footer
        header = section.header
        hp = header.paragraphs[0]
        hp.text = "University of Education, Lahore — AI Student Complaint Management System"
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if hp.runs:
            hp.runs[0].font.name = "Segoe UI"
            hp.runs[0].font.size = Pt(8.5)
            hp.runs[0].font.color.rgb = RGBColor(0x9C, 0xA3, 0xAF)

        footer = section.footer
        fp = footer.paragraphs[0]
        fp.text = "Comprehensive Presentation & Functional Specification Document | Microsoft Enterprise Standard"
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if fp.runs:
            fp.runs[0].font.name = "Segoe UI"
            fp.runs[0].font.size = Pt(8.5)
            fp.runs[0].font.color.rgb = RGBColor(0x9C, 0xA3, 0xAF)

    # -------------------------------------------------------------
    # COVER PAGE / TITLE BLOCK
    # -------------------------------------------------------------
    p_title_pre = doc.add_paragraph()
    p_title_pre.paragraph_format.space_before = Pt(36)
    p_title_pre.paragraph_format.space_after = Pt(4)
    r_sub = p_title_pre.add_run("UNIVERSITY OF EDUCATION, LAHORE")
    r_sub.font.name = "Segoe UI Semibold"
    r_sub.font.size = Pt(13)
    r_sub.font.bold = True
    r_sub.font.color.rgb = RGBColor(0x0B, 0x45, 0xA0)

    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(12)
    r_main = p_title.add_run("AI-Assisted Multi-Tier Grievance & Complaint Management Portal")
    r_main.font.name = "Segoe UI"
    r_main.font.size = Pt(26)
    r_main.font.bold = True
    r_main.font.color.rgb = RGBColor(0x00, 0x2B, 0x7A)

    p_tag = doc.add_paragraph()
    p_tag.paragraph_format.space_before = Pt(0)
    p_tag.paragraph_format.space_after = Pt(24)
    r_tag = p_tag.add_run("Complete System Architecture, Multi-Portal Screen-by-Screen Functional Specifications, Enterprise Upgrades & Presentation Defense Guide")
    r_tag.font.name = "Segoe UI"
    r_tag.font.size = Pt(12)
    r_tag.font.italic = True
    r_tag.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)

    # Metadata Table
    meta_table = doc.add_table(rows=6, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_widths = [Inches(2.2), Inches(4.5)]
    meta_data = [
        ("Project Title:", "AI Student Complaint Management System (UE CMS)"),
        ("Institution:", "University of Education, Lahore (Multi-Campus System)"),
        ("System Standard:", "Enterprise Grade (Microsoft / Corporate Level)"),
        ("Key Technologies:", "FastAPI, SQLAlchemy, MySQL 8.0, Jinja2, Bootstrap 5, AI Triage Engine"),
        ("User Roles Covered:", "Student, Employee, Professor, Campus Administrator, Higher Authority (VC / Registrar / Controller)"),
        ("Document Purpose:", "Official Project Presentation, System Walkthrough, Viva Voce & Technical Defense"),
    ]
    for row_idx, (k, v) in enumerate(meta_data):
        row = meta_table.rows[row_idx]
        row.cells[0].text = k
        row.cells[1].text = v
        set_cell_background(row.cells[0], "F3F4F6")
        set_cell_background(row.cells[1], "FFFFFF")
        set_cell_margins(row.cells[0], 80, 80, 120, 120)
        set_cell_margins(row.cells[1], 80, 80, 120, 120)
        row.cells[0].paragraphs[0].runs[0].font.bold = True
        row.cells[0].paragraphs[0].runs[0].font.size = Pt(9.5)
        row.cells[0].paragraphs[0].runs[0].font.color.rgb = RGBColor(0x00, 0x2B, 0x7A)
        row.cells[1].paragraphs[0].runs[0].font.size = Pt(9.5)
        row.cells[1].paragraphs[0].runs[0].font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
        row.cells[0].width = meta_widths[0]
        row.cells[1].width = meta_widths[1]

    doc.add_page_break()

    # -------------------------------------------------------------
    # SECTION 1: EXECUTIVE PROJECT OVERVIEW
    # -------------------------------------------------------------
    add_styled_heading(doc, "1. Executive Summary & Problem Statement", level=1)
    
    p = doc.add_paragraph(
        "Higher education institutions face significant challenges in handling student grievances efficiently, "
        "transparently, and securely. Traditional paper-based or basic ticketing portals suffer from severe bottlenecks: "
        "complaints get lost between campuses, turnaround times exceed acceptable standards with no SLA accountability, "
        "and vulnerable students fear lodging sensitive reports due to lack of strict confidentiality protections."
    )
    p.runs[0].font.name = "Segoe UI"
    p.runs[0].font.size = Pt(10)

    p2 = doc.add_paragraph(
        "The University of Education AI Complaint Management System is an end-to-end, enterprise-grade governance platform "
        "architected to resolve these challenges across all campuses. Powered by a high-throughput Python FastAPI backend, "
        "relational MySQL persistence, and integrated AI automated triage, it guarantees institutional transparency, "
        "strict role-based access control (RBAC), multi-tier escalation hierarchy, and real-time SLA breach surveillance."
    )
    p2.runs[0].font.name = "Segoe UI"
    p2.runs[0].font.size = Pt(10)

    create_callout_box(
        doc,
        "Core Architectural Mandate",
        "The entire platform operates under a Zero Breaking Changes principle: all 7 enterprise upgrades "
        "(SLA badges, CSV exports, official printable dossiers, in-app bell notifications, student CSAT 5-star ratings, "
        "two-way clarification threads with strict confidentiality protection, and diagnostics monitoring) integrate "
        "cleanly into existing interfaces with zero disruption to daily academic operations."
    )

    # -------------------------------------------------------------
    # SECTION 2: SYSTEM ARCHITECTURE & ROLE ECOSYSTEM
    # -------------------------------------------------------------
    add_styled_heading(doc, "2. System Architecture & 5-Role Ecosystem", level=1)

    p = doc.add_paragraph(
        "The system connects 5 distinct university stakeholder roles in a synchronized, governed workflow:"
    )
    p.runs[0].font.name = "Segoe UI"
    p.runs[0].font.size = Pt(10)

    roles_table = doc.add_table(rows=6, cols=3)
    roles_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    roles_widths = [Inches(1.5), Inches(2.2), Inches(3.0)]
    roles_headers = ["User Role", "Target Audience", "Primary Responsibilities & Scope"]
    roles_data = [
        ("Student", "Enrolled university students", "Lodge general/confidential grievances, upload evidence, track multi-stage progress, submit 5-star CSAT ratings, and clarify details."),
        ("Employee / Staff", "Department officers (IT, Accounts, Library, Transport, Hostel)", "Review assigned departmental complaints, log internal actions, update operational status, and collaborate directly with Campus Admin."),
        ("Professor", "Faculty members & academic supervisors", "Assess academic complaints, grade disputes, and departmental classroom concerns; provide academic findings and resolutions."),
        ("Campus Admin", "Campus Complaint Directorate & Registrars", "Central operations hub: AI triage validation, departmental assignment, SLA monitoring, multi-hop escalation to Higher Authorities, and official response dispatch."),
        ("Higher Authority", "Vice Chancellor, Pro-VC, Registrar, Controller of Exams", "Executive oversight across all UE campuses: review escalated cases, re-escalate between senior offices, and issue binding directives."),
    ]
    for r_idx, row in enumerate(roles_data):
        roles_table.rows[r_idx+1].cells[0].text = row[0]
        roles_table.rows[r_idx+1].cells[1].text = row[1]
        roles_table.rows[r_idx+1].cells[2].text = row[2]
    format_table_headers(roles_table, roles_widths, roles_headers)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # -------------------------------------------------------------
    # SECTION 3: SCREEN-BY-SCREEN PAGE SPECIFICATIONS
    # -------------------------------------------------------------
    add_styled_heading(doc, "3. Screen-by-Screen Functional Specifications", level=1)
    
    doc.add_paragraph(
        "The following sections meticulously define every template, screen, UI component, and underlying backend logic "
        "across all modules in the University of Education Complaint Portal."
    ).runs[0].font.size = Pt(10)

    # 3.1 Public & Authentication
    add_styled_heading(doc, "3.1 Public & Authentication Module", level=2)

    screens_auth = [
        ("Login Portal (login.html)", "/login", 
         "Features unified authentication supporting all 5 system roles. Validates user credentials via Bcrypt password hashes, issues secure HTTP-only JWT access tokens, and dynamically redirects users to their appropriate dashboard based on assigned UserRole (Student -> /student/dashboard, Employee -> /employee/dashboard, etc.). Includes 'Remember Me', input validation, and password visibility toggles."),
        ("User Profile & Security (profile.html)", "/profile", 
         "Allows authenticated users to view their university identity profile (Campus, Department, Student ID / Staff ID, Program). Enables secure self-service password updates with current password verification and confirmation checks. Displays account activity metrics."),
        ("Master Portal Frame (base.html)", "Global Template", 
         "The responsive Bootstrap 5 master frame. Houses the UE brand navigation bar, responsive collapse menu, user session pill, and the Enterprise Notification Bell with dynamic unread badges. Features Microsoft-standard styling, WCAG-compliant high contrast color palettes, and global security headers (CSP, X-Frame-Options, CSRF origin verification).")
    ]
    for name, path, desc in screens_auth:
        add_styled_heading(doc, name, level=3)
        p = doc.add_paragraph()
        r1 = p.add_run(f"Endpoint / Route: {path}\n")
        r1.bold = True
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(0x00, 0x2B, 0x7A)
        r2 = p.add_run(desc)
        r2.font.size = Pt(9.5)
        p.paragraph_format.space_after = Pt(6)

    # 3.2 Student Portal
    add_styled_heading(doc, "3.2 Student Portal (Self-Service Grievance Hub)", level=2)

    screens_student = [
        ("Student Dashboard (student_dashboard.html)", "/student/dashboard",
         "The landing center for enrolled students. Features real-time KPI counter tiles (Total Complaints Lodged, In Progress, Awaiting Confirmation, Resolved/Closed). Displays 'Active Issues Needing Action' alert box whenever a complaint is awaiting student resolution confirmation. Includes quick-action tiles for 'Lodge New Complaint' and 'Track Complaints'."),
        ("Lodge Complaint Form (student_complaint_form.html)", "/student/complaints/new",
         "Interactive grievance submission interface. Captures Grievance Category, Target Campus (Main Campus, Bank Road, Multan, Faisalabad, etc.), Specific Subject, Detailed Statement, and Evidence Attachments (PNG/JPG/PDF). Crucially features the 'Strict Confidentiality / Hide My Identity' checkbox which automatically anonymizes the student's records and activates privacy protection."),
        ("My Complaints Directory (student_complaints.html / my_complaints.html)", "/student/complaints",
         "Filterable registry of all student submissions. Shows reference numbers (e.g. CMP-2026-0042), dates, categories, dynamic status badges, and SLA Urgency Badges. Features live search and status filter tabs (All, In Progress, Resolved)."),
        ("Student Complaint Detail View (student_complaint_detail.html)", "/student/complaints/{id}",
         "The comprehensive grievance tracker and interactive interaction hub:\n"
         "• Complaint Statement & Evidence: Full statement with high-resolution image preview.\n"
         "• Official University Response: Displays formal administration remarks post-triage.\n"
         "• Interactive 5-Star CSAT Rating: When status reaches 'RESOLVED_AWAITING_CONFIRMATION', allows student to rate resolution quality from 1 to 5 stars (with live interactive labels: Highly Satisfied to Very Dissatisfied) and choose 'Issue Resolved (Confirm & Close)' or 'Issue Not Resolved (Dispute & Reopen)'.\n"
         "• Two-Way Clarification Thread: Active when non-confidential; allows students to communicate with university admins. When confidential, replaced with a secure Privacy Shield Alert stating two-way communication is disabled for anonymity.\n"
         "• Status Timeline: Vertical tracker showing exact progress (Submitted -> Triage -> Assigned -> In Progress -> Resolved).\n"
         "• Official Dossier Print: Instant print-ready official dossier rendering.\n"
         "• WhatsApp Share: 1-click sharing of complaint details with university helpline or advisors.")
    ]
    for name, path, desc in screens_student:
        add_styled_heading(doc, name, level=3)
        p = doc.add_paragraph()
        r1 = p.add_run(f"Endpoint / Route: {path}\n")
        r1.bold = True
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(0x00, 0x2B, 0x7A)
        r2 = p.add_run(desc)
        r2.font.size = Pt(9.5)
        p.paragraph_format.space_after = Pt(6)

    # 3.3 Employee Portal
    add_styled_heading(doc, "3.3 Employee Portal (Departmental Action Hub)", level=2)

    screens_emp = [
        ("Employee Dashboard (employee_dashboard.html)", "/employee/dashboard",
         "The operational dashboard for university department officers (IT, Accounts, Transport, Hostel, Examination). Presents assigned workload queues, urgent SLA breach alerts, and quick-filter tables. Includes a dedicated section for internal employee equipment/support requests."),
        ("Employee Complaints Directory (employee_complaints.html)", "/employee/complaints",
         "Table listing all grievances formally assigned to the employee's department. Features priority badges (CRITICAL, HIGH, MEDIUM, LOW) and SLA countdown timer pills."),
        ("Employee Complaint Detail (employee_complaint_detail.html)", "/employee/complaints/{id}",
         "The staff resolution console:\n"
         "• Student Particulars: Real student name/ID if open; masked as '[Confidential Student]' if student requested anonymity.\n"
         "• SLA Urgency Pill: Real-time hours remaining before departmental escalation.\n"
         "• Staff Update Form: Status dropdown (IN_PROGRESS, WAITING_FOR_STUDENT, RESOLVED) and internal actions taken textarea.\n"
         "• Admin Collaboration Notes Card: Dedicated communication channel between the departmental employee and Campus Admin. Staff post progress updates or request admin intervention without exposing confidential student identities."),
        ("Employee Requests Registry & Form (employee_requests.html / employee_request_form.html / employee_request_detail.html)", "/employee/requests",
         "Complete internal requisition system allowing departmental staff to request equipment, maintenance, or policy clarifications from the central Campus Administration, complete with approval workflows and tracking.")
    ]
    for name, path, desc in screens_emp:
        add_styled_heading(doc, name, level=3)
        p = doc.add_paragraph()
        r1 = p.add_run(f"Endpoint / Route: {path}\n")
        r1.bold = True
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(0x00, 0x2B, 0x7A)
        r2 = p.add_run(desc)
        r2.font.size = Pt(9.5)
        p.paragraph_format.space_after = Pt(6)

    # 3.4 Professor Portal
    add_styled_heading(doc, "3.4 Professor Portal (Academic Review Hub)", level=2)

    screens_prof = [
        ("Professor Dashboard (professor_dashboard.html)", "/professor/dashboard",
         "Faculty overview displaying academic grievances, course grade inquiries, and student classroom feedback assigned to the professor or department."),
        ("Professor Review Detail (professor_complaint_detail.html)", "/professor/complaints/{id}",
         "Allows faculty to review academic statements, review attached work/assignments, provide formal academic findings, submit resolution remarks, and dispatch verified explanations back to administration.")
    ]
    for name, path, desc in screens_prof:
        add_styled_heading(doc, name, level=3)
        p = doc.add_paragraph()
        r1 = p.add_run(f"Endpoint / Route: {path}\n")
        r1.bold = True
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(0x00, 0x2B, 0x7A)
        r2 = p.add_run(desc)
        r2.font.size = Pt(9.5)
        p.paragraph_format.space_after = Pt(6)

    # 3.5 Higher Authority Portal
    add_styled_heading(doc, "3.5 Higher Authority Portal (Executive Governance)", level=2)

    screens_auth_port = [
        ("Higher Authority Dashboard (authority_dashboard.html)", "/authority/dashboard",
         "The executive cockpit for top university leadership (Vice Chancellor, Pro-Vice Chancellor, Registrar, Controller of Examinations). Displays university-wide escalated grievances, cross-campus breakdown charts, priority counts, and 1-Click Excel/CSV Export."),
        ("Executive Complaint Review (authority_complaint_detail.html)", "/authority/complaints/{id}",
         "High-level decision and governance console:\n"
         "• Full Dossier: Student particulars (confidentiality-preserved), original statement, evidence.\n"
         "• Executive Status Actions: Update case status (RESOLVED, IN_PROGRESS, UNDER_REVIEW, REJECTED) with official authority resolution comments.\n"
         "• Re-Escalation / Forwarding Form: Forward the case to another Higher Authority office (e.g. VC directs case to Controller of Examinations) with official directives.\n"
         "• Direct Admin Collaboration Notes: Two-way communication card to issue instructions to Campus Admin.\n"
         "• Multi-Hop Escalation Trail: Complete audit of who escalated the case, timestamps, and previous authority notes.")
    ]
    for name, path, desc in screens_auth_port:
        add_styled_heading(doc, name, level=3)
        p = doc.add_paragraph()
        r1 = p.add_run(f"Endpoint / Route: {path}\n")
        r1.bold = True
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(0x00, 0x2B, 0x7A)
        r2 = p.add_run(desc)
        r2.font.size = Pt(9.5)
        p.paragraph_format.space_after = Pt(6)

    # 3.6 Admin Portal
    add_styled_heading(doc, "3.6 Campus Admin Portal (Operations & Administration)", level=2)

    screens_admin = [
        ("Master Admin Dashboard (dashboard.html)", "/admin/dashboard",
         "Central mission control. Features live metric cards (Total, New, Critical, High, Resolved, Pending Review, Duplicates Detected). Real-time filter form (Campus, Category, Priority, Status, Search). Includes 1-Click Excel / CSV Export button and table displaying SLA countdown pills for every active case."),
        ("Master Complaint Console (complaint_detail.html)", "/admin/complaints/{id}",
         "The central processing center:\n"
         "• Card 1: Review & Actions (Status update, department reassignment, authorized handler assignment, response approval).\n"
         "• Card 2: Forward / Escalate to Higher Authority (Select VC, Registrar, etc., with reason and remarks).\n"
         "• Card 3: Student Particulars (Real records or safeguarding confidential badge).\n"
         "• Card 4: Original Complaint Statement & Evidence Attachment Preview.\n"
         "• Card 5: Student Resolution Feedback & CSAT Score (Gold stars and student confirmation).\n"
         "• Card 6: AI-Assisted Triage (Classification confidence circle gauge, suggested priority, category/subcategory, recommended action).\n"
         "• Multi-Tier Clarifications Stream: Multi-party collaboration thread connecting Admin with Students, Employees, and Higher Authorities.\n"
         "• Print Official Dossier & WhatsApp Share: Instant formal documentation and secure sharing.\n"
         "• Card 7: Audit History & Complete Timeline Modal."),
        ("User Management (admin_users.html)", "/admin/users",
         "Full CRUD management of portal user accounts across all roles. Features role changes, campus assignment, account activation/deactivation, and credential provisioning."),
        ("Department Management (admin_departments.html)", "/admin/departments",
         "Campus department mapping and authorized handler assignment. Configures routing rules that connect AI categories to responsible department teams."),
        ("Analytical Reports (admin_reports.html)", "/admin/reports",
         "Executive reporting suite displaying grievance trends, category volume distributions, average resolution turnaround times, and campus performance comparisons."),
        ("System Configuration Settings (admin_settings.html)", "/admin/settings",
         "Institutional settings manager: AI model provider (Claude/Mock), duplicate detection thresholds (window days & text similarity %), SLA response deadlines, and SMTP email credentials."),
        ("System Health & Observability (admin_system_health.html)", "/admin/system-health",
         "Real-time diagnostic center displaying MySQL connection latency (ms), upload folder write status, AI triage status, and University CSAT Scorecard with 5-star rating distribution.")
    ]
    for name, path, desc in screens_admin:
        add_styled_heading(doc, name, level=3)
        p = doc.add_paragraph()
        r1 = p.add_run(f"Endpoint / Route: {path}\n")
        r1.bold = True
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(0x00, 0x2B, 0x7A)
        r2 = p.add_run(desc)
        r2.font.size = Pt(9.5)
        p.paragraph_format.space_after = Pt(6)

    # -------------------------------------------------------------
    # SECTION 4: THE 7 ENTERPRISE MICROSOFT-LEVEL FEATURES
    # -------------------------------------------------------------
    doc.add_page_break()
    add_styled_heading(doc, "4. The 7 Microsoft-Level Enterprise Upgrades", level=1)

    p = doc.add_paragraph(
        "To elevate the project to Microsoft / Corporate standard, 7 specialized features were engineered and verified, "
        "adhering strictly to zero-breaking-change principles and privacy preservation:"
    )
    p.runs[0].font.size = Pt(10)

    feat_table = doc.add_table(rows=8, cols=3)
    feat_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    feat_widths = [Inches(0.6), Inches(2.2), Inches(3.7)]
    feat_headers = ["#", "Enterprise Upgrade", "Technical Architecture & Implementation Details"]
    feat_data = [
        ("1", "Layout Preservation & Stepper Removal", "Visual Complaint Progress Stepper was completely removed per institutional mandate to prevent detail view clutter; original clean Microsoft-style card layout 100% restored across all 6 roles."),
        ("2", "Dynamic SLA Breach Badges & Countdown", "Priority-based SLA engine (Critical: 12h, High: 24h, Medium: 48h, Low: 72h). Renders rounded-pill badges: Green (#DCFCE7) SLA Met, Blue (#EBF3FD) >12h left, Yellow (#FEF3C7) urgent <12h, Red (#FEE2E2) SLA Breached."),
        ("3", "One-Click Excel / CSV Export & Printable Official Dossier + WhatsApp", "RFC 4180 streaming CSV export on Admin & Authority dashboards. High-fidelity @media print stylesheet rendering formal headers, case particulars, and stamp/signature blocks. 1-click WhatsApp instant sharing with URL-encoded parameters."),
        ("4", "In-App Notification Bell & Real-time Dropdown Alerts", "Navbar bell icon with dynamic red pill counter. Dropdown shows 10 latest updates with direct navigation links. Auto-dispatches on complaint submission, assignment, resolution, and escalation. Auto mark-as-read API."),
        ("5", "Student CSAT (5-Star Satisfaction Rating on Resolution)", "Post-resolution verification widget on student portal. Interactive 1-5 gold star rating with dynamic labels. Confirming resolution marks status CLOSED; disputing marks REOPENED with admin alert. Displays gold stars across Student, Admin, and Authority views."),
        ("6", "Two-Way Clarification Thread (Strict Privacy & Multi-Tier)", "Multi-channel collaboration stream. Strict Privacy Rule: permanently blocks two-way messaging for confidential complaints to protect student identity. Multi-Tier: Employee <-> Admin, Admin <-> Student, Admin <-> Higher Authority."),
        ("7", "System Health Diagnostics Dashboard (/healthz & /admin/system-health)", "Lightweight /healthz JSON ping checking MySQL latency, disk write permissions, and AI engine status. Dedicated /admin/system-health dashboard with real-time latency cards and University CSAT distribution bar charts."),
    ]
    for r_idx, row in enumerate(feat_data):
        feat_table.rows[r_idx+1].cells[0].text = row[0]
        feat_table.rows[r_idx+1].cells[1].text = row[1]
        feat_table.rows[r_idx+1].cells[2].text = row[2]
    format_table_headers(feat_table, feat_widths, feat_headers)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # -------------------------------------------------------------
    # SECTION 5: TECHNICAL STACK & DATA MODEL
    # -------------------------------------------------------------
    add_styled_heading(doc, "5. Technical Stack & Database Architecture", level=1)

    tech_p = doc.add_paragraph(
        "The system is built on an enterprise-grade, asynchronous Python stack optimized for high concurrency, "
        "low latency, and ACID relational data integrity:"
    )
    tech_p.runs[0].font.size = Pt(10)

    tech_table = doc.add_table(rows=7, cols=2)
    tech_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    tech_widths = [Inches(2.2), Inches(4.3)]
    tech_headers = ["Layer / Component", "Technology & Design Pattern"]
    tech_data = [
        ("Web Framework", "FastAPI (ASGI, High Concurrency, Asynchronous Request Pipeline)"),
        ("ORM & Data Access", "SQLAlchemy 2.0 (Mapped Column Declarative Dataclasses, Unit of Work)"),
        ("Database Engine", "MySQL 8.0 / MariaDB (InnoDB, Foreign Key Constraints, Indexed Querying)"),
        ("Templating & UI", "Jinja2 + Bootstrap 5.3 + Bootstrap Icons (Responsive, WCAG Compliant)"),
        ("AI Triage Classifier", "Claude 3.5 Sonnet / Multi-Provider AI Engine (Structured JSON Parsing)"),
        ("Authentication & Security", "JWT (JSON Web Tokens) in HTTP-only Cookies + Bcrypt Password Hashing + CSP"),
    ]
    for r_idx, row in enumerate(tech_data):
        tech_table.rows[r_idx+1].cells[0].text = row[0]
        tech_table.rows[r_idx+1].cells[1].text = row[1]
    format_table_headers(tech_table, tech_widths, tech_headers)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    add_styled_heading(doc, "5.1 Core Database Tables & Entity Relationships", level=2)

    db_items = [
        ("users", "Central authentication identity table storing email, password_hash, full_name, role (STUDENT, EMPLOYEE, PROFESSOR, ADMIN, HIGHER_AUTHORITY), campus_id, and authority_name."),
        ("complaints", "The master grievance entity. Stores unique complaint_number (CMP-YYYY-XXXX), user_id, title, complaint_text, originating_campus, target_campus, attachment_path, status, and is_confidential boolean."),
        ("complaint_analysis", "AI classification results: category, subcategory, confidence score, priority (CRITICAL/HIGH/MEDIUM/LOW), assigned_department, and suggested_action."),
        ("complaint_assignments", "Formal departmental routing tracking assigned employee, handler notes, and reassignment history."),
        ("complaint_forwardings", "Escalation tracking table recording forwardings from Admin to Higher Authorities (VC, Registrar, etc.) and between Higher Authorities."),
        ("complaint_feedback", "Records student resolution confirmation, 5-star CSAT satisfaction rating (1-5), remarks, and dispute reopening timestamps."),
        ("complaint_clarifications", "Multi-party two-way communication thread storing sender_id, sender_name, sender_role, message, and timestamp."),
        ("notifications", "In-app and email notification tracking table storing recipient_user_id, subject, body_preview, link, is_read flag, and delivery_status."),
        ("complaint_history", "Immutable audit trail logging every state transition, officer name, timestamp, and previous/new values.")
    ]
    for t_name, t_desc in db_items:
        p = doc.add_paragraph()
        r1 = p.add_run(f"• `{t_name}`: ")
        r1.bold = True
        r1.font.name = "Consolas"
        r1.font.size = Pt(9.5)
        r2 = p.add_run(t_desc)
        r2.font.name = "Segoe UI"
        r2.font.size = Pt(9.5)
        p.paragraph_format.space_after = Pt(3)

    # -------------------------------------------------------------
    # SECTION 6: PRESENTATION & VIVA DEFENSE GUIDE
    # -------------------------------------------------------------
    doc.add_page_break()
    add_styled_heading(doc, "6. Presentation & Viva Voce Defense Guide", level=1)

    doc.add_paragraph(
        "When presenting this project to academic evaluators, university leadership, or technical panels, "
        "highlight the following strategic demonstration flows and responses to potential questions:"
    ).runs[0].font.size = Pt(10)

    qa_items = [
        ("Q1: What makes this portal different from standard ticketing systems?",
         "Three foundational differentiators: (1) Role-Aware Automated AI Triage that classifies category and priority in seconds; "
         "(2) Strict Safeguarding Confidentiality that protects vulnerable students from retaliation; and "
         "(3) A complete multi-campus Higher Authority escalation chain where executive leadership can review and re-route grievances with binding directives."),
        
        ("Q2: How does the system protect confidential complaints?",
         "When a student checks 'Strict Confidentiality', their name and ID are stripped and masked across employee and report views. "
         "Furthermore, the Two-Way Clarification thread is permanently disabled for that complaint so nobody can coerce or communicate with the student, "
         "guaranteeing total whistleblower protection while allowing staff to resolve the underlying issue internally."),
        
        ("Q3: How is SLA compliance enforced?",
         "The compute_sla_info engine tracks real-time elapsed hours against strict institutional priority deadlines (Critical: 12h, High: 24h, Medium: 48h, Low: 72h). "
         "Active cases display dynamic color-coded countdown badges. Cases with under 12 hours turn amber, and breached cases turn red, "
         "allowing administrators to intervene before institutional reputation is impacted."),

        ("Q4: How was Zero Breaking Changes achieved during feature upgrades?",
         "All enterprise features (SLA badges, CSAT, Notifications, Exports, Healthz) were engineered as modular extensions. "
         "Jinjas macros and lightweight Bootstrap components were inserted into pre-existing grid slots without altering parent containers, "
         "preserving familiar workflows for existing users while adding Microsoft-grade capabilities.")
    ]

    for q, a in qa_items:
        p = doc.add_paragraph()
        rq = p.add_run(f"{q}\n")
        rq.bold = True
        rq.font.name = "Segoe UI"
        rq.font.size = Pt(10)
        rq.font.color.rgb = RGBColor(0x00, 0x2B, 0x7A)
        ra = p.add_run(a)
        ra.font.name = "Segoe UI"
        ra.font.size = Pt(9.5)
        p.paragraph_format.space_after = Pt(8)

    add_styled_heading(doc, "6.1 Recommended 5-Minute Live Demo Flow", level=2)
    demo_steps = [
        ("Step 1: Student Submission", "Log in as Student -> Submit a complaint (e.g. 'Lab 3 Wi-Fi connection failure') with photo attachment -> Point out the SLA Urgency Pill and Status Timeline."),
        ("Step 2: AI Triage & Admin Console", "Log in as Admin -> Open complaint -> Show AI Analysis Card (Confidence %, Category, Suggested priority) -> Assign department and handler -> Point out Export to Excel and Printable Dossier."),
        ("Step 3: Executive Escalation", "In Admin view -> Escalate case to 'Controller of Examinations' -> Log in as Higher Authority -> Show complaint appearing in Higher Authority Dashboard across campuses."),
        ("Step 4: Two-Way Collaboration", "Higher Authority sends directive to Admin -> Admin receives bell notification -> Staff collaborates on the clarification stream."),
        ("Step 5: Resolution & CSAT Rating", "Admin marks complaint Resolved -> Student receives notification -> Student opens complaint, clicks 5 Gold Stars (Highly Satisfied), and submits -> Show status turning CLOSED and gold stars rendering on Admin and Authority screens."),
        ("Step 6: System Diagnostics", "Navigate to /admin/system-health -> Show real-time DB latency and CSAT Scorecard distribution.")
    ]
    for step_title, step_desc in demo_steps:
        p = doc.add_paragraph()
        r1 = p.add_run(f"• {step_title}: ")
        r1.bold = True
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(0x0B, 0x45, 0xA0)
        r2 = p.add_run(step_desc)
        r2.font.size = Pt(9.5)
        p.paragraph_format.space_after = Pt(4)

    # Save document
    filename = "University_of_Education_Complaint_Management_System_Presentation_Document.docx"
    doc.save(filename)
    print(f"Document successfully created: {os.path.abspath(filename)}")


if __name__ == "__main__":
    build_word_document()
