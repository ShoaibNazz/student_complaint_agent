# Privacy & AI Considerations

This system uses AI to **assist** staff. It does not make final decisions.

## What is sent to the AI provider
- Only the complaint **title, description, subject and class/program**, plus short non-identifying safety-signal labels.
- **Never sent:** student name, student ID, email, phone, passwords, API keys, or internal notes.
- The student's first name is inserted into the draft greeting *locally*, after the AI responds.
- With `AI_PROVIDER=mock` (the default) nothing leaves your server.
- If you use a hosted provider, review its data-retention terms and your obligations (GDPR, FERPA, local law). Students may write personal details in free text, so cover this in your privacy notice.

## Human oversight
- AI output is a **suggestion**. Replies are **never sent automatically**; administrators edit and approve them.
- AI never closes or resolves a complaint and never makes disciplinary, legal, or emergency decisions.
- Deterministic safety rules flag suicide/self-harm, violence, weapons, abuse, harassment, discrimination, fire/danger, etc. They force `requires_human_review` and can only **raise** priority, never lower it.
- Classifications below `LOW_CONFIDENCE_THRESHOLD` are flagged for manual review.
- If the AI fails, the complaint stays saved, is triaged by rules only, flagged for manual review, and can be re-analysed.
- Prompts require neutral wording ("The student reports...") and forbid determining guilt. Drafts containing liability admissions, blame, or promises are replaced with a safe template.

## Data handling
- The original complaint text is stored unchanged; AI text is stored separately, and the AI's original draft is kept beside the edited one.
- Every change is recorded in `complaint_history`. Deletion is a *soft delete* so the audit trail remains.
- Logs contain reference numbers and categories, **not** complaint text, names, emails, or API keys.
- User content is HTML-escaped on output (Jinja2 autoescape); all queries go through the ORM. A Content-Security-Policy and other security headers are set.
- Student-facing pages show only the reference number, never the AI analysis.

## Operational recommendations
- Set `ADMIN_PASSWORD` and serve over **HTTPS** behind a reverse proxy. An empty password disables auth (local development only).
- Built-in auth is one shared account. For production add per-user accounts and roles (hook: `app/core/security.py::require_role`) so sensitive complaints can be limited to designated officers.
- Encrypt backups, define a retention period, and have a process for access/erasure requests.
- This tool is not monitored in real time and is **not** an emergency channel.
