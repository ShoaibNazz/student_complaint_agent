-- ============================================================================
-- UNIVERSITY COMPLAINT MANAGEMENT PORTAL
-- Complete Relational Database Schema (MySQL 8.0+)
-- Architecture: 3NF (Third Normal Form) Relational Database
-- Compatibility: phpMyAdmin, MySQL Workbench, MySQL CLI
-- Note: Zero dummy/sample data included. Schema structure only.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS `university_complaints`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `university_complaints`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------------------------------------------------------
-- 1. Table: campuses
-- Represents university constituent campuses.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `campuses`;
CREATE TABLE `campuses` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(120) NOT NULL,
  `code` VARCHAR(40) NULL,
  `location` VARCHAR(255) NULL,
  `description` VARCHAR(255) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `ix_campuses_name` (`name`),
  UNIQUE KEY `ix_campuses_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2. Table: departments
-- Represents academic, administrative, and support departments.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `departments`;
CREATE TABLE `departments` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(120) NOT NULL,
  `code` VARCHAR(40) NULL,
  `description` VARCHAR(255) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `ix_departments_name` (`name`),
  UNIQUE KEY `ix_departments_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 3. Table: department_campuses (M:N Associative / Junction Table)
-- Resolves Many-to-Many relationship between departments and campuses.
-- Satisfies 1NF by eliminating denormalized comma-separated strings.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `department_campuses`;
CREATE TABLE `department_campuses` (
  `department_id` INT NOT NULL,
  `campus_id` INT NOT NULL,
  PRIMARY KEY (`department_id`, `campus_id`),
  KEY `ix_department_campuses_campus_id` (`campus_id`),
  CONSTRAINT `fk_dept_camp_department` FOREIGN KEY (`department_id`)
    REFERENCES `departments` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_dept_camp_campus` FOREIGN KEY (`campus_id`)
    REFERENCES `campuses` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 4. Table: users
-- Central authentication and core profile entity for all actors.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `full_name` VARCHAR(120) NOT NULL,
  `email` VARCHAR(254) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `role` VARCHAR(20) NOT NULL DEFAULT 'STUDENT',
  `phone` VARCHAR(40) NULL,
  `campus_id` INT NULL,
  `avatar_path` VARCHAR(500) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `ix_users_email` (`email`),
  KEY `ix_users_role` (`role`),
  KEY `ix_users_campus_id` (`campus_id`),
  KEY `ix_users_created_at` (`created_at`),
  CONSTRAINT `fk_users_campus` FOREIGN KEY (`campus_id`)
    REFERENCES `campuses` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 5. Table: students (1:1 with users)
-- Normalized subtype entity storing academic attributes of students.
-- Eliminates partial dependencies and NULL pollution from base users table.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `students`;
CREATE TABLE `students` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `student_id` VARCHAR(60) NOT NULL,
  `program` VARCHAR(120) NULL,
  `batch_year` VARCHAR(20) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `ix_students_user_id` (`user_id`),
  UNIQUE KEY `ix_students_student_id` (`student_id`),
  CONSTRAINT `fk_students_user` FOREIGN KEY (`user_id`)
    REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 6. Table: employees (1:1 with users)
-- Normalized subtype entity storing employment attributes of staff & faculty.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `employees`;
CREATE TABLE `employees` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `employee_id` VARCHAR(60) NOT NULL,
  `department_id` INT NULL,
  `role_designation` VARCHAR(120) NOT NULL DEFAULT 'Employee',
  `is_faculty` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `ix_employees_user_id` (`user_id`),
  UNIQUE KEY `ix_employees_employee_id` (`employee_id`),
  KEY `ix_employees_department_id` (`department_id`),
  CONSTRAINT `fk_employees_user` FOREIGN KEY (`user_id`)
    REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_employees_department` FOREIGN KEY (`department_id`)
    REFERENCES `departments` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 7. Table: admins (1:1 with users)
-- Normalized subtype entity storing administrative privileges and designation.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `admins`;
CREATE TABLE `admins` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `admin_id` VARCHAR(60) NOT NULL,
  `designation` VARCHAR(120) NOT NULL DEFAULT 'System Administrator',
  `permission_level` VARCHAR(40) NOT NULL DEFAULT 'SUPER_ADMIN',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `ix_admins_user_id` (`user_id`),
  UNIQUE KEY `ix_admins_admin_id` (`admin_id`),
  CONSTRAINT `fk_admins_user` FOREIGN KEY (`user_id`)
    REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 8. Table: complaints
-- Primary complaint transaction record for grievance lifecycle.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `complaints`;
CREATE TABLE `complaints` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `complaint_number` VARCHAR(40) NOT NULL,
  `user_id` INT NULL,
  `student_profile_id` INT NULL,
  `student_id_code` VARCHAR(60) NULL,
  `student_name` VARCHAR(120) NOT NULL,
  `email` VARCHAR(254) NULL,
  `phone` VARCHAR(40) NULL,
  `class_or_program` VARCHAR(120) NULL,
  `subject` VARCHAR(120) NULL,
  `account_type` VARCHAR(30) NULL,
  `originating_campus_id` INT NULL,
  `target_campus_id` INT NULL,
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
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `ix_complaints_complaint_number` (`complaint_number`),
  KEY `ix_complaints_user_id` (`user_id`),
  KEY `ix_complaints_student_profile_id` (`student_profile_id`),
  KEY `ix_complaints_student_id_code` (`student_id_code`),
  KEY `ix_complaints_email` (`email`),
  KEY `ix_complaints_status` (`status`),
  KEY `ix_complaints_is_confidential` (`is_confidential`),
  KEY `ix_complaints_originating_campus_id` (`originating_campus_id`),
  KEY `ix_complaints_target_campus_id` (`target_campus_id`),
  KEY `ix_complaints_duplicate_of_id` (`duplicate_of_id`),
  KEY `ix_complaints_created_at` (`created_at`),
  CONSTRAINT `fk_complaints_user` FOREIGN KEY (`user_id`)
    REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_complaints_student_profile` FOREIGN KEY (`student_profile_id`)
    REFERENCES `students` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_complaints_orig_campus` FOREIGN KEY (`originating_campus_id`)
    REFERENCES `campuses` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_complaints_target_campus` FOREIGN KEY (`target_campus_id`)
    REFERENCES `campuses` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_complaints_duplicate_of` FOREIGN KEY (`duplicate_of_id`)
    REFERENCES `complaints` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 9. Table: complaint_analyses (1:1 with complaints)
-- AI classification, priority scoring, automated routing, and drafted responses.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `complaint_analyses`;
CREATE TABLE `complaint_analyses` (
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
  `analyzed_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `ix_complaint_analyses_complaint_id` (`complaint_id`),
  KEY `ix_complaint_analyses_category` (`category`),
  KEY `ix_complaint_analyses_priority` (`priority`),
  KEY `ix_complaint_analyses_assigned_dept` (`assigned_department`),
  KEY `ix_complaint_analyses_requires_review` (`requires_human_review`),
  CONSTRAINT `fk_analyses_complaint` FOREIGN KEY (`complaint_id`)
    REFERENCES `complaints` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 10. Table: complaint_status_history (1:M with complaints)
-- Immutable audit log of state changes throughout complaint lifecycle.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `complaint_status_history`;
CREATE TABLE `complaint_status_history` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `complaint_id` INT NOT NULL,
  `user_id` INT NULL,
  `action` VARCHAR(80) NOT NULL,
  `previous_value` TEXT NULL,
  `new_value` TEXT NULL,
  `performed_by` VARCHAR(80) NOT NULL DEFAULT 'system',
  `timestamp` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `ix_complaint_status_history_complaint_id` (`complaint_id`),
  KEY `ix_complaint_status_history_user_id` (`user_id`),
  KEY `ix_complaint_status_history_timestamp` (`timestamp`),
  CONSTRAINT `fk_history_complaint` FOREIGN KEY (`complaint_id`)
    REFERENCES `complaints` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_history_user` FOREIGN KEY (`user_id`)
    REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 11. Table: complaint_assignments (1:M with complaints)
-- Case routing assignments to responsible departments and handling officers.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `complaint_assignments`;
CREATE TABLE `complaint_assignments` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `complaint_id` INT NOT NULL,
  `department_id` INT NULL,
  `department_name` VARCHAR(120) NOT NULL,
  `handler_id` INT NULL,
  `handler_name` VARCHAR(120) NULL,
  `assigned_by_id` INT NULL,
  `assigned_by_name` VARCHAR(120) NULL,
  `assigned_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `notes` TEXT NULL,
  `status` VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  KEY `ix_complaint_assignments_complaint_id` (`complaint_id`),
  KEY `ix_complaint_assignments_department_id` (`department_id`),
  KEY `ix_complaint_assignments_handler_id` (`handler_id`),
  KEY `ix_complaint_assignments_status` (`status`),
  CONSTRAINT `fk_assignments_complaint` FOREIGN KEY (`complaint_id`)
    REFERENCES `complaints` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_assignments_department` FOREIGN KEY (`department_id`)
    REFERENCES `departments` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_assignments_handler` FOREIGN KEY (`handler_id`)
    REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_assignments_assigned_by` FOREIGN KEY (`assigned_by_id`)
    REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 12. Table: complaint_feedback (1:1 with complaints)
-- Student resolution confirmation, satisfaction rating, and dispute feedback.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `complaint_feedback`;
CREATE TABLE `complaint_feedback` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `complaint_id` INT NOT NULL,
  `student_id` INT NOT NULL,
  `is_resolved` TINYINT(1) NOT NULL DEFAULT 1,
  `satisfaction_rating` INT NULL,
  `feedback_remarks` TEXT NULL,
  `confirmed_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `reopened_review_status` VARCHAR(40) NULL,
  UNIQUE KEY `ix_complaint_feedback_complaint_id` (`complaint_id`),
  KEY `ix_complaint_feedback_student_id` (`student_id`),
  CONSTRAINT `fk_feedback_complaint` FOREIGN KEY (`complaint_id`)
    REFERENCES `complaints` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_feedback_student` FOREIGN KEY (`student_id`)
    REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 13. Table: complaint_forwardings (1:M with complaints)
-- Hierarchical escalation and forwarding records to high university authorities.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `complaint_forwardings`;
CREATE TABLE `complaint_forwardings` (
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
  `forwarded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `response_status` VARCHAR(40) NOT NULL DEFAULT 'PENDING',
  `response_remarks` TEXT NULL,
  `responded_at` DATETIME NULL,
  KEY `ix_complaint_forwardings_complaint_id` (`complaint_id`),
  KEY `ix_complaint_forwardings_forwarded_by` (`forwarded_by_id`),
  KEY `ix_complaint_forwardings_receiving_auth` (`receiving_authority`),
  KEY `ix_complaint_forwardings_recipient_user` (`recipient_user_id`),
  CONSTRAINT `fk_forwardings_complaint` FOREIGN KEY (`complaint_id`)
    REFERENCES `complaints` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_forwardings_forwarded_by` FOREIGN KEY (`forwarded_by_id`)
    REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_forwardings_recipient_user` FOREIGN KEY (`recipient_user_id`)
    REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 14. Table: notifications
-- Transactional notifications and dispatched alerts.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `notifications`;
CREATE TABLE `notifications` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `recipient_user_id` INT NULL,
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
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `ix_notifications_recipient_user_id` (`recipient_user_id`),
  KEY `ix_notifications_recipient_email` (`recipient_email`),
  KEY `ix_notifications_related_complaint_id` (`related_complaint_id`),
  KEY `ix_notifications_related_request_id` (`related_request_id`),
  KEY `ix_notifications_notification_type` (`notification_type`),
  KEY `ix_notifications_delivery_status` (`delivery_status`),
  KEY `ix_notifications_created_at` (`created_at`),
  CONSTRAINT `fk_notifications_user` FOREIGN KEY (`recipient_user_id`)
    REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_notifications_complaint` FOREIGN KEY (`related_complaint_id`)
    REFERENCES `complaints` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_notifications_request` FOREIGN KEY (`related_request_id`)
    REFERENCES `employee_requests` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 15. Table: employee_requests
-- Staff administrative applications separate from student complaints.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `employee_requests`;
CREATE TABLE `employee_requests` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `request_number` VARCHAR(40) NOT NULL,
  `user_id` INT NOT NULL,
  `employee_profile_id` INT NULL,
  `employee_id_code` VARCHAR(60) NOT NULL,
  `employee_name` VARCHAR(120) NOT NULL,
  `department_id` INT NULL,
  `department` VARCHAR(120) NULL,
  `campus_id` INT NULL,
  `campus` VARCHAR(120) NOT NULL,
  `category` VARCHAR(80) NOT NULL,
  `target_authority` VARCHAR(160) NULL,
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
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `ix_employee_requests_request_number` (`request_number`),
  KEY `ix_employee_requests_user_id` (`user_id`),
  KEY `ix_employee_requests_employee_profile_id` (`employee_profile_id`),
  KEY `ix_employee_requests_employee_id_code` (`employee_id_code`),
  KEY `ix_employee_requests_department_id` (`department_id`),
  KEY `ix_employee_requests_campus_id` (`campus_id`),
  KEY `ix_employee_requests_category` (`category`),
  KEY `ix_employee_requests_status` (`status`),
  KEY `ix_employee_requests_created_at` (`created_at`),
  CONSTRAINT `fk_requests_user` FOREIGN KEY (`user_id`)
    REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_requests_employee_profile` FOREIGN KEY (`employee_profile_id`)
    REFERENCES `employees` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_requests_department` FOREIGN KEY (`department_id`)
    REFERENCES `departments` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_requests_campus` FOREIGN KEY (`campus_id`)
    REFERENCES `campuses` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_requests_reviewing_officer` FOREIGN KEY (`reviewing_officer_id`)
    REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_requests_approving_authority` FOREIGN KEY (`approving_authority_id`)
    REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 16. Table: request_approvals (1:M with employee_requests)
-- Stage-based audit approvals for employee applications.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `request_approvals`;
CREATE TABLE `request_approvals` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `request_id` INT NOT NULL,
  `stage` VARCHAR(80) NOT NULL,
  `action` VARCHAR(40) NOT NULL,
  `actor_id` INT NULL,
  `actor_name` VARCHAR(120) NOT NULL,
  `remarks` TEXT NULL,
  `action_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `ix_request_approvals_request_id` (`request_id`),
  KEY `ix_request_approvals_actor_id` (`actor_id`),
  CONSTRAINT `fk_approvals_request` FOREIGN KEY (`request_id`)
    REFERENCES `employee_requests` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_approvals_actor` FOREIGN KEY (`actor_id`)
    REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 17. Table: audit_logs
-- Security event logging for compliance and monitoring.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `audit_logs`;
CREATE TABLE `audit_logs` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NULL,
  `user_identifier` VARCHAR(80) NOT NULL,
  `action` VARCHAR(100) NOT NULL,
  `target_type` VARCHAR(50) NOT NULL,
  `target_id` INT NOT NULL,
  `campus` VARCHAR(120) NULL,
  `ip_address` VARCHAR(60) NULL,
  `details` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `ix_audit_logs_user_id` (`user_id`),
  KEY `ix_audit_logs_action` (`action`),
  KEY `ix_audit_logs_target_type` (`target_type`),
  KEY `ix_audit_logs_target_id` (`target_id`),
  KEY `ix_audit_logs_created_at` (`created_at`),
  CONSTRAINT `fk_audit_user` FOREIGN KEY (`user_id`)
    REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 18. Table: university_directory
-- Official university roster of authorized student/employee identities.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `university_directory`;
CREATE TABLE `university_directory` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `role` VARCHAR(20) NOT NULL,
  `identifier` VARCHAR(60) NOT NULL,
  `full_name` VARCHAR(120) NOT NULL,
  `email` VARCHAR(254) NOT NULL,
  `department_id` INT NULL,
  `department` VARCHAR(120) NULL,
  `program` VARCHAR(120) NULL,
  `campus_id` INT NULL,
  `campus` VARCHAR(120) NULL,
  `role_designation` VARCHAR(120) NULL,
  `is_claimed` TINYINT(1) NOT NULL DEFAULT 0,
  UNIQUE KEY `ix_university_directory_identifier` (`identifier`),
  UNIQUE KEY `ix_university_directory_email` (`email`),
  KEY `ix_university_directory_role` (`role`),
  KEY `ix_university_directory_dept_id` (`department_id`),
  KEY `ix_university_directory_campus_id` (`campus_id`),
  CONSTRAINT `fk_directory_dept` FOREIGN KEY (`department_id`)
    REFERENCES `departments` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_directory_campus` FOREIGN KEY (`campus_id`)
    REFERENCES `campuses` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
-- ============================================================================
-- END OF SCHEMA SCRIPT
-- ============================================================================
