# University Complaint Portal — Table Catalog

## Summary Statistics
- **Total Tables Implemented:** **14**
- **Storage Engine:** InnoDB
- **Charset / Collation:** utf8mb4 / utf8mb4_unicode_ci
- **Foreign Key Constraints Active:** Yes (with ON DELETE CASCADE / SET NULL protections)

---

## Complete Table Inventory

| # | Table Name | Operational Purpose | Primary Key | Key Foreign Keys | Associated Workflows |
|---|---|---|---|---|---|
| 1 | `campuses` | Campus directory, campus isolation & scoping | `id` | None | Multi-campus routing & authorization |
| 2 | `departments` | Academic & administrative unit directory | `id` | None | Complaint assignment & employee requests |
| 3 | `users` | Unified authentication accounts for all roles | `id` | `campus_id -> campuses(id)` | Auth, sessions, profiles, RBAC |
| 4 | `university_directory`| Official pre-provisioned roster for identity validation | `id` | None | Registration verification |
| 5 | `complaints` | Core student complaint entity & immutable text | `id` | `user_id -> users(id)` | Student submission, tracking & review |
| 6 | `complaint_analyses` | AI triage suggestions, category, priority, draft response | `id` | `complaint_id -> complaints(id)` | Advisory classification & admin triage |
| 7 | `complaint_history` | Complete event audit log for all actions | `id` | `complaint_id -> complaints(id)` | Administrative traceability & audit |
| 8 | `complaint_assignments`| Handler & department assignment logs | `id` | `complaint_id`, `handler_id`, `department_id` | Admin routing & department handling |
| 9 | `complaint_forwardings`| Multi-tier escalation preserving original complaint ID | `id` | `complaint_id`, `forwarded_by_id` | Forwarding & higher-authority review |
| 10 | `resolution_feedback` | Student confirmation or dispute of resolved status | `id` | `complaint_id`, `student_id` | Verification & reopening workflow |
| 11 | `employee_requests` | Formal administrative applications for staff | `id` | `user_id -> users(id)` | Employee applications & review |
| 12 | `request_approvals` | Multi-stage staff request approvals trail | `id` | `request_id`, `actor_id` | Reviewing officer & approval workflow |
| 13 | `email_notifications` | Transactional email delivery and attempt tracking | `id` | `related_complaint_id`, `related_request_id` | Email delivery & notification logs |
| 14 | `audit_logs` | Security-sensitive administrative operations log | `id` | `user_id -> users(id)` | Access control, confidentiality compliance |
