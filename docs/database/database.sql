-- =============================================================================
-- University Complaint Management Portal — MySQL 8.0 DDL Schema
-- Character Set: utf8mb4, Collation: utf8mb4_unicode_ci, Engine: InnoDB
-- Total Implemented Tables: 14
-- =============================================================================

CREATE DATABASE IF NOT EXISTS `university_complaints`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `university_complaints`;

-- 1. Campuses
CREATE TABLE IF NOT EXISTS `campuses` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(120) NOT NULL,
  `code` VARCHAR(40) NULL,
  `description` VARCHAR(255) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY `uk_campuses_name` (`name`),
  UNIQUE KEY `uk_campuses_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Departments
CREATE TABLE IF NOT EXISTS `departments` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(120) NOT NULL,
  `description` VARCHAR(255) NULL,
  `campuses_served` VARCHAR(500) DEFAULT 'All Campuses',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY `uk_departments_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Users (Unified Authentication & RBAC)
CREATE TABLE IF NOT EXISTS `users` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `full_name` VARCHAR(120) NOT NULL,
  `email` VARCHAR(254) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `role` VARCHAR(20) NOT NULL DEFAULT 'STUDENT',
  `student_id` VARCHAR(60) NULL,
  `employee_id` VARCHAR(60) NULL,
  `professor_id` VARCHAR(60) NULL,
  `admin_id` VARCHAR(60) NULL,
  `department` VARCHAR(120) NULL,
  `program` VARCHAR(120) NULL,
  `campus` VARCHAR(120) NULL,
  `campus_id` INT NULL,
  `role_designation` VARCHAR(120) NULL,
  `avatar_path` VARCHAR(500) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  UNIQUE KEY `uk_users_email` (`email`),
  UNIQUE KEY `uk_users_student_id` (`student_id`),
  UNIQUE KEY `uk_users_employee_id` (`employee_id`),
  UNIQUE KEY `uk_users_professor_id` (`professor_id`),
  UNIQUE KEY `uk_users_admin_id` (`admin_id`),
  KEY `idx_users_role` (`role`),
  KEY `idx_users_campus` (`campus`),
  KEY `idx_users_campus_id` (`campus_id`),
  CONSTRAINT `fk_users_campus` FOREIGN KEY (`campus_id`) REFERENCES `campuses` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. University Official Pre-provisioned Directory Roster
CREATE TABLE IF NOT EXISTS `university_directory` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `role` VARCHAR(20) NOT NULL,
  `identifier` VARCHAR(60) NOT NULL,
  `full_name` VARCHAR(120) NOT NULL,
  `email` VARCHAR(254) NOT NULL,
  `department` VARCHAR(120) NULL,
  `program` VARCHAR(120) NULL,
  `campus` VARCHAR(120) NULL,
  `campus_id` INT NULL,
  `role_designation` VARCHAR(120) NULL,
  `is_claimed` TINYINT(1) NOT NULL DEFAULT 0,
  UNIQUE KEY `uk_dir_identifier` (`identifier`),
  UNIQUE KEY `uk_dir_email` (`email`),
  KEY `idx_dir_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Complaints
CREATE TABLE IF NOT EXISTS `complaints` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NULL,
  `complaint_number` VARCHAR(40) NOT NULL,
  `student_name` VARCHAR(120) NOT NULL,
  `student_id` VARCHAR(60) NULL,
  `email` VARCHAR(254) NULL,
  `phone` VARCHAR(40) NULL,
  `class_or_program` VARCHAR(120) NULL,
  `subject` VARCHAR(120) NULL,
  `account_type` VARCHAR(30) NULL,
  `originating_campus` VARCHAR(120) NULL,
  `target_campus` VARCHAR(120) NULL,
  `attachment_path` VARCHAR(500) NULL,
  `attachment_name` VARCHAR(255) NULL,
  `title` VARCHAR(200) NOT NULL,
  `complaint_text` TEXT NOT NULL,
  `status` VARCHAR(40) NOT NULL DEFAULT 'NEW',
  `is_confidential` TINYINT(1) NOT NULL DEFAULT 0,
  `analysis_status` VARCHAR(20) NOT NULL DEFAULT 'PENDING',
  `possible_duplicate` TINYINT(1) NOT NULL DEFAULT 0,
  `duplicate_of_id` INT NULL,
  `internal_notes` TEXT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  `deleted_at` DATETIME NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  UNIQUE KEY `uk_complaints_number` (`complaint_number`),
  KEY `idx_complaints_user_id` (`user_id`),
  KEY `idx_complaints_student_id` (`student_id`),
  KEY `idx_complaints_email` (`email`),
  KEY `idx_complaints_status` (`status`),
  KEY `idx_complaints_confidential` (`is_confidential`),
  KEY `idx_complaints_created_at` (`created_at`),
  CONSTRAINT `fk_complaints_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_complaints_duplicate` FOREIGN KEY (`duplicate_of_id`) REFERENCES `complaints` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Complaint Advisory AI Analysis
CREATE TABLE IF NOT EXISTS `complaint_analyses` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `complaint_id` INT NOT NULL,
  `summary` TEXT NOT NULL,
  `category` VARCHAR(80) NOT NULL,
  `subcategory` VARCHAR(120) NULL,
  `category_confidence` FLOAT NOT NULL DEFAULT 0.0,
  `priority` VARCHAR(10) NOT NULL,
  `priority_score` FLOAT NOT NULL DEFAULT 0.0,
  `priority_reason` TEXT NULL,
  `assigned_department` VARCHAR(120) NOT NULL,
  `routing_reason` TEXT NULL,
  `requires_human_review` TINYINT(1) NOT NULL DEFAULT 0,
  `human_review_reason` TEXT NULL,
  `suggested_action` TEXT NULL,
  `draft_response` TEXT NOT NULL,
  `original_draft_response` TEXT NULL,
  `response_approved` TINYINT(1) NOT NULL DEFAULT 0,
  `tags` JSON NULL,
  `ai_model_used` VARCHAR(120) NULL,
  `analysis_error` VARCHAR(300) NULL,
  `analyzed_at` DATETIME NOT NULL,
  UNIQUE KEY `uk_analyses_complaint_id` (`complaint_id`),
  KEY `idx_analyses_category` (`category`),
  KEY `idx_analyses_priority` (`priority`),
  KEY `idx_analyses_department` (`assigned_department`),
  CONSTRAINT `fk_analyses_complaint` FOREIGN KEY (`complaint_id`) REFERENCES `complaints` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Complaint History (Event Audit Trail)
CREATE TABLE IF NOT EXISTS `complaint_history` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `complaint_id` INT NOT NULL,
  `timestamp` DATETIME NOT NULL,
  `action` VARCHAR(80) NOT NULL,
  `previous_value` TEXT NULL,
  `new_value` TEXT NULL,
  `performed_by` VARCHAR(80) NOT NULL DEFAULT 'system',
  KEY `idx_history_complaint_id` (`complaint_id`),
  CONSTRAINT `fk_history_complaint` FOREIGN KEY (`complaint_id`) REFERENCES `complaints` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Complaint Assignments
CREATE TABLE IF NOT EXISTS `complaint_assignments` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `complaint_id` INT NOT NULL,
  `department_id` INT NULL,
  `department_name` VARCHAR(120) NOT NULL,
  `handler_id` INT NULL,
  `handler_name` VARCHAR(120) NULL,
  `assigned_by_id` INT NULL,
  `assigned_by_name` VARCHAR(120) NULL,
  `assigned_at` DATETIME NOT NULL,
  `notes` TEXT NULL,
  `status` VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  KEY `idx_assign_complaint_id` (`complaint_id`),
  KEY `idx_assign_handler_id` (`handler_id`),
  CONSTRAINT `fk_assign_complaint` FOREIGN KEY (`complaint_id`) REFERENCES `complaints` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_assign_dept` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_assign_handler` FOREIGN KEY (`handler_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_assign_by` FOREIGN KEY (`assigned_by_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. Complaint Forwardings & Escalation (Preserves Original Complaint ID)
CREATE TABLE IF NOT EXISTS `complaint_forwardings` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `complaint_id` INT NOT NULL,
  `forwarded_by_id` INT NULL,
  `forwarded_by_name` VARCHAR(120) NOT NULL,
  `sender_authority` VARCHAR(120) NOT NULL,
  `receiving_authority` VARCHAR(120) NOT NULL,
  `recipient_user_id` INT NULL,
  `forwarding_reason` TEXT NOT NULL,
  `admin_remarks` TEXT NULL,
  `category` VARCHAR(80) NOT NULL,
  `priority` VARCHAR(20) NOT NULL,
  `forwarded_at` DATETIME NOT NULL,
  `response_status` VARCHAR(40) NOT NULL DEFAULT 'PENDING',
  `response_remarks` TEXT NULL,
  `responded_at` DATETIME NULL,
  KEY `idx_fwd_complaint_id` (`complaint_id`),
  KEY `idx_fwd_receiving` (`receiving_authority`),
  CONSTRAINT `fk_fwd_complaint` FOREIGN KEY (`complaint_id`) REFERENCES `complaints` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_fwd_by` FOREIGN KEY (`forwarded_by_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_fwd_recipient` FOREIGN KEY (`recipient_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. Student Resolution Feedback
CREATE TABLE IF NOT EXISTS `resolution_feedback` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `complaint_id` INT NOT NULL,
  `student_id` INT NOT NULL,
  `is_resolved` TINYINT(1) NOT NULL DEFAULT 1,
  `satisfaction_rating` INT NULL,
  `feedback_remarks` TEXT NULL,
  `confirmed_at` DATETIME NOT NULL,
  `reopened_review_status` VARCHAR(40) NULL,
  UNIQUE KEY `uk_feedback_complaint_id` (`complaint_id`),
  KEY `idx_feedback_student_id` (`student_id`),
  CONSTRAINT `fk_feedback_complaint` FOREIGN KEY (`complaint_id`) REFERENCES `complaints` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_feedback_student` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 11. Employee Administrative Requests (Separate from Student Complaints)
CREATE TABLE IF NOT EXISTS `employee_requests` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `request_number` VARCHAR(40) NOT NULL,
  `user_id` INT NOT NULL,
  `employee_name` VARCHAR(120) NOT NULL,
  `employee_id` VARCHAR(60) NOT NULL,
  `department` VARCHAR(120) NULL,
  `campus` VARCHAR(120) NOT NULL,
  `category` VARCHAR(80) NOT NULL,
  `title` VARCHAR(200) NOT NULL,
  `description` TEXT NOT NULL,
  `attachment_path` VARCHAR(500) NULL,
  `attachment_name` VARCHAR(255) NULL,
  `status` VARCHAR(40) NOT NULL DEFAULT 'SUBMITTED',
  `current_stage` VARCHAR(80) NOT NULL DEFAULT 'Reviewing Officer',
  `reviewing_officer_id` INT NULL,
  `reviewing_officer_name` VARCHAR(120) NULL,
  `approving_authority_id` INT NULL,
  `approving_authority_name` VARCHAR(120) NULL,
  `decision_remarks` TEXT NULL,
  `decided_at` DATETIME NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  UNIQUE KEY `uk_requests_number` (`request_number`),
  KEY `idx_requests_user_id` (`user_id`),
  KEY `idx_requests_campus` (`campus`),
  KEY `idx_requests_category` (`category`),
  KEY `idx_requests_status` (`status`),
  CONSTRAINT `fk_requests_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_requests_rev_officer` FOREIGN KEY (`reviewing_officer_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_requests_appr_auth` FOREIGN KEY (`approving_authority_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 12. Request Approvals History
CREATE TABLE IF NOT EXISTS `request_approvals` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `request_id` INT NOT NULL,
  `stage` VARCHAR(80) NOT NULL,
  `action` VARCHAR(40) NOT NULL,
  `actor_id` INT NULL,
  `actor_name` VARCHAR(120) NOT NULL,
  `remarks` TEXT NULL,
  `action_at` DATETIME NOT NULL,
  KEY `idx_appr_request_id` (`request_id`),
  CONSTRAINT `fk_appr_request` FOREIGN KEY (`request_id`) REFERENCES `employee_requests` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_appr_actor` FOREIGN KEY (`actor_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 13. Email Notifications Log
CREATE TABLE IF NOT EXISTS `email_notifications` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `recipient_email` VARCHAR(254) NOT NULL,
  `recipient_name` VARCHAR(120) NOT NULL,
  `related_complaint_id` INT NULL,
  `related_request_id` INT NULL,
  `notification_type` VARCHAR(60) NOT NULL,
  `subject` VARCHAR(255) NOT NULL,
  `body_preview` TEXT NOT NULL,
  `delivery_status` VARCHAR(30) NOT NULL DEFAULT 'QUEUED',
  `attempt_count` INT NOT NULL DEFAULT 1,
  `error_message` TEXT NULL,
  `sent_at` DATETIME NULL,
  `created_at` DATETIME NOT NULL,
  KEY `idx_notif_email` (`recipient_email`),
  KEY `idx_notif_complaint` (`related_complaint_id`),
  KEY `idx_notif_request` (`related_request_id`),
  KEY `idx_notif_status` (`delivery_status`),
  CONSTRAINT `fk_notif_complaint` FOREIGN KEY (`related_complaint_id`) REFERENCES `complaints` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_notif_request` FOREIGN KEY (`related_request_id`) REFERENCES `employee_requests` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 14. Audit Logs (Security Audit Trail)
CREATE TABLE IF NOT EXISTS `audit_logs` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NULL,
  `user_identifier` VARCHAR(80) NOT NULL,
  `action` VARCHAR(100) NOT NULL,
  `target_type` VARCHAR(50) NOT NULL,
  `target_id` INT NOT NULL,
  `campus` VARCHAR(120) NULL,
  `ip_address` VARCHAR(60) NULL,
  `details` TEXT NULL,
  `created_at` DATETIME NOT NULL,
  KEY `idx_audit_user_id` (`user_id`),
  KEY `idx_audit_action` (`action`),
  KEY `idx_audit_target` (`target_type`, `target_id`),
  KEY `idx_audit_created` (`created_at`),
  CONSTRAINT `fk_audit_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
