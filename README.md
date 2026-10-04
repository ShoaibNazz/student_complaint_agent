# AI Student Complaint Agent

AI-assisted complaint triage for a school, college or university. Students submit complaints; the system **summarises, categorises, prioritises, routes to a department, flags sensitive cases for human review, and drafts a reply**. Staff review and edit everything. The AI never sends replies, closes complaints, or makes disciplinary/legal/emergency decisions.

```
Student complaint -> validate -> save original -> safety rules -> AI analysis -> validate JSON
  -> category / priority / department / human-review flag -> suggested action + draft reply
  -> store -> admin dashboard -> admin edits/approves -> workflow
```

## 1. Architecture

```
app/
  main.py            FastAPI app, middleware, error handlers
  api/               complaints.py (REST), dashboard.py (stats/config), web.py (HTML pages)
  core/              config.py (env + JSON config, logging), security.py, exceptions.py
  database/          SQLAlchemy engine/session (SQLite default, PostgreSQL-ready)
  models/            Complaint, ComplaintAnalysis, ComplaintHistory, enums
  schemas/           Pydantic request/response + AI output schema
  services/          complaint, analysis (ComplaintAnalyzer), routing, priority, category,
                     duplicate, response, history
  ai/                base.py (AIProvider), mock_provider, anthropic_provider, parser, prompts, factory
  rules/             safety_rules.py (risk signals), priority_rules.py (config-driven)
  templates/ static/ Jinja2 + Bootstrap admin UI and student form
config/              categories.json, departments.json, routing.json, priority_rules.json
tests/               pytest suite (77 tests)
sample_data/ scripts/  sample complaints + seeding script
```

**Hybrid design:** deterministic safety rules run first and can only *raise* urgency or force human review. The AI supplies contextual classification. The analyzer then validates the AI JSON (Pydantic, tolerant parsing, retries), applies the rules, routes by configuration, and replaces any unsafe draft with a neutral template.

## 2. Requirements
Python 3.11+ (tested on 3.12). No API key is needed: the default `mock` provider works offline.

## 3. Installation
```bash
python -m venv venv
```
Windows: `venv\Scripts\activate`   Linux/macOS: `source venv/bin/activate`
```bash
pip install -r requirements.txt
```

## 4. Configuration
```bash
cp .env.example .env        # Windows: copy .env.example .env
```
Key settings: `DATABASE_URL`, `AI_PROVIDER` (`mock`|`anthropic`), `ANTHROPIC_API_KEY`, `MODEL_NAME`, `LOW_CONFIDENCE_THRESHOLD` (0.60), `DUPLICATE_THRESHOLD`, `REQUIRE_STUDENT_ID`, `REQUIRE_EMAIL`, `ADMIN_USERNAME`/`ADMIN_PASSWORD`.

**Set `ADMIN_PASSWORD` before exposing the app.** If empty, admin pages and the admin API are open (development only; a warning is logged).

Institution-specific behaviour lives in `config/*.json` (restart after editing):
- `categories.json`: categories, subcategories, keywords (`word`, `stem*`, phrases), suggested actions
- `departments.json`: valid departments
- `routing.json`: category -> department mapping, plus `subcategory_overrides` such as `"Academic::Assessment Marks"`
- `priority_rules.json`: base priority per category and escalation regexes

## 5. Database
Tables are created automatically at startup. For PostgreSQL: `pip install "psycopg[binary]"` and set `DATABASE_URL=postgresql+psycopg://user:pass@host/dbname`. For schema migrations in production, add Alembic.

Optional sample data (7 example complaints): `python -m scripts.seed_sample_data`

## 6. Run
```bash
uvicorn app.main:app --reload
# or: python run.py
```
| URL | Purpose |
|---|---|
| http://127.0.0.1:8000/submit | Student complaint form |
| http://127.0.0.1:8000/admin | Admin dashboard (Basic auth when `ADMIN_PASSWORD` is set) |
| http://127.0.0.1:8000/docs | Swagger UI |
| http://127.0.0.1:8000/redoc | ReDoc |

## 7. REST API
`POST /api/complaints` is public and returns only the reference number. Everything else requires admin auth (HTTP Basic) when enabled.

| Method | Path | Description |
|---|---|---|
| POST | `/api/complaints` | Submit a complaint (runs the full pipeline) |
| GET | `/api/complaints` | List. Filters: `priority`, `category`, `department`, `status` (or `OPEN`), `requires_human_review`, `analysis_status`; search `q`; `sort`, `skip`, `limit` |
| GET | `/api/complaints/{id}` | Detail with analysis and history |
| PUT | `/api/complaints/{id}` | Update contact info / `internal_notes` (original text is immutable) |
| DELETE | `/api/complaints/{id}` | Soft delete (audit trail kept) |
| POST | `/api/complaints/{id}/analyze` | (Re)run AI analysis, e.g. after `FAILED` |
| PUT | `/api/complaints/{id}/status` | `{"status": "UNDER_REVIEW"}` |
| PUT | `/api/complaints/{id}/assignment` | `{"category","subcategory","department","priority"}` |
| PUT | `/api/complaints/{id}/response` | `{"draft_response": "...", "approved": true}` |
| GET | `/api/dashboard/stats` | Dashboard counters |
| GET | `/api/categories`, `/api/departments` | Configured lists |

Statuses: `NEW, UNDER_REVIEW, ASSIGNED, IN_PROGRESS, WAITING_FOR_STUDENT, RESOLVED, CLOSED, REJECTED`.

### Example requests
```bash
curl -X POST http://127.0.0.1:8000/api/complaints -H "Content-Type: application/json" -d '{
  "student_name": "Ali Ahmed", "student_id": "STU-1024", "email": "ali@example.edu",
  "class_or_program": "BS Computer Science",
  "complaint_title": "Assignment marks not uploaded",
  "complaint_text": "My mathematics teacher has not uploaded our assignment marks for the last three weeks."}'

curl "http://127.0.0.1:8000/api/complaints?priority=HIGH&status=OPEN&q=marks"
curl -X PUT http://127.0.0.1:8000/api/complaints/1/status -H "Content-Type: application/json" -d '{"status":"IN_PROGRESS"}'
# when auth is enabled add:  -u admin:YOUR_PASSWORD
```
On Windows `cmd`, quoting JSON is awkward. Use the Swagger UI at `/docs` or PowerShell's `Invoke-RestMethod`.

## 8. Using the MockAIProvider
`AI_PROVIDER=mock` (the default) uses a deterministic keyword classifier driven by `config/categories.json`. It returns real JSON that goes through the same parsing, validation and post-processing as a real model, so the whole app runs offline. Accuracy is limited; it exists for development, demos and tests.

## 9. Configuring Claude
```ini
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...        # keep out of version control
MODEL_NAME=claude-sonnet-5-5        # use a current model id from your Anthropic console
```
If the provider is `anthropic` but the key is empty, the app logs a warning and falls back to the mock provider. Provider errors and timeouts are retried (`AI_MAX_RETRIES`, `AI_RETRY_DELAY`). If they persist, the complaint stays saved with `analysis_status=FAILED`, rule-based triage, and a human-review flag. Use **Retry analysis** in the UI or `POST /api/complaints/{id}/analyze`.

### Adding another provider (OpenAI, Gemini, local)
Subclass `app.ai.base.AIProvider` (implement `analyze_complaint`, return the raw JSON text, raise `AIProviderError` on failure) and register it:
```python
from app.ai.factory import register_provider
register_provider("openai", lambda settings: MyOpenAIProvider(...))
```
Then set `AI_PROVIDER=openai`. Reuse `app/ai/prompts.py` for the prompts.

## 10. Tests
```bash
pytest -v
```
Covers creation, validation, classification, priority, critical detection, routing, low confidence, malformed AI JSON with retries, provider failure and retry, duplicates, database storage, XSS escaping and auth.

## 11. Safety and limitations
- AI and rules are **triage aids**. Critical or sensitive items are flagged for urgent *human* review. The system makes no emergency or disciplinary decisions and is not an emergency channel.
- Keyword rules can give false positives (for example the word "attack" in a harmless context). That is deliberate: they raise review, they never accuse.
- Duplicate detection is lexical (`difflib` plus keyword overlap). Replace `duplicate_service.similarity_fn` with an embedding-based function later.
- Built-in auth is a single shared account; add per-user roles for production. See `PRIVACY.md`.
