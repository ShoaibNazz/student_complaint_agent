# Entity Relationship Diagram (ERD)
## University Complaint Management Portal - Relational 3NF Architecture

This document provides the formal Entity Relationship Diagram (ERD) for the university complaint management portal. The schema is fully normalized up to the **Third Normal Form (3NF)**, strictly enforcing referential integrity, eliminates repeating groups, eliminates partial dependencies, and isolates role-specific attributes into discrete subtype entities.

---

### ERD Visual Diagram (Mermaid Specification)

```mermaid
erDiagram
    users {
        int id PK
        string full_name
        string email UK
        string password_hash
        string role
        string phone
        int campus_id FK
        string avatar_path
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    students {
        int id PK
        int user_id UK,FK
        string student_id UK
        string program
        string batch_year
        datetime created_at
        datetime updated_at
    }

    employees {
        int id PK
        int user_id UK,FK
        string employee_id UK
        int department_id FK
        string role_designation
        boolean is_faculty
        datetime created_at
        datetime updated_at
    }

    admins {
        int id PK
        int user_id UK,FK
        string admin_id UK
        string designation
        string permission_level
        datetime created_at
        datetime updated_at
    }

    campuses {
        int id PK
        string name UK
        string code UK
        string location
        string description
        boolean is_active
        datetime created_at
    }

    departments {
        int id PK
        string name UK
        string code UK
        string description
        boolean is_active
        datetime created_at
    }

    department_campuses {
        int department_id PK,FK
        int campus_id PK,FK
    }

    complaints {
        int id PK
        string complaint_number UK
        int user_id FK
        int student_profile_id FK
        string student_id_code
        string student_name
        string email
        string phone
        string class_or_program
        string subject
        string account_type
        int originating_campus_id FK
        int target_campus_id FK
        string originating_campus
        string target_campus
        string attachment_path
        string attachment_name
        string title
        text complaint_text
        string status
        boolean is_confidential
        string analysis_status
        boolean possible_duplicate
        int duplicate_of_id FK
        text internal_notes
        boolean is_deleted
        datetime deleted_at
        datetime created_at
        datetime updated_at
    }

    complaint_analyses {
        int id PK
        int complaint_id UK,FK
        text summary
        string category
        string subcategory
        float category_confidence
        string priority
        float priority_score
        text priority_reason
        string assigned_department
        text routing_reason
        boolean requires_human_review
        text human_review_reason
        text suggested_action
        text draft_response
        text original_draft_response
        boolean response_approved
        json tags
        string ai_model_used
        string analysis_error
        datetime analyzed_at
    }

    complaint_status_history {
        int id PK
        int complaint_id FK
        int user_id FK
        string action
        text previous_value
        text new_value
        string performed_by
        datetime timestamp
    }

    complaint_assignments {
        int id PK
        int complaint_id FK
        int department_id FK
        string department_name
        int handler_id FK
        string handler_name
        int assigned_by_id FK
        string assigned_by_name
        datetime assigned_at
        text notes
        string status
    }

    complaint_feedback {
        int id PK
        int complaint_id UK,FK
        int student_id FK
        boolean is_resolved
        int satisfaction_rating
        text feedback_remarks
        datetime confirmed_at
        string reopened_review_status
    }

    complaint_forwardings {
        int id PK
        int complaint_id FK
        int forwarded_by_id FK
        string forwarded_by_name
        string sender_authority
        string receiving_authority
        int recipient_user_id FK
        text forwarding_reason
        text admin_remarks
        string category
        string priority
        datetime forwarded_at
        string response_status
        text response_remarks
        datetime responded_at
    }

    notifications {
        int id PK
        int recipient_user_id FK
        string recipient_email
        string recipient_name
        int related_complaint_id FK
        int related_request_id FK
        string notification_type
        string subject
        text body_preview
        string delivery_status
        int attempt_count
        text error_message
        datetime sent_at
        datetime created_at
    }

    employee_requests {
        int id PK
        string request_number UK
        int user_id FK
        int employee_profile_id FK
        string employee_id_code
        string employee_name
        int department_id FK
        string department
        int campus_id FK
        string campus
        string category
        string target_authority
        string title
        text description
        string attachment_path
        string attachment_name
        string status
        string current_stage
        int reviewing_officer_id FK
        string reviewing_officer_name
        int approving_authority_id FK
        string approving_authority_name
        text decision_remarks
        datetime decided_at
        datetime created_at
        datetime updated_at
    }

    request_approvals {
        int id PK
        int request_id FK
        string stage
        string action
        int actor_id FK
        string actor_name
        text remarks
        datetime action_at
    }

    audit_logs {
        int id PK
        int user_id FK
        string user_identifier
        string action
        string target_type
        int target_id
        string campus
        string ip_address
        text details
        datetime created_at
    }

    university_directory {
        int id PK
        string role
        string identifier UK
        string full_name
        string email UK
        int department_id FK
        string department
        string program
        int campus_id FK
        string campus
        string role_designation
        boolean is_claimed
    }

    %% Relationships and Cardinalities
    users ||--o| students : "1:1 (user_id [UNIQUE])"
    users ||--o| employees : "1:1 (user_id [UNIQUE])"
    users ||--o| admins : "1:1 (user_id [UNIQUE])"
    campuses ||--o{ users : "1:M assigns campus"
    departments ||--o{ employees : "1:M employs"

    %% Many-to-Many (M:N) resolved via Associative Table
    departments ||--o{ department_campuses : "1:M provides"
    campuses ||--o{ department_campuses : "1:M hosts"

    %% Complaints Core Flow
    users ||--o{ complaints : "1:M submits"
    students ||--o{ complaints : "1:M authored by"
    campuses ||--o{ complaints : "1:M originating campus"
    campuses ||--o{ complaints : "1:M target campus"
    complaints ||--o| complaint_analyses : "1:1 (complaint_id [UNIQUE])"
    complaints ||--o{ complaint_status_history : "1:M audits"
    complaints ||--o{ complaint_assignments : "1:M routes to"
    departments ||--o{ complaint_assignments : "1:M manages"
    users ||--o{ complaint_assignments : "1:M assigned officer"
    complaints ||--o| complaint_feedback : "1:1 (complaint_id [UNIQUE])"
    users ||--o{ complaint_feedback : "1:M feedback provider"
    complaints ||--o{ complaint_forwardings : "1:M escalates"

    %% Staff Requests Flow
    users ||--o{ employee_requests : "1:M submits"
    employees ||--o{ employee_requests : "1:M requested by"
    departments ||--o{ employee_requests : "1:M department"
    campuses ||--o{ employee_requests : "1:M campus"
    employee_requests ||--o{ request_approvals : "1:M approval stages"

    %% Communications & Security
    users ||--o{ notifications : "1:M receives"
    complaints ||--o{ notifications : "1:M notifies for"
    employee_requests ||--o{ notifications : "1:M notifies for"
    users ||--o{ audit_logs : "1:M audits"
    departments ||--o{ university_directory : "1:M directory department"
    campuses ||--o{ university_directory : "1:M directory campus"
```

---

### Cardinality Summary Table

| Relationship | Cardinality | Primary Entity | Foreign Entity | Foreign Key Column | Constraint & Cascade Rule |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **User to Student** | **1:1** | `users(id)` | `students(user_id)` | `user_id` | `UNIQUE`, `ON DELETE CASCADE` |
| **User to Employee** | **1:1** | `users(id)` | `employees(user_id)` | `user_id` | `UNIQUE`, `ON DELETE CASCADE` |
| **User to Admin** | **1:1** | `users(id)` | `admins(user_id)` | `user_id` | `UNIQUE`, `ON DELETE CASCADE` |
| **Complaint to Analysis** | **1:1** | `complaints(id)` | `complaint_analyses(complaint_id)` | `complaint_id` | `UNIQUE`, `ON DELETE CASCADE` |
| **Complaint to Feedback** | **1:1** | `complaints(id)` | `complaint_feedback(complaint_id)` | `complaint_id` | `UNIQUE`, `ON DELETE CASCADE` |
| **Campus to User** | **1:M** | `campuses(id)` | `users(campus_id)` | `campus_id` | `ON DELETE SET NULL` |
| **Department to Employee** | **1:M** | `departments(id)` | `employees(department_id)` | `department_id` | `ON DELETE SET NULL` |
| **User to Complaint** | **1:M** | `users(id)` | `complaints(user_id)` | `user_id` | `ON DELETE SET NULL` |
| **Complaint to History** | **1:M** | `complaints(id)` | `complaint_status_history(complaint_id)` | `complaint_id` | `ON DELETE CASCADE` |
| **Complaint to Assignment** | **1:M** | `complaints(id)` | `complaint_assignments(complaint_id)` | `complaint_id` | `ON DELETE CASCADE` |
| **Complaint to Forwarding** | **1:M** | `complaints(id)` | `complaint_forwardings(complaint_id)` | `complaint_id` | `ON DELETE CASCADE` |
| **User to Notification** | **1:M** | `users(id)` | `notifications(recipient_user_id)` | `recipient_user_id` | `ON DELETE SET NULL` |
| **User to Employee Request** | **1:M** | `users(id)` | `employee_requests(user_id)` | `user_id` | `ON DELETE CASCADE` |
| **Request to Approval** | **1:M** | `employee_requests(id)` | `request_approvals(request_id)` | `request_id` | `ON DELETE CASCADE` |
| **Department to Campus** | **M:N** | `departments(id)` & `campuses(id)` | `department_campuses` | `(department_id, campus_id)` | Composite PK, `ON DELETE CASCADE` |
