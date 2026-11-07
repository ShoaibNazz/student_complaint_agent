-- =============================================================================
-- Fictional Demonstration Dataset for University Complaint Management Portal
-- Safe for Academic Presentation & Viva Evaluation (Zero Real Personal Data)
-- =============================================================================

USE `university_complaints`;

-- 1. Campuses
INSERT INTO `campuses` (`id`, `name`, `code`, `description`, `is_active`) VALUES
(1, 'Township Campus, Lahore (Main Campus)', 'UE-LHR-MAIN', 'Central Administrative & Academic Headquarters', 1),
(2, 'Lower Mall Campus, Lahore', 'UE-LHR-LM', 'Historic Lower Mall Constituent Campus', 1),
(3, 'Bank Road Campus, Lahore', 'UE-LHR-BR', 'Bank Road Campus for Women, Lahore', 1),
(4, 'Multan Campus', 'UE-MLT', 'Multan Constituent Campus, Bosan Road', 1),
(5, 'Faisalabad Campus', 'UE-FSD', 'Faisalabad Constituent Campus, Samanabad', 1);

-- 2. Departments
INSERT INTO `departments` (`id`, `name`, `description`, `campuses_served`, `is_active`) VALUES
(1, 'Department of Information Sciences', 'Computer Science, IT and Software Engineering degrees', 'All Campuses', 1),
(2, 'Department of Mathematics', 'Pure and Applied Mathematics Programs', 'All Campuses', 1),
(3, 'Examination Department', 'Controller of Examinations, grading, transcripts', 'All Campuses', 1),
(4, 'IT Department', 'Campus Network, LMS, and Student Portal Services', 'All Campuses', 1),
(5, 'Directorate of Student Affairs', 'Student Welfare, hostel allotment, discipline inquiries', 'All Campuses', 1);

-- 3. Users (Hashed password for all demo accounts: 'DemoPass123!')
-- Hash: $2b$12$KIXpZ0k7E6lS3qU6g2yR..VzEfZjP7y4x0JvA9BqjZpM3sQ9Z4n4e (fictional bcrypt placeholder)
INSERT INTO `users` (`id`, `full_name`, `email`, `password_hash`, `role`, `student_id`, `employee_id`, `professor_id`, `admin_id`, `department`, `program`, `campus`, `campus_id`, `role_designation`, `is_active`, `created_at`, `updated_at`) VALUES
(1, 'Dr. Muhammad Imran', 'admin.multan@ue.edu.pk', '$2b$12$1234567890123456789012345678901234567890123456789012', 'ADMIN', NULL, NULL, NULL, 'ADM-MLT-001', 'Campus Administration', NULL, 'Multan Campus', 4, 'Campus Administrator', 1, '2026-09-01 08:00:00', '2026-09-01 08:00:00'),
(2, 'Dr. Irtaza Sheikh', 'irtaza.sheikh@ue.edu.pk', '$2b$12$1234567890123456789012345678901234567890123456789012', 'EMPLOYEE', NULL, 'EMP-MLT-102', NULL, NULL, 'Department of Information Sciences', NULL, 'Multan Campus', 4, 'Assistant Professor', 1, '2026-09-05 09:30:00', '2026-09-05 09:30:00'),
(3, 'Muhammad Shoaib', 'shoaib.student@ue.edu.pk', '$2b$12$1234567890123456789012345678901234567890123456789012', 'STUDENT', 'STU-MLT-2024-0012', NULL, NULL, NULL, 'Department of Information Sciences', 'BS Computer Science', 'Multan Campus', 4, NULL, 1, '2026-09-10 10:15:00', '2026-09-10 10:15:00'),
(4, 'Fatima Noor', 'fatima.noor@ue.edu.pk', '$2b$12$1234567890123456789012345678901234567890123456789012', 'STUDENT', 'STU-MLT-2024-0045', NULL, NULL, NULL, 'Department of Mathematics', 'BS Mathematics', 'Multan Campus', 4, NULL, 1, '2026-09-12 11:00:00', '2026-09-12 11:00:00');

-- 4. University Pre-provisioned Directory Roster
INSERT INTO `university_directory` (`id`, `role`, `identifier`, `full_name`, `email`, `department`, `program`, `campus`, `campus_id`, `role_designation`, `is_claimed`) VALUES
(1, 'ADMIN', 'ADM-MLT-001', 'Dr. Muhammad Imran', 'admin.multan@ue.edu.pk', 'Campus Administration', NULL, 'Multan Campus', 4, 'Campus Administrator', 1),
(2, 'EMPLOYEE', 'EMP-MLT-102', 'Dr. Irtaza Sheikh', 'irtaza.sheikh@ue.edu.pk', 'Department of Information Sciences', NULL, 'Multan Campus', 4, 'Assistant Professor', 1),
(3, 'STUDENT', 'STU-MLT-2024-0012', 'Muhammad Shoaib', 'shoaib.student@ue.edu.pk', 'Department of Information Sciences', 'BS Computer Science', 'Multan Campus', 4, NULL, 1),
(4, 'STUDENT', 'STU-MLT-2024-0045', 'Fatima Noor', 'fatima.noor@ue.edu.pk', 'Department of Mathematics', 'BS Mathematics', 'Multan Campus', 4, NULL, 1);

-- 5. Complaints
INSERT INTO `complaints` (`id`, `user_id`, `complaint_number`, `student_name`, `student_id`, `email`, `phone`, `class_or_program`, `subject`, `account_type`, `originating_campus`, `target_campus`, `attachment_path`, `attachment_name`, `title`, `complaint_text`, `status`, `is_confidential`, `analysis_status`, `possible_duplicate`, `duplicate_of_id`, `internal_notes`, `is_deleted`, `created_at`, `updated_at`) VALUES
(1, 3, 'CMP-2026-000001', 'Muhammad Shoaib', 'STU-MLT-2024-0012', 'shoaib.student@ue.edu.pk', '03001234567', 'BS Computer Science', 'Attendance / CS-301', 'STUDENT', 'Multan Campus', 'Multan Campus', NULL, NULL, 'Course Attendance is not updated on student portal', 'I attended all classes of Web Technologies CS-301, but the portal still displays 70% attendance instead of 95%. Please reconcile with instructor attendance register.', 'ASSIGNED', 0, 'COMPLETED', 0, NULL, 'Referred to Information Sciences HOD for register verification.', 0, '2026-10-15 09:30:00', '2026-10-15 10:00:00'),
(2, 4, 'CMP-2026-000002', 'Fatima Noor', 'STU-MLT-2024-0045', 'fatima.noor@ue.edu.pk', '03019876543', 'BS Mathematics', 'Calculus-II Result', 'STUDENT', 'Multan Campus', 'Multan Campus', NULL, NULL, 'Result marksheet mismatch for Calculus II', 'My transcript displays a grade of D in Calculus II whereas my mid and final papers were scored above 78%.', 'IN_PROGRESS', 0, 'COMPLETED', 0, NULL, 'Forwarded to Controller of Examinations for ledger verification.', 0, '2026-10-18 11:20:00', '2026-10-18 12:15:00'),
(3, 3, 'CMP-2026-000003', 'Confidential Student', 'RESTRICTED', 'confidential@portal.internal', 'RESTRICTED', 'BS Computer Science', 'Faculty Conduct', 'STUDENT', 'Multan Campus', 'Multan Campus', NULL, NULL, 'Unfair lab viva evaluation and intimidating behavior', 'Student reported biased grading during the lab examination and verbal intimidation. Submitted under strict confidentiality.', 'UNDER_REVIEW', 1, 'COMPLETED', 0, NULL, 'Handled under institutional safeguarding guidelines. Identity protected.', 0, '2026-10-20 14:00:00', '2026-10-20 14:05:00');

-- 6. AI Analysis
INSERT INTO `complaint_analyses` (`id`, `complaint_id`, `summary`, `category`, `subcategory`, `category_confidence`, `priority`, `priority_score`, `priority_reason`, `assigned_department`, `routing_reason`, `requires_human_review`, `human_review_reason`, `suggested_action`, `draft_response`, `original_draft_response`, `response_approved`, `tags`, `ai_model_used`, `analyzed_at`) VALUES
(1, 1, 'Student reports discrepancy between physical attendance and portal display for CS-301.', 'Attendance', 'Incorrect Record', 0.94, 'MEDIUM', 2.0, 'Attendance shortage affects final exam roll slip generation.', 'Department of Information Sciences', 'Department holds course attendance registers.', 0, NULL, 'Reconcile physical attendance sheet with portal record.', 'Dear Student, your attendance reconciliation request has been sent to your department coordinator.', 'Dear Student, your attendance record is being reviewed.', 1, '["attendance", "cs-301", "portal"]', 'claude-sonnet-5-5', '2026-10-15 09:30:05'),
(2, 2, 'Transcript marksheet discrepancy in Calculus-II.', 'Results / Marks', 'Incorrect Marks', 0.96, 'HIGH', 3.0, 'Disputed grade affects semester GPA and scholarship eligibility.', 'Examination Department', 'Controller of Examinations handles grade ledger disputes.', 0, NULL, 'Cross-check paper award lists against central examination ledger.', 'Dear Student, your grade dispute has been escalated to the examination office.', 'Result review initiated.', 1, '["grades", "calculus", "result"]', 'claude-sonnet-5-5', '2026-10-18 11:20:06'),
(3, 3, 'Sensitive report alleging unfair evaluation and faculty intimidation.', 'Harassment / Bullying', 'Verbal / Inappropriate Conduct', 0.92, 'CRITICAL', 4.0, 'Sensitive allegation involving student safety and fairness.', 'Directorate of Student Affairs', 'Designated Safeguarding Officer review required.', 1, 'Sensitive faculty grievance requiring confidential inquiry.', 'Refer confidentially to the Designated Safeguarding Officer.', 'Dear Student, your confidential inquiry has been logged for inquiry by authorized personnel.', 'Confidential receipt acknowledged.', 1, '["confidential", "safeguarding", "conduct"]', 'claude-sonnet-5-5', '2026-10-20 14:00:08');

-- 7. Complaint History
INSERT INTO `complaint_history` (`id`, `complaint_id`, `timestamp`, `action`, `previous_value`, `new_value`, `performed_by`) VALUES
(1, 1, '2026-10-15 09:30:00', 'Complaint created', NULL, 'CMP-2026-000001', 'student'),
(2, 1, '2026-10-15 10:00:00', 'Department assigned', 'Under Review', 'Department of Information Sciences', 'Dr. Muhammad Imran'),
(3, 2, '2026-10-18 11:20:00', 'Complaint created', NULL, 'CMP-2026-000002', 'student'),
(4, 2, '2026-10-18 12:15:00', 'Complaint forwarded to Controller of Examinations', 'Multan Campus Administration', 'Controller of Examinations', 'Dr. Muhammad Imran'),
(5, 3, '2026-10-20 14:00:00', 'Confidential complaint created', NULL, 'CMP-2026-000003', 'student');

-- 8. Assignments
INSERT INTO `complaint_assignments` (`id`, `complaint_id`, `department_id`, `department_name`, `handler_id`, `handler_name`, `assigned_by_id`, `assigned_by_name`, `assigned_at`, `notes`, `status`) VALUES
(1, 1, 1, 'Department of Information Sciences', 2, 'Dr. Irtaza Sheikh', 1, 'Dr. Muhammad Imran', '2026-10-15 10:00:00', 'Please verify against course attendance register.', 'ACTIVE');

-- 9. Forwardings
INSERT INTO `complaint_forwardings` (`id`, `complaint_id`, `forwarded_by_id`, `forwarded_by_name`, `sender_authority`, `receiving_authority`, `recipient_user_id`, `forwarding_reason`, `admin_remarks`, `category`, `priority`, `forwarded_at`, `response_status`) VALUES
(1, 2, 1, 'Dr. Muhammad Imran', 'Multan Campus Administration', 'Controller of Examinations', NULL, 'Result marksheet requires central ledger cross-verification.', 'Instructor score sheet attached for comparison.', 'Results / Marks', 'HIGH', '2026-10-18 12:15:00', 'PENDING');

-- 10. Student Resolution Feedback
INSERT INTO `resolution_feedback` (`id`, `complaint_id`, `student_id`, `is_resolved`, `satisfaction_rating`, `feedback_remarks`, `confirmed_at`) VALUES
(1, 1, 3, 1, 5, 'My attendance register was checked and updated on the student portal. Thank you.', '2026-10-16 14:30:00');

-- 11. Employee Administrative Requests
INSERT INTO `employee_requests` (`id`, `request_number`, `user_id`, `employee_name`, `employee_id`, `department`, `campus`, `category`, `title`, `description`, `status`, `current_stage`, `reviewing_officer_id`, `reviewing_officer_name`, `approving_authority_id`, `approving_authority_name`, `decision_remarks`, `decided_at`, `created_at`, `updated_at`) VALUES
(1, 'REQ-2026-000001', 2, 'Dr. Irtaza Sheikh', 'EMP-MLT-102', 'Department of Information Sciences', 'Multan Campus', 'Leave Application', 'Casual Leave for Research Symposium Attendance', 'Requesting 2 days casual duty leave (24-25 October) to present research findings at National Computing Symposium.', 'APPROVED', 'Completed', 1, 'Dr. Muhammad Imran', 1, 'Dr. Muhammad Imran', 'Approved with recommendation. Classes rescheduled on timetable.', '2026-10-22 11:00:00', '2026-10-21 09:00:00', '2026-10-22 11:00:00');

-- 12. Request Approvals
INSERT INTO `request_approvals` (`id`, `request_id`, `stage`, `action`, `actor_id`, `actor_name`, `remarks`, `action_at`) VALUES
(1, 1, 'Submission', 'SUBMITTED', 2, 'Dr. Irtaza Sheikh', 'Application submitted through Employee Portal.', '2026-10-21 09:00:00'),
(2, 1, 'Reviewing Officer', 'REVIEWED', 1, 'Dr. Muhammad Imran', 'Verified timetable coverage.', '2026-10-21 15:30:00'),
(3, 1, 'Completed', 'APPROVED', 1, 'Dr. Muhammad Imran', 'Approved with duty allowance.', '2026-10-22 11:00:00');

-- 13. Email Notifications
INSERT INTO `email_notifications` (`id`, `recipient_email`, `recipient_name`, `related_complaint_id`, `related_request_id`, `notification_type`, `subject`, `body_preview`, `delivery_status`, `attempt_count`, `sent_at`, `created_at`) VALUES
(1, 'shoaib.student@ue.edu.pk', 'Muhammad Shoaib', 1, NULL, 'COMPLAINT_ASSIGNED', '[University Portal] Update on Complaint CMP-2026-000001', 'Dear Muhammad Shoaib, Your complaint has been assigned to Department of Information Sciences for review.', 'SENT', 1, '2026-10-15 10:00:02', '2026-10-15 10:00:01'),
(2, 'fatima.noor@ue.edu.pk', 'Fatima Noor', 2, NULL, 'COMPLAINT_FORWARDED', '[University Portal] Escalation Update on Complaint CMP-2026-000002', 'Dear Fatima Noor, Your grade discrepancy complaint has been forwarded to Controller of Examinations.', 'SENT', 1, '2026-10-18 12:15:02', '2026-10-18 12:15:01');

-- 14. Audit Logs
INSERT INTO `audit_logs` (`id`, `user_id`, `user_identifier`, `action`, `target_type`, `target_id`, `campus`, `ip_address`, `details`, `created_at`) VALUES
(1, 1, 'ADM-MLT-001', 'ASSIGN_COMPLAINT', 'COMPLAINT', 1, 'Multan Campus', '127.0.0.1', 'Assigned complaint CMP-2026-000001 to handler Dr. Irtaza Sheikh.', '2026-10-15 10:00:00'),
(2, 1, 'ADM-MLT-001', 'FORWARD_COMPLAINT', 'COMPLAINT', 2, 'Multan Campus', '127.0.0.1', 'Forwarded CMP-2026-000002 to Controller of Examinations.', '2026-10-18 12:15:00'),
(3, 1, 'ADM-MLT-001', 'APPROVE_REQUEST', 'EMPLOYEE_REQUEST', 1, 'Multan Campus', '127.0.0.1', 'Approved leave application REQ-2026-000001.', '2026-10-22 11:00:00');
