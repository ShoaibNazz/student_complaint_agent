# University Complaint Management Portal — Presentation & Viva Guide

---

## 1. Project Introduction
The **University Complaint Management Portal** is a web-based, role-oriented governance and grievance redressal platform engineered for multi-campus public and private higher-education institutions.

It provides four dedicated user experiences:
1. **Students:** Submit academic, administrative, and sensitive grievances; track progress on visual status timelines; submit confidential reports; verify whether administrative resolutions actually solved their problem.
2. **Employees / Faculty:** Submit official administrative applications (Leave, Timetable Adjustments, Workload Concerns, Resource Requisitions); track hierarchical approval stages.
3. **Department Handlers:** Access assigned grievances relevant to their academic discipline and provide internal feedback.
4. **Campus Administrators:** Triage central complaint review queues, verify AI classification recommendations, assign department handlers, escalate complaints to central university bodies (Registrar, Controller of Examinations, Vice-Chancellor Office), and oversee campus data isolation.

---

## 2. Purpose of MySQL in the System
MySQL 8.0 acts as the central, persistent source of truth for the entire platform.
- **Relational Integrity:** Ensures that complaints are always linked to valid registered users and physical campuses.
- **Transactional Consistency:** Ensures that status transitions, handler assignments, audit logs, and notification queueing either commit completely or roll back together.
- **Security & Concurrency:** Utilizes InnoDB row-level locking, foreign key constraints, and indexing to support thousands of concurrent students during peak examination and admissions periods.

---

## 3. Why a Relational Database is Appropriate
Compared to flat-file storage or NoSQL document stores:
- **Strict Referential Integrity:** Foreign keys (`ON DELETE CASCADE` or `ON DELETE SET NULL`) eliminate dangling records or orphaned complaints when student profiles or departments change.
- **Data Normalization:** Student identity information is stored once in `users`, preventing redundant duplication across hundreds of complaint records.
- **Complex Analytical Queries:** Enables multi-table joins to generate executive dashboards, campus-by-campus resolution metrics, and department workload reports.
- **Auditability:** Immutability of original complaint statements and strict append-only history tables require relational guarantees.

---

## 4. Database Architecture Overview
The database layer is constructed with **SQLAlchemy 2.0 ORM** connected to **MySQL 8.0 (InnoDB engine)** via **PyMySQL / MySQL Connector**.
- **Character Set:** `utf8mb4` (Full multilingual and emoji/special character support).
- **Collation:** `utf8mb4_unicode_ci` (Accurate case-insensitive sorting).
- **Session Model:** Scoped request sessions with automated commit/rollback lifecycle and connection pooling (`pool_pre_ping=True`, `pool_recycle=3600`).

---

## 5. Complete List of Tables (Exact Count: 14)

The database schema consists of exactly **14 relational tables**:
1. `campuses`
2. `departments`
3. `users`
4. `university_directory`
5. `complaints`
6. `complaint_analyses`
7. `complaint_history`
8. `complaint_assignments`
9. `complaint_forwardings`
10. `resolution_feedback`
11. `employee_requests`
12. `request_approvals`
13. `email_notifications`
14. `audit_logs`

---

## 6. Detailed Explanation of Each Table

1. **`campuses`**: Stores constituent university campuses (e.g., Multan Campus, Township Campus). Used to enforce multi-campus data isolation on database queries.
2. **`departments`**: Academic and administrative units (e.g., Department of Information Sciences, Examination Department).
3. **`users`**: Unified accounts table containing authentication credentials (bcrypt hash), role (`STUDENT`, `EMPLOYEE`, `PROFESSOR`, `ADMIN`), campus link, and profile attributes.
4. **`university_directory`**: Official pre-provisioned roster from university records. Validates authentic student IDs and employee IDs during registration.
5. **`complaints`**: Core student grievance entity. Stores immutable original complaint text, status, campus references, and confidentiality flag.
6. **`complaint_analyses`**: Stores advisory AI-suggested category, subcategory, urgency priority score, confidence score, and administrative draft response.
7. **`complaint_history`**: Chronological event audit log recording every status change, department update, and timestamp.
8. **`complaint_assignments`**: Logs formal assignments of complaints to specific departments and authorized handlers.
9. **`complaint_forwardings`**: Escalation log tracking complaints routed to higher authorities (e.g., Controller of Examinations) while strictly preserving the original complaint ID.
10. **`resolution_feedback`**: Records student verification of complaint resolution (`Issue Resolved` vs. `Issue Not Resolved`), satisfaction ratings, and remarks.
11. **`employee_requests`**: Staff administrative applications (Leave, Timetable Adjustments, Workload Concerns), kept strictly separated from student complaints.
12. **`request_approvals`**: Multi-tier approval records for staff applications (Reviewing Officer, Approving Authority).
13. **`email_notifications`**: Transaction-safe log of student email notifications sent post-commit without storing plain credentials.
14. **`audit_logs`**: System security audit trail for sensitive administrative operations.

---

## 7. Primary Keys and Foreign Keys Explained
- **Primary Key (PK):** A column that uniquely identifies each row in a table. In our system, all tables utilize auto-incrementing integer primary keys (`id INT AUTO_INCREMENT`), providing fast index lookup and joins.
- **Foreign Key (FK):** A column that creates a formal link between two tables. For example:
  - `complaints.user_id -> users.id`: Guarantees a complaint belongs to an authentic registered user.
  - `complaint_analyses.complaint_id -> complaints.id`: Enforces that an AI analysis record links to an existing complaint.
  - `ON DELETE CASCADE`: Deleting a complaint automatically cleans up its dependent analyses and history.
  - `ON DELETE SET NULL`: If a handler user account is deactivated, existing assignment records retain historical traceability with `NULL` handler ID.

---

## 8. Relationship Types in the Schema
- **One-to-One (1:1):**
  - `complaints` &harr; `complaint_analyses`: Each complaint has exactly one advisory AI triage record (`complaint_id UNIQUE`).
  - `complaints` &harr; `resolution_feedback`: Each complaint has at most one student resolution confirmation record (`complaint_id UNIQUE`).
- **One-to-Many (1:N):**
  - `campuses` &rarr; `users`: One campus has many registered students, employees, and administrators.
  - `users` &rarr; `complaints`: One student can submit multiple complaints.
  - `complaints` &rarr; `complaint_history`: One complaint accumulates multiple chronological status events.
  - `complaints` &rarr; `complaint_forwardings`: One complaint can be forwarded through multiple authorities over its lifecycle.
  - `users` &rarr; `employee_requests`: One employee submits multiple administrative requests.
  - `employee_requests` &rarr; `request_approvals`: One request moves through multiple approval steps.
- **Many-to-Many (N:M):**
  - Modeled through explicit junction/history tables: `complaint_assignments` models the relationship between `complaints` and `users` (handlers) with associated assignment metadata.

---

## 9. ER Diagram Walkthrough
The Entity-Relationship diagram (visualized in `er_diagram.svg` and `er_diagram.mmd`) shows:
1. `campuses` and `departments` form the foundational organizational structure.
2. `users` branches into two parallel workflows:
   - **Student branch:** Submits `complaints` &rarr; analyzed by `complaint_analyses` &rarr; assigned via `complaint_assignments` &rarr; escalated via `complaint_forwardings` &rarr; verified by `resolution_feedback`.
   - **Staff branch:** Submits `employee_requests` &rarr; approved via `request_approvals`.
3. Cross-cutting tables (`complaint_history`, `email_notifications`, `audit_logs`) continuously monitor and record actions across both workflows.

---

## 10. Student Complaint Workflow
1. Student logs in to the Student Portal.
2. Form automatically obtains verified Student ID, Full Name, Account Role, and Registered Campus from the authenticated session (tamper-proof).
3. Student enters subject, title, and statement, with optional 500KB image attachment.
4. Optional **Confidentiality Control** enables identity protection.
5. System saves complaint with unique reference (`CMP-YYYY-XXXXXX`).
6. Advisory AI evaluates text and stores suggested category, priority score, and draft response.
7. Complaint is placed in the Central Administrator unassigned review queue.

---

## 11. Administrator Assignment Workflow
1. Campus Administrator opens their review queue (restricted to their assigned campus).
2. Admin reviews the student's original statement alongside AI recommendations.
3. AI suggestions are strictly advisory: the administrator confirms or corrects the category and priority.
4. Admin selects the responsible Department and chooses an Authorized Department Handler.
5. Admin reviews the student-facing response and clicks **Save Changes**.
6. System commits assignment, updates status to `ASSIGNED`, writes event history, and dispatches a student-facing email notification.

---

## 12. Forwarding and Escalation Workflow
When a grievance cannot be resolved locally (e.g. grade discrepancies requiring central examination ledger cross-checking):
1. Administrator clicks **Forward / Escalate Complaint**.
2. Selects an authorized higher body (e.g. Controller of Examinations, Registrar Office).
3. Enters forwarding reason and administrative remarks.
4. **Key Feature:** The system preserves the original `complaint_id` and reference number. No duplicate or confusing new IDs are generated.
5. Status changes to `IN_PROGRESS` at the higher tier, with full forwarding chain preserved in `complaint_forwardings`.
6. Confidentiality settings persist through all forwarding stages.

---

## 13. Employee Request Workflow
Staff administrative applications (Leave, Timetable Adjustments, Workload Allocations, Resource Requisitions) are kept strictly separate from student complaints:
1. Employee navigates to **My Requests &rarr; Submit Request**.
2. Selects category (e.g. Casual Leave) and enters statement with optional documentation.
3. System assigns unique request number (`REQ-YYYY-XXXXXX`).
4. Follows multi-tier approval trail (Reviewing Officer &rarr; Approving Authority).
5. Decisions (Approved/Rejected) and remarks are logged with full timestamps.

---

## 14. Student Resolution Confirmation Workflow
Unlike legacy portals where admins mark issues resolved without student consent:
1. Admin marks complaint as `Resolved — Awaiting Student Confirmation`.
2. Student receives an automated email and portal prompt.
3. Student opens complaint in My Complaints and selects:
   - **Issue Resolved:** Confirms closure, sets status to `CLOSED`, records satisfaction rating.
   - **Issue Not Resolved:** Reopens complaint (`REOPENED`), flags for admin review, and alerts administrator.
4. Prevents premature administrative closures while retaining complete audit history.

---

## 15. Authentication, Permissions, and Confidentiality
- **Authentication:** Passwords hashed with bcrypt; sessions issued via HTTP-only, SameSite JWT cookies.
- **Campus Isolation:** All database queries scope records by `admin.campus`, preventing cross-campus data leaks.
- **IDOR Protection:** Backend verifies `complaint.user_id == current_user.id` on all endpoints.
- **Confidentiality Protection:** For complaints flagged `is_confidential = 1`, personal student data (`student_name`, `email`, `student_id`, `phone`) is masked in general lists, accessible only to authorized administrative investigators.

---

## 16. Practical Example MySQL Queries

### Query 1: List complaints submitted by a particular student
```sql
SELECT c.complaint_number, c.title, c.status, c.created_at, a.category, a.priority
FROM complaints c
LEFT JOIN complaint_analyses a ON c.id = a.complaint_id
WHERE c.user_id = 3 AND c.is_deleted = 0
ORDER BY c.created_at DESC;
```

### Query 2: Display complaint details with student and department information
```sql
SELECT c.complaint_number, c.student_name, c.email, c.title, c.status,
       u.campus, a.category, a.assigned_department, ca.handler_name
FROM complaints c
JOIN users u ON c.user_id = u.id
LEFT JOIN complaint_analyses a ON c.id = a.complaint_id
LEFT JOIN complaint_assignments ca ON c.id = ca.complaint_id AND ca.status = 'ACTIVE'
WHERE c.id = 1;
```

### Query 3: List complaints awaiting administrator review in Multan Campus
```sql
SELECT c.complaint_number, c.student_name, c.title, c.created_at, a.category, a.priority
FROM complaints c
LEFT JOIN complaint_analyses a ON c.id = a.complaint_id
WHERE c.originating_campus = 'Multan Campus'
  AND c.status = 'NEW'
  AND c.is_deleted = 0
ORDER BY c.created_at ASC;
```

### Query 4: Show complete forwarding and escalation history for a complaint
```sql
SELECT f.sender_authority, f.receiving_authority, f.forwarding_reason,
       f.admin_remarks, f.forwarded_at, f.forwarded_by_name
FROM complaint_forwardings f
WHERE f.complaint_id = 2
ORDER BY f.forwarded_at ASC;
```

### Query 5: List active employees within a specific department
```sql
SELECT u.id, u.full_name, u.email, u.employee_id, u.role_designation, u.campus
FROM users u
WHERE u.department = 'Department of Information Sciences'
  AND u.is_active = 1
  AND u.role IN ('EMPLOYEE', 'PROFESSOR', 'ADMIN')
ORDER BY u.full_name ASC;
```

### Query 6: Display employee administrative requests and current approval status
```sql
SELECT r.request_number, r.employee_name, r.category, r.title, r.status,
       r.current_stage, r.reviewing_officer_name, r.created_at
FROM employee_requests r
WHERE r.campus = 'Multan Campus'
ORDER BY r.created_at DESC;
```

### Query 7: Show complaints marked resolved but awaiting student confirmation
```sql
SELECT c.complaint_number, c.student_name, c.title, c.updated_at,
       rf.is_resolved, rf.confirmed_at
FROM complaints c
LEFT JOIN resolution_feedback rf ON c.id = rf.complaint_id
WHERE c.status IN ('RESOLVED', 'RESOLVED_AWAITING_CONFIRMATION')
  AND (rf.id IS NULL OR rf.is_resolved = 0);
```

### Query 8: Aggregate complaint volume count by status, campus, or category
```sql
SELECT c.originating_campus, c.status, COUNT(c.id) AS total_complaints
FROM complaints c
WHERE c.is_deleted = 0
GROUP BY c.originating_campus, c.status
ORDER BY c.originating_campus, total_complaints DESC;
```

### Query 9: Chronological audit history of a complaint
```sql
SELECT h.timestamp, h.action, h.previous_value, h.new_value, h.performed_by
FROM complaint_history h
WHERE h.complaint_id = 1
ORDER BY h.timestamp ASC;
```

---

## 17. Database Normalization and Integrity Analysis
- **First Normal Form (1NF):** Every table attribute holds atomic scalar values. Repeating groups (such as forwarding steps, assignment history, and status changes) are decoupled into dedicated relational tables (`complaint_history`, `complaint_forwardings`, `complaint_assignments`).
- **Second Normal Form (2NF):** Every non-key attribute is fully functionally dependent on the primary key. Composite business keys are replaced with clean surrogate keys (`id INT AUTO_INCREMENT`).
- **Third Normal Form (3NF):** No transitive dependencies exist. Campus metadata and department descriptions reside in `campuses` and `departments`, preventing update anomalies when campus details change.
- **Boyce-Codd Normal Form (BCNF):** All functional determinants are candidate keys.

---

## 18. How to Setup and Run the Database Locally
1. Start MySQL 8.0 service:
   ```powershell
   Start-Service MySQL80
   ```
2. Create database and load schema:
   ```bash
   mysql -u root -p < docs/database/database.sql
   ```
3. Load demo sample data (optional):
   ```bash
   mysql -u root -p university_complaints < docs/database/sample_data.sql
   ```
4. Configure `.env`:
   ```ini
   DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/university_complaints
   ```
5. Launch the application:
   ```powershell
   python run.py
   ```

---

## 19. Possible Future Improvements
- **Automated SLA Escalation:** Cron triggers automatically escalating complaints if unassigned after 48 hours.
- **SMS / WhatsApp Gateway:** Twilio / local telecom SMS integration for students without email access.
- **Biometric Signatures:** Digital cryptographic verification for employee leave approvals.
- **Elasticsearch Integration:** Full-text search over millions of historical complaints.

---

## 20. Presentation Script & Viva Questions with Answers

### Presentation Script (2-Minute Pitch)
> "Respected examiners, our project is an enterprise-grade University Complaint and Administrative Management Portal. Unlike basic CRUD portals, our architecture addresses real institutional challenges. First, we implemented **MySQL 8.0 with InnoDB** to guarantee ACID transactions across 14 normalized tables. Second, we solved the problem of false resolutions by introducing a **Student Resolution Verification Workflow**, ensuring a complaint cannot be closed without student confirmation. Third, we separated **Staff Administrative Applications** (leave, workload, timetable) from student complaints. Fourth, we engineered an **Administrator-First Review Queue** with advisory AI classification, ensuring that AI recommendations are verified by human administrators. Finally, we implemented **Multi-Campus Data Isolation**, **Confidentiality Safeguards**, and **Escalation Trails** that preserve the original complaint ID across all stages. The platform has been verified with 134 passing automated tests."

### Top 10 Viva Questions & Answers

**Q1: Why did you transition from SQLite to MySQL?**
*Answer:* SQLite is a serverless file-based database that locks the entire file during write operations, making it unsuitable for multi-user university environments. MySQL 8.0 with InnoDB provides client-server concurrency, row-level locking, foreign key integrity, and connection pooling needed for simultaneous student and administrative access.

**Q2: What is the purpose of the 14 tables in your database?**
*Answer:* The 14 tables normalize the university domain: 4 organizational and user tables (`campuses`, `departments`, `users`, `university_directory`), 6 complaint lifecycle tables (`complaints`, `complaint_analyses`, `complaint_history`, `complaint_assignments`, `complaint_forwardings`, `resolution_feedback`), 2 employee workflow tables (`employee_requests`, `request_approvals`), and 2 enterprise tracking tables (`email_notifications`, `audit_logs`).

**Q3: Why did you combine students, employees, and admins in one `users` table?**
*Answer:* To avoid duplicating authentication mechanisms, password hashing, and session tokens. Role-specific fields are supported cleanly, and foreign keys in audit and history tables reference a single authentic user table.

**Q4: How do you prevent cross-campus data leaks?**
*Answer:* We enforce campus isolation server-side in SQLAlchemy database queries. When an administrator logs in, queries automatically filter `WHERE campus = admin.campus`. URL parameter manipulation or filter spoofing cannot bypass this server-side restriction.

**Q5: How does your AI classification work, and can it make erroneous assignments?**
*Answer:* AI classification is strictly **advisory**. When a complaint is submitted, AI suggests category, priority, and department, but the complaint always enters the central administrator's unassigned review queue. The human administrator retains sole authority to confirm or reassign.

**Q6: What happens when a complaint is escalated or forwarded? Does it get a new ID?**
*Answer:* No, the original complaint ID and reference number (`CMP-YYYY-XXXXXX`) remain strictly preserved. We insert a record into `complaint_forwardings` tracking the sending and receiving authorities and reasons without ever mutating the original ID.

**Q7: How is student privacy protected in sensitive complaints?**
*Answer:* Students can toggle **Keep My Identity Confidential**. The database records `is_confidential = 1`. In ordinary complaint listings and handler views, student identity fields are masked with `"Confidential Student"`. Only authorized administrative investigators can view the identity.

**Q8: What is the resolution confirmation workflow?**
*Answer:* An administrator marks a complaint `Resolved — Awaiting Confirmation`. The student reviews the resolution in their portal and chooses `Issue Resolved` (which closes the complaint) or `Issue Not Resolved` (which reopens the complaint as `REOPENED` for administrative reconsideration).

**Q9: Why are employee requests separated from student complaints?**
*Answer:* Employees submit administrative requests such as leave, workload changes, or equipment requisitions rather than grievances against supervisors. Keeping `employee_requests` distinct allows appropriate professional terminology and multi-tier approval workflows.

**Q10: What happens if the email server is offline when an assignment is saved?**
*Answer:* The complaint assignment transaction commits successfully first. The email notification is recorded with status `FAILED` in `email_notifications` without rolling back the saved assignment. This prevents external email outages from breaking core university records.
