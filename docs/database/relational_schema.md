# Relational Database Schema Notation

## 1. Formal Schema Representation

```text
CAMPUSES(
    id PK,
    name UK,
    code UK,
    description,
    is_active
)

DEPARTMENTS(
    id PK,
    name UK,
    description,
    campuses_served,
    is_active
)

USERS(
    id PK,
    full_name,
    email UK,
    password_hash,
    role,
    student_id UK,
    employee_id UK,
    professor_id UK,
    admin_id UK,
    department,
    program,
    campus,
    campus_id FK -> CAMPUSES(id),
    role_designation,
    avatar_path,
    is_active,
    created_at,
    updated_at
)

UNIVERSITY_DIRECTORY(
    id PK,
    role,
    identifier UK,
    full_name,
    email UK,
    department,
    program,
    campus,
    campus_id,
    role_designation,
    is_claimed
)

COMPLAINTS(
    id PK,
    user_id FK -> USERS(id),
    complaint_number UK,
    student_name,
    student_id,
    email,
    phone,
    class_or_program,
    subject,
    account_type,
    originating_campus,
    target_campus,
    attachment_path,
    attachment_name,
    title,
    complaint_text,
    status,
    is_confidential,
    analysis_status,
    possible_duplicate,
    duplicate_of_id FK -> COMPLAINTS(id),
    internal_notes,
    is_deleted,
    deleted_at,
    created_at,
    updated_at
)

COMPLAINT_ANALYSES(
    id PK,
    complaint_id FK -> COMPLAINTS(id) UK,
    summary,
    category,
    subcategory,
    category_confidence,
    priority,
    priority_score,
    priority_reason,
    assigned_department,
    routing_reason,
    requires_human_review,
    human_review_reason,
    suggested_action,
    draft_response,
    original_draft_response,
    response_approved,
    tags,
    ai_model_used,
    analysis_error,
    analyzed_at
)

COMPLAINT_HISTORY(
    id PK,
    complaint_id FK -> COMPLAINTS(id),
    timestamp,
    action,
    previous_value,
    new_value,
    performed_by
)

COMPLAINT_ASSIGNMENTS(
    id PK,
    complaint_id FK -> COMPLAINTS(id),
    department_id FK -> DEPARTMENTS(id),
    department_name,
    handler_id FK -> USERS(id),
    handler_name,
    assigned_by_id FK -> USERS(id),
    assigned_by_name,
    assigned_at,
    notes,
    status
)

COMPLAINT_FORWARDINGS(
    id PK,
    complaint_id FK -> COMPLAINTS(id),
    forwarded_by_id FK -> USERS(id),
    forwarded_by_name,
    sender_authority,
    receiving_authority,
    recipient_user_id FK -> USERS(id),
    forwarding_reason,
    admin_remarks,
    category,
    priority,
    forwarded_at,
    response_status,
    response_remarks,
    responded_at
)

RESOLUTION_FEEDBACK(
    id PK,
    complaint_id FK -> COMPLAINTS(id) UK,
    student_id FK -> USERS(id),
    is_resolved,
    satisfaction_rating,
    feedback_remarks,
    confirmed_at,
    reopened_review_status
)

EMPLOYEE_REQUESTS(
    id PK,
    request_number UK,
    user_id FK -> USERS(id),
    employee_name,
    employee_id,
    department,
    campus,
    category,
    title,
    description,
    attachment_path,
    attachment_name,
    status,
    current_stage,
    reviewing_officer_id FK -> USERS(id),
    reviewing_officer_name,
    approving_authority_id FK -> USERS(id),
    approving_authority_name,
    decision_remarks,
    decided_at,
    created_at,
    updated_at
)

REQUEST_APPROVALS(
    id PK,
    request_id FK -> EMPLOYEE_REQUESTS(id),
    stage,
    action,
    actor_id FK -> USERS(id),
    actor_name,
    remarks,
    action_at
)

EMAIL_NOTIFICATIONS(
    id PK,
    recipient_email,
    recipient_name,
    related_complaint_id FK -> COMPLAINTS(id),
    related_request_id FK -> EMPLOYEE_REQUESTS(id),
    notification_type,
    subject,
    body_preview,
    delivery_status,
    attempt_count,
    error_message,
    sent_at,
    created_at
)

AUDIT_LOGS(
    id PK,
    user_id FK -> USERS(id),
    user_identifier,
    action,
    target_type,
    target_id,
    campus,
    ip_address,
    details,
    created_at
)
```

---

## 2. Cardinality & Relationship Matrix

| Primary Entity | Foreign Entity | Cardinality | Business Meaning |
|---|---|---|---|
| `campuses` | `users` | 1 to Many (1:N) | A campus contains multiple registered users. |
| `users` | `complaints` | 1 to Many (1:N) | A student user can submit multiple complaints. |
| `complaints` | `complaint_analyses` | 1 to 1 (1:1) | Each complaint has exactly one advisory AI analysis record. |
| `complaints` | `complaint_history` | 1 to Many (1:N) | A complaint logs multiple chronological status & action events. |
| `complaints` | `complaint_assignments`| 1 to Many (1:N) | A complaint can have multiple assignment history records. |
| `complaints` | `complaint_forwardings`| 1 to Many (1:N) | A complaint can be forwarded through multiple authorities while keeping its original ID. |
| `complaints` | `resolution_feedback` | 1 to 1 (1:1) | A complaint has one student verification feedback record. |
| `users` | `employee_requests` | 1 to Many (1:N) | An employee user can submit multiple administrative requests. |
| `employee_requests` | `request_approvals` | 1 to Many (1:N) | A staff request goes through multiple approval steps. |
| `complaints` | `email_notifications` | 1 to Many (1:N) | A complaint triggers email notification records upon assignment or status changes. |
