# University Complaint Portal — Database Architecture & Design Documentation

## 1. Overview
This directory contains the complete technical design, relational schema, Entity-Relationship (ER) models, MySQL initialization scripts, realistic sample datasets, and evaluation presentation materials for the **University Complaint Management Portal**.

The system utilizes **MySQL 8.0 (InnoDB engine)** as its primary relational database, providing multi-campus data isolation, role-based workflows (Students, Employees, Professors, Administrators), AI-assisted complaint classification with administrator triage, grievance forwarding/escalation, confidential submission safeguards, verified student resolution feedback, separated administrative staff applications, and transactional audit trails.

---

## 2. Table of Contents & Documentation Index

| File | Description | Link |
|---|---|---|
| **Schema Design** | Comprehensive schema design, data types, constraints, indexes, and normalization analysis. | [`schema_design.md`](./schema_design.md) |
| **Relational Schema** | Formal relational model notation with explicit PK, FK, UK annotations and cardinalities. | [`relational_schema.md`](./relational_schema.md) |
| **Table Catalog** | Exact inventory of all 14 implemented database tables and their operational roles. | [`table_catalog.md`](./table_catalog.md) |
| **Mermaid ER Diagram** | Full Entity-Relationship diagram in valid Mermaid syntax for markdown & mermaid viewers. | [`er_diagram.mmd`](./er_diagram.mmd) |
| **Vector ER Diagram (SVG)** | Standalone, zoomable vector graphic diagram of the database architecture. | [`er_diagram.svg`](./er_diagram.svg) |
| **MySQL DDL Script** | Production-ready MySQL script creating all databases, tables, constraints, and indexes. | [`database.sql`](./database.sql) |
| **Sample Dataset** | Realistic, fictional sample data satisfying all foreign-key constraints for presentation. | [`sample_data.sql`](./sample_data.sql) |
| **Project File Structure** | Complete repository directory tree, file functions, and end-to-end execution flow. | [`file_structure.md`](./file_structure.md) |
| **Presentation & Viva Guide** | Teacher/viva presentation material, architecture walkthrough, SQL queries, and Q&A. | [`presentation_guide.md`](./presentation_guide.md) |

---

## 3. Key Architecture Metrics
- **Database Engine:** MySQL 8.0+ (InnoDB)
- **Character Set / Collation:** `utf8mb4` / `utf8mb4_unicode_ci`
- **Total Relational Tables:** **14**
- **Supported User Roles:** `STUDENT`, `EMPLOYEE`, `PROFESSOR`, `ADMIN`
- **Primary Security Guarantees:** Server-side RBAC, IDOR protection, hashed passwords (bcrypt), and confidential identity masking.
