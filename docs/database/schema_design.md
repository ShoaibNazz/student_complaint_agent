# Complete Relational Database Schema Design

## 1. Architecture & Design Rationale

### 1.1 Why a Normalized Relational Database (MySQL 8.0 / InnoDB)?
A university complaint and administrative management system requires strict ACID compliance:
- **Atomicity:** When an administrator reassigns a grievance, the assignment record, the audit history entry, and the status update must succeed together. If any fails, all rollback safely.
- **Consistency:** Referential integrity prevents orphan complaints, broken department assignments, or unresolved escalations.
- **Isolation:** Concurrent student submissions and staff reviews must not create dirty reads or race conditions.
- **Durability:** Committed complaints and official decisions persist safely on non-volatile disk.

### 1.2 Unified User Authentication Model vs. Multi-Table Fragmentation
The architecture employs a single, consolidated `users` table rather than separate `students`, `employees`, and `admins` authentication tables.
- **Elimination of Credential Duplication:** Shared authentication infrastructure (bcrypt password hashing, JWT sessions, profile avatars, active status).
- **Smooth Role Evolution:** An employee who enrolls in a postgraduate degree or a lecturer who is elevated to campus administrator retains a unified identity record with distinct role attributes.
- **Polymorphic Foreign Keys:** Tables such as `audit_logs`, `complaint_history`, and `email_notifications` cleanly reference `users(id)` with universal referential integrity.
- **Pre-provisioned Roster Validation:** The companion `university_directory` table pre-provisions authentic university institutional IDs, preventing unauthorized public account creation.

---

## 2. Table Specifications (14 Tables)

### Table 1: `campuses`
Represents physical constituent campuses of the university. Enforces campus-level data isolation.
- `id` INT AUTO_INCREMENT PRIMARY KEY
- `name` VARCHAR(120) NOT NULL UNIQUE (e.g. "Multan Campus", "Township Campus, Lahore")
- `code` VARCHAR(40) UNIQUE (e.g. "UE-MLT", "UE-LHR-MAIN")
- `description` VARCHAR(255)
- `is_active` TINYINT(1) DEFAULT 1

### Table 2: `departments`
Academic and administrative divisions that resolve student grievances and process staff applications.
- `id` INT AUTO_INCREMENT PRIMARY KEY
- `name` VARCHAR(120) NOT NULL UNIQUE
- `description` VARCHAR(255)
- `campuses_served` VARCHAR(500) DEFAULT 'All Campuses'
- `is_active` TINYINT(1) DEFAULT 1

### Table 3: `users`
Authenticated system principals across all institutional roles.
- `id` INT AUTO_INCREMENT PRIMARY KEY
- `full_name` VARCHAR(120) NOT NULL
- `email` VARCHAR(254) NOT NULL UNIQUE (INDEX)
- `password_hash` VARCHAR(255) NOT NULL
- `role` VARCHAR(20) NOT NULL (INDEX: 'STUDENT', 'EMPLOYEE', 'PROFESSOR', 'ADMIN')
- `student_id` VARCHAR(60) UNIQUE (INDEX)
- `employee_id` VARCHAR(60) UNIQUE (INDEX)
- `professor_id` VARCHAR(60) UNIQUE (INDEX)
- `admin_id` VARCHAR(60) UNIQUE (INDEX)
- `department` VARCHAR(120)
- `program` VARCHAR(120)
- `campus` VARCHAR(120) (INDEX)
- `campus_id` INT FOREIGN KEY REFERENCES campuses(id)
- `role_designation` VARCHAR(120)
- `avatar_path` VARCHAR(500)
- `is_active` TINYINT(1) DEFAULT 1
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

### Table 4: `university_directory`
Verified institutional roster used for registration eligibility verification.
- `id` INT AUTO_INCREMENT PRIMARY KEY
- `role` VARCHAR(20) NOT NULL (INDEX)
- `identifier` VARCHAR(60) NOT NULL UNIQUE (INDEX)
- `full_name` VARCHAR(120) NOT NULL
- `email` VARCHAR(254) NOT NULL UNIQUE (INDEX)
- `department` VARCHAR(120)
- `program` VARCHAR(120)
- `campus` VARCHAR(120)
- `campus_id` INT
- `role_designation` VARCHAR(120)
- `is_claimed` TINYINT(1) DEFAULT 0

### Table 5: `complaints`
Primary student grievance records.
- `id` INT AUTO_INCREMENT PRIMARY KEY
- `user_id` INT NULLABLE FOREIGN KEY REFERENCES users(id) ON DELETE SET NULL (INDEX)
- `complaint_number` VARCHAR(40) NOT NULL UNIQUE (INDEX: e.g. CMP-2026-000001)
- `student_name` VARCHAR(120) NOT NULL
- `student_id` VARCHAR(60) (INDEX)
- `email` VARCHAR(254) (INDEX)
- `phone` VARCHAR(40)
- `class_or_program` VARCHAR(120)
- `subject` VARCHAR(120)
- `account_type` VARCHAR(30)
- `originating_campus` VARCHAR(120)
- `target_campus` VARCHAR(120)
- `attachment_path` VARCHAR(500)
- `attachment_name` VARCHAR(255)
- `title` VARCHAR(200) NOT NULL
- `complaint_text` TEXT NOT NULL (Immutable original statement)
- `status` VARCHAR(40) NOT NULL DEFAULT 'NEW' (INDEX)
- `is_confidential` TINYINT(1) NOT NULL DEFAULT 0 (INDEX: Masks personal identity from ordinary handlers)
- `analysis_status` VARCHAR(20) NOT NULL DEFAULT 'PENDING'
- `possible_duplicate` TINYINT(1) DEFAULT 0
- `duplicate_of_id` INT NULLABLE FOREIGN KEY REFERENCES complaints(id) ON DELETE SET NULL
- `internal_notes` TEXT NULLABLE
- `is_deleted` TINYINT(1) DEFAULT 0 (INDEX)
- `deleted_at` DATETIME NULLABLE
- `created_at` DATETIME NOT NULL (INDEX)
- `updated_at` DATETIME NOT NULL

### Table 6: `complaint_analyses`
Advisory AI classification, confidence score, and administrative draft responses.
- `id` INT AUTO_INCREMENT PRIMARY KEY
- `complaint_id` INT NOT NULL UNIQUE FOREIGN KEY REFERENCES complaints(id) ON DELETE CASCADE (INDEX)
- `summary` TEXT NOT NULL
- `category` VARCHAR(80) NOT NULL (INDEX)
- `subcategory` VARCHAR(120) NULLABLE
- `category_confidence` FLOAT NOT NULL DEFAULT 0.0
- `priority` VARCHAR(10) NOT NULL (INDEX: 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
- `priority_score` FLOAT NOT NULL DEFAULT 0.0
- `priority_reason` TEXT NULLABLE
- `assigned_department` VARCHAR(120) NOT NULL (INDEX)
- `routing_reason` TEXT NULLABLE
- `requires_human_review` TINYINT(1) NOT NULL DEFAULT 0 (INDEX)
- `human_review_reason` TEXT NULLABLE
- `suggested_action` TEXT NULLABLE
- `draft_response` TEXT NOT NULL
- `original_draft_response` TEXT NULLABLE
- `response_approved` TINYINT(1) NOT NULL DEFAULT 0
- `tags` JSON NULLABLE
- `ai_model_used` VARCHAR(120) NULLABLE
- `analysis_error` VARCHAR(300) NULLABLE
- `analyzed_at` DATETIME NOT NULL

### Table 7: `complaint_history`
Chronological event audit log for all complaint lifecycle actions.
- `id` INT AUTO_INCREMENT PRIMARY KEY
- `complaint_id` INT NOT NULL FOREIGN KEY REFERENCES complaints(id) ON DELETE CASCADE (INDEX)
- `timestamp` DATETIME NOT NULL
- `action` VARCHAR(80) NOT NULL
- `previous_value` TEXT NULLABLE
- `new_value` TEXT NULLABLE
- `performed_by` VARCHAR(80) NOT NULL DEFAULT 'system'

### Table 8: `complaint_assignments`
Formal department and individual handler assignment history.
- `id` INT AUTO_INCREMENT PRIMARY KEY
- `complaint_id` INT NOT NULL FOREIGN KEY REFERENCES complaints(id) ON DELETE CASCADE (INDEX)
- `department_id` INT NULLABLE FOREIGN KEY REFERENCES departments(id) ON DELETE SET NULL
- `department_name` VARCHAR(120) NOT NULL
- `handler_id` INT NULLABLE FOREIGN KEY REFERENCES users(id) ON DELETE SET NULL (INDEX)
- `handler_name` VARCHAR(120) NULLABLE
- `assigned_by_id` INT NULLABLE FOREIGN KEY REFERENCES users(id) ON DELETE SET NULL
- `assigned_by_name` VARCHAR(120) NULLABLE
- `assigned_at` DATETIME NOT NULL
- `notes` TEXT NULLABLE
- `status` VARCHAR(40) NOT NULL DEFAULT 'ACTIVE'

### Table 9: `complaint_forwardings`
Escalation trail to campus or central university offices (preserves original complaint ID).
- `id` INT AUTO_INCREMENT PRIMARY KEY
- `complaint_id` INT NOT NULL FOREIGN KEY REFERENCES complaints(id) ON DELETE CASCADE (INDEX)
- `forwarded_by_id` INT NULLABLE FOREIGN KEY REFERENCES users(id) ON DELETE SET NULL
- `forwarded_by_name` VARCHAR(120) NOT NULL
- `sender_authority` VARCHAR(120) NOT NULL
- `receiving_authority` VARCHAR(120) NOT NULL (INDEX)
- `recipient_user_id` INT NULLABLE FOREIGN KEY REFERENCES users(id) ON DELETE SET NULL
- `forwarding_reason` TEXT NOT NULL
- `admin_remarks` TEXT NULLABLE
- `category` VARCHAR(80) NOT NULL
- `priority` VARCHAR(20) NOT NULL
- `forwarded_at` DATETIME NOT NULL
- `response_status` VARCHAR(40) NOT NULL DEFAULT 'PENDING'
- `response_remarks` TEXT NULLABLE
- `responded_at` DATETIME NULLABLE

### Table 10: `resolution_feedback`
Student confirmation or dispute regarding administrative resolution.
- `id` INT AUTO_INCREMENT PRIMARY KEY
- `complaint_id` INT NOT NULL UNIQUE FOREIGN KEY REFERENCES complaints(id) ON DELETE CASCADE (INDEX)
- `student_id` INT NOT NULL FOREIGN KEY REFERENCES users(id) ON DELETE CASCADE (INDEX)
- `is_resolved` TINYINT(1) NOT NULL DEFAULT 1
- `satisfaction_rating` INT NULLABLE
- `feedback_remarks` TEXT NULLABLE
- `confirmed_at` DATETIME NOT NULL
- `reopened_review_status` VARCHAR(40) NULLABLE

### Table 11: `employee_requests`
Administrative applications submitted by university employees (completely separate from student grievances).
- `id` INT AUTO_INCREMENT PRIMARY KEY
- `request_number` VARCHAR(40) NOT NULL UNIQUE (INDEX: e.g. REQ-2026-000001)
- `user_id` INT NOT NULL FOREIGN KEY REFERENCES users(id) ON DELETE CASCADE (INDEX)
- `employee_name` VARCHAR(120) NOT NULL
- `employee_id` VARCHAR(60) NOT NULL (INDEX)
- `department` VARCHAR(120) NULLABLE
- `campus` VARCHAR(120) NOT NULL (INDEX)
- `category` VARCHAR(80) NOT NULL (INDEX: 'Leave Application', 'Workload Change', 'Timetable Adjustment', etc.)
- `title` VARCHAR(200) NOT NULL
- `description` TEXT NOT NULL
- `attachment_path` VARCHAR(500) NULLABLE
- `attachment_name` VARCHAR(255) NULLABLE
- `status` VARCHAR(40) NOT NULL DEFAULT 'SUBMITTED' (INDEX)
- `current_stage` VARCHAR(80) NOT NULL DEFAULT 'Reviewing Officer'
- `reviewing_officer_id` INT NULLABLE FOREIGN KEY REFERENCES users(id) ON DELETE SET NULL
- `reviewing_officer_name` VARCHAR(120) NULLABLE
- `approving_authority_id` INT NULLABLE FOREIGN KEY REFERENCES users(id) ON DELETE SET NULL
- `approving_authority_name` VARCHAR(120) NULLABLE
- `decision_remarks` TEXT NULLABLE
- `decided_at` DATETIME NULLABLE
- `created_at` DATETIME NOT NULL (INDEX)
- `updated_at` DATETIME NOT NULL

### Table 12: `request_approvals`
Audit trail of approval steps for staff applications.
- `id` INT AUTO_INCREMENT PRIMARY KEY
- `request_id` INT NOT NULL FOREIGN KEY REFERENCES employee_requests(id) ON DELETE CASCADE (INDEX)
- `stage` VARCHAR(80) NOT NULL
- `action` VARCHAR(40) NOT NULL
- `actor_id` INT NULLABLE FOREIGN KEY REFERENCES users(id) ON DELETE SET NULL
- `actor_name` VARCHAR(120) NOT NULL
- `remarks` TEXT NULLABLE
- `action_at` DATETIME NOT NULL

### Table 13: `email_notifications`
Transactional email logs recorded post-commit without storing plain credentials.
- `id` INT AUTO_INCREMENT PRIMARY KEY
- `recipient_email` VARCHAR(254) NOT NULL (INDEX)
- `recipient_name` VARCHAR(120) NOT NULL
- `related_complaint_id` INT NULLABLE FOREIGN KEY REFERENCES complaints(id) ON DELETE SET NULL (INDEX)
- `related_request_id` INT NULLABLE FOREIGN KEY REFERENCES employee_requests(id) ON DELETE SET NULL (INDEX)
- `notification_type` VARCHAR(60) NOT NULL (INDEX)
- `subject` VARCHAR(255) NOT NULL
- `body_preview` TEXT NOT NULL
- `delivery_status` VARCHAR(30) NOT NULL DEFAULT 'QUEUED' (INDEX)
- `attempt_count` INT NOT NULL DEFAULT 1
- `error_message` TEXT NULLABLE
- `sent_at` DATETIME NULLABLE
- `created_at` DATETIME NOT NULL

### Table 14: `audit_logs`
Security-sensitive administrative event log without disclosing confidential identities.
- `id` INT AUTO_INCREMENT PRIMARY KEY
- `user_id` INT NULLABLE FOREIGN KEY REFERENCES users(id) ON DELETE SET NULL (INDEX)
- `user_identifier` VARCHAR(80) NOT NULL
- `action` VARCHAR(100) NOT NULL (INDEX)
- `target_type` VARCHAR(50) NOT NULL (INDEX)
- `target_id` INT NOT NULL (INDEX)
- `campus` VARCHAR(120) NULLABLE
- `ip_address` VARCHAR(60) NULLABLE
- `details` TEXT NULLABLE
- `created_at` DATETIME NOT NULL (INDEX)
