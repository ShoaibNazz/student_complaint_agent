"""Script to seed campuses, departments, administrative test users, and import the 42 students with pending complaints."""
from __future__ import annotations

import csv
from pathlib import Path
from sqlalchemy import select, text
from app.core.config import get_settings, load_json_config
from app.core.security import hash_password
from app.database.database import SessionLocal
from app.models.campus import Campus, DepartmentRecord, department_campuses
from app.models.complaint import Complaint
from app.models.analysis import ComplaintAnalysis
from app.models.history import ComplaintStatusHistory
from app.models.enums import ComplaintStatus, UserRole
from app.models.user import User, Student, Employee, Admin, UniversityDirectory
from app.utils.time import utcnow


def seed_campuses_and_departments(db):
    print("1. Checking & Seeding Campuses...")
    campus_data = [
        ("Township Campus, Lahore (Main Campus)", "UE-LHR-MAIN", "Central Campus, College Road, Township, Lahore"),
        ("Lower Mall Campus, Lahore", "UE-LHR-LM", "Historic Lower Mall Campus, Lahore"),
        ("Bank Road Campus, Lahore", "UE-LHR-BR", "Bank Road Campus for Women, Lahore"),
        ("Attock Campus", "UE-ATK", "Attock Constituent Campus, Punjab"),
        ("Dera Ghazi Khan Campus", "UE-DGK", "DG Khan Constituent Campus, Punjab"),
        ("Faisalabad Campus", "UE-FSD", "Faisalabad Constituent Campus, Samanabad, Faisalabad"),
        ("Jauharabad Campus", "UE-JHD", "Jauharabad Constituent Campus, Khushab, Punjab"),
        ("Multan Campus", "UE-MLT", "Multan Constituent Campus, Bosan Road, Multan"),
        ("Vehari Campus", "UE-VHR", "Vehari Constituent Campus, Punjab"),
    ]
    campus_objs = {}
    for name, code, desc in campus_data:
        c = db.scalars(select(Campus).where(Campus.name == name)).first()
        if not c:
            c = Campus(name=name, code=code, location="Punjab, Pakistan", description=desc, is_active=True)
            db.add(c)
            db.flush()
        campus_objs[name] = c

    print("2. Checking & Seeding Departments...")
    depts_json = load_json_config("departments")
    dept_objs = {}
    for d in depts_json.get("departments", []):
        d_name = d.get("name")
        d_desc = d.get("description", "")
        if d_name:
            rec = db.scalars(select(DepartmentRecord).where(DepartmentRecord.name == d_name)).first()
            if not rec:
                rec = DepartmentRecord(name=d_name, description=d_desc, is_active=True)
                db.add(rec)
                db.flush()
            dept_objs[d_name] = rec
            # Link to Multan Campus in junction table if not present
            multan = campus_objs.get("Multan Campus")
            if multan and multan not in rec.campuses:
                rec.campuses.append(multan)

    db.commit()
    print(f"-> Verified {len(campus_objs)} campuses and {len(dept_objs)} departments.")
    return campus_objs, dept_objs


def seed_admin_and_employees(db, campus_objs, dept_objs):
    print("3. Checking & Seeding Multan Admin and Department Employees...")
    multan = campus_objs["Multan Campus"]

    # Multan Admin
    admin_user = db.scalars(select(User).where(User.email == "admin.multan@ue.edu.pk")).first()
    if not admin_user:
        admin_user = User(
            full_name="Multan Administrator",
            email="admin.multan@ue.edu.pk",
            password_hash=hash_password("adminpassword"),
            role="ADMIN",
            campus_id=multan.id,
            is_active=True,
        )
        db.add(admin_user)
        db.flush()
        adm = Admin(
            user_id=admin_user.id,
            admin_id="ADMIN-MLT-001",
            designation="Administrator",
            permission_level="SUPER_ADMIN",
        )
        db.add(adm)
        db.commit()
        print("-> Created Multan Admin (admin.multan@ue.edu.pk / ADMIN-MLT-001)")

    # Multan Employees for different departments
    employees_to_seed = [
        ("Dr. Tariq Mahmood", "tariq.mahmood@ue.edu.pk", "EMP240011", "Department of Information Sciences", "Professor", True),
        ("Bilal Ahmed", "bilal.ahmed@ue.edu.pk", "EMP240022", "Department of Mathematics", "Lecturer", False),
        ("Farah Naz", "farah.naz@ue.edu.pk", "EMP240033", "Department of Education", "Head of Department (HOD)", False),
        ("Muhammad Asif", "asif.admin@ue.edu.pk", "EMP240044", "Administration / Maintenance", "Assistant Registrar", False),
        ("Rashid IT Officer", "rashid.it@ue.edu.pk", "EMP240055", "IT Department", "IT Officer", False),
        ("Naseem Library Officer", "naseem.library@ue.edu.pk", "EMP240066", "Library Department", "Librarian", False),
        ("Zahid Accounts Officer", "zahid.accounts@ue.edu.pk", "EMP240077", "Accounts Department", "Accounts Officer", False),
    ]

    for name, email, emp_id, dept_name, role_desig, is_fac in employees_to_seed:
        existing = db.scalars(select(User).where(User.email == email)).first()
        if not existing:
            dept_rec = dept_objs.get(dept_name)
            emp_user = User(
                full_name=name,
                email=email,
                password_hash=hash_password("password123"),
                role="PROFESSOR" if is_fac else "EMPLOYEE",
                campus_id=multan.id,
                is_active=True,
            )
            db.add(emp_user)
            db.flush()
            emp_profile = Employee(
                user_id=emp_user.id,
                employee_id=emp_id,
                department_id=dept_rec.id if dept_rec else None,
                role_designation=role_desig,
                is_faculty=is_fac,
            )
            db.add(emp_profile)
            db.commit()
            print(f"-> Created Employee {name} ({dept_name})")


def classify_complaint(title: str, text: str) -> tuple[str, str, str]:
    """Returns (category, required_department, priority)."""
    t_lower = (title + " " + text).lower()

    if any(k in t_lower for k in ["wi-fi", "internet", "network", "connectivity", "access point"]):
        return "IT / Portal / LMS", "IT Department", "MEDIUM"
    elif any(k in t_lower for k in ["computer", "pc", "freeze", "systems running slowly", "workstation", "keyboard", "mouse", "software", "development tools"]):
        return "IT / Portal / LMS", "Department of Information Sciences", "MEDIUM"
    elif any(k in t_lower for k in ["portal", "login", "authentication", "lms", "uploading assignments"]):
        return "IT / Portal / LMS", "IT Department", "HIGH"
    elif any(k in t_lower for k in ["washroom", "cleanliness", "water cooler", "drinking water", "drainage"]):
        return "Facilities / Maintenance", "Administration / Maintenance", "MEDIUM"
    elif any(k in t_lower for k in ["chair", "seating", "fans", "lighting", "desk", "whiteboard", "air conditioner", "projector", "staircase", "electrical sockets"]):
        return "Facilities / Maintenance", "Administration / Maintenance", "MEDIUM"
    elif any(k in t_lower for k in ["library", "book", "textbook", "reading list", "e-journal", "study space"]):
        return "Library", "Library Department", "LOW"
    elif any(k in t_lower for k in ["fee", "payment", "counter"]):
        return "Fees / Finance", "Accounts Department", "MEDIUM"
    elif any(k in t_lower for k in ["shuttle", "transport", "bus"]):
        return "Transport", "Transport Department", "MEDIUM"
    elif any(k in t_lower for k in ["transcript", "bonafide certificate", "id card", "student record", "correction"]):
        return "Academic", "Academic Administration", "MEDIUM"
    elif any(k in t_lower for k in ["timetable", "schedule", "overlapping", "lecture room", "noise"]):
        return "Academic", "Academic Department", "MEDIUM"
    elif any(k in t_lower for k in ["examination", "seating plan", "exam"]):
        return "Examination", "Examination Department", "HIGH"
    elif any(k in t_lower for k in ["sports", "playing surface"]):
        return "Facilities / Maintenance", "Department of Physical Education and Sports Sciences", "LOW"
    else:
        return "Facilities / Maintenance", "Administration / Maintenance", "MEDIUM"


def import_42_students(db, multan_campus):
    csv_path = Path("data/students_42.csv")
    if not csv_path.exists():
        print(f"Error: {csv_path} not found!")
        return

    print("4. Importing 42 Students and Submitting Complaints (Status = PENDING)...")
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} records from CSV.")
    imported_count = 0

    for idx, r in enumerate(rows, start=1):
        name = r["Student Name"].strip()
        roll_raw = r["Roll Number"].strip()
        roll_no = roll_raw.upper()
        email = r["Email"].strip().lower().replace(",pk", ".pk")
        password = r["Initial Password"].strip()
        prog = r["Program"].strip() or "BSCS"
        title = r["Complaint Title"].strip()
        desc = r["Complaint Description"].strip()

        # Check existing user
        user = db.scalars(select(User).where(User.email == email)).first()
        if not user:
            user = db.scalars(
                select(User).join(Student, User.id == Student.user_id).where(Student.student_id == roll_no)
            ).first()

        if not user:
            user = User(
                full_name=name,
                email=email,
                password_hash=hash_password(password),
                role="STUDENT",
                campus_id=multan_campus.id,
                is_active=True,
            )
            db.add(user)
            db.flush()

            student = Student(
                user_id=user.id,
                student_id=roll_no,
                program=prog,
            )
            db.add(student)
            db.flush()
        else:
            student = user.student_profile
            if not student:
                student = Student(user_id=user.id, student_id=roll_no, program=prog)
                db.add(student)
                db.flush()

        # Update or add University Directory
        dir_entry = db.scalars(select(UniversityDirectory).where(UniversityDirectory.identifier == roll_no)).first()
        if not dir_entry:
            dir_entry = UniversityDirectory(
                role="STUDENT",
                identifier=roll_no,
                full_name=name,
                email=email,
                campus_id=multan_campus.id,
                campus="Multan Campus",
                program=prog,
                role_designation="Student",
                is_claimed=True,
            )
            db.add(dir_entry)

        # Check if complaint already exists
        existing_comp = db.scalars(
            select(Complaint).where(Complaint.user_id == user.id, Complaint.title == title)
        ).first()

        if not existing_comp:
            category, req_dept, priority = classify_complaint(title, desc)

            comp = Complaint(
                complaint_number=f"TMP-{idx:04d}",
                user_id=user.id,
                student_profile_id=student.id,
                student_id_code=roll_no,
                student_name=name,
                email=email,
                class_or_program=prog,
                account_type="STUDENT",
                originating_campus="Multan Campus",
                target_campus="Multan Campus",
                originating_campus_id=multan_campus.id,
                target_campus_id=multan_campus.id,
                title=title,
                complaint_text=desc,
                status="PENDING",  # Important Instruction 1: status show to student should be pending
                is_confidential=False,
                analysis_status="COMPLETED",
            )
            db.add(comp)
            db.flush()
            comp.complaint_number = f"CMP-2026-{comp.id:06d}"

            # Initial audit history
            hist = ComplaintStatusHistory(
                complaint_id=comp.id,
                user_id=user.id,
                action="Complaint submitted",
                new_value="PENDING",
                performed_by=name,
                timestamp=utcnow(),
            )
            db.add(hist)

            # AI / triage analysis: Contains the required department for Admin to see!
            summary_txt = f"{title}. {desc[:120]}..."
            draft_res = (
                f"Dear {name},\n\nYour grievance regarding '{title}' has been officially registered at Multan Campus. "
                f"It has been routed to the {req_dept} for evaluation and corrective action. "
                f"You will be notified once an administrative decision or officer has been assigned.\n\n"
                f"Sincerely,\nUniversity Complaint Cell, Multan Campus"
            )
            analysis = ComplaintAnalysis(
                complaint_id=comp.id,
                summary=summary_txt,
                category=category,
                category_confidence=0.95,
                priority=priority,
                priority_score=0.75 if priority == "HIGH" else 0.50,
                priority_reason=f"Categorized as {priority} priority based on issue domain.",
                assigned_department=req_dept,
                routing_reason=f"Requires intervention by {req_dept}.",
                requires_human_review=False,
                draft_response=draft_res,
                response_approved=False,
                tags=[prog, "Multan Campus", category],
                ai_model_used="claude-sonnet-5-5",
                analyzed_at=utcnow(),
            )
            db.add(analysis)

            # NOTE: We intentionally DO NOT create ComplaintAssignment yet.
            # Per Instruction 2: Only when Admin assigns the department/officer does it go to the employee!
            imported_count += 1
            print(f"[{idx}/42] Registered: {name} ({roll_no}) -> Complaint {comp.complaint_number} | Required Dept: {req_dept}")

    db.commit()
    print(f"\nSUCCESS: Successfully registered {imported_count} new student complaints (all with Status: PENDING).")


def main():
    db = SessionLocal()
    try:
        campus_objs, dept_objs = seed_campuses_and_departments(db)
        seed_admin_and_employees(db, campus_objs, dept_objs)
        import_42_students(db, campus_objs["Multan Campus"])
    finally:
        db.close()


if __name__ == "__main__":
    main()
