# Yash CRM 2.0

Yash CRM is a browser-based FastAPI CRM with core sales, inventory, service, marketing, analytics, customization, security, automation and data-administration foundations. The production deployment is a stateless Docker web service backed by PostgreSQL.

## Included modules

- Home, Leads, Contacts, Accounts, Deals and Products
- Activities separated into Tasks, Meetings and Calls
- Price Books, Vendors, Quotes, Sales Orders, Purchase Orders and Invoices
- Campaigns, Cases, Solutions and Documents
- Forecasts, saved Reports and configurable Dashboards
- Setup for company/personal settings, users, roles, profiles, permissions, sharing rules and audit history
- Module, field, layout, pipeline, validation-rule and custom-view configuration
- Workflow, assignment, approval, blueprint, scoring, schedule and webhook configuration foundations
- Email, quote and invoice templates
- CSV import/export, duplicate detection and recycle/restore
- API client, webhook and integration metadata without storing raw secrets
- Protected AI Assistant for stuck leads, quotation follow-ups and executive sales summaries
- Optional daily sales-summary email delivery with an auditable sent/failed log

Expanded modules use a shared typed platform-record engine. Common relationships, ownership, amount, due date, status, timestamps and archival state are queryable columns; module-specific and custom values are stored as JSON. This avoids a new migration for every custom field while retaining database-enforced links to users, accounts, contacts and deals.

## Production architecture

```text
Browser -> HTTPS/Render proxy -> FastAPI/Uvicorn -> PostgreSQL
```

End users need only the HTTPS URL and the shared application credentials. They do not install Python, run PowerShell, or start a local server.

## Deploy on Render

The root `render.yaml` creates the Docker web service and PostgreSQL database. In Render, create a new Blueprint from this repository and provide the two values marked `sync: false`:

- `APP_PASSWORD`: a unique password of at least 12 characters
- `ADMIN_EMAIL`: the initial administrator's real email address

Render supplies `DATABASE_URL`, `PORT`, and the service hostname. The container applies Alembic migrations before it starts Uvicorn. See [CLOUD_DEPLOY.md](CLOUD_DEPLOY.md) for the exact deployment and verification sequence.

## Local development

Python 3.12 is the production runtime. A local SQLite database is supported only in development.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: . .venv/bin/activate
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Development mode seeds demo records by default. Do not use SQLite or demo seeding for production.

## Configuration

Copy `.env.example` only as a reference; the application does not automatically load it. Set environment variables through your shell or hosting provider.

| Variable | Production behavior |
| --- | --- |
| `APP_ENV` | Must be `production` on the hosted service. |
| `DATABASE_URL` | Required PostgreSQL URL. `postgres://` and `postgresql://` are normalized for Psycopg 3. |
| `ALLOWED_HOSTS` | Required exact host list. `*` is rejected in production. |
| `ENABLE_AUTH` | Defaults to enabled in production. |
| `APP_USERNAME` | Shared HTTP Basic username. |
| `APP_PASSWORD` | Shared secret, at least 12 characters; never commit it. |
| `ADMIN_NAME` / `ADMIN_EMAIL` | Initial CRM administrator record. The name and email remain editable in Settings. |
| `CORS_ORIGINS` | Usually empty because the UI and API are same-origin. Wildcard CORS is rejected in production. |
| `SEED_DEMO_DATA` | Keep `false` in production. |
| `SALES_SUMMARY_ENABLED` | Set `true` to run the in-process daily summary scheduler. Defaults to `false`. |
| `SALES_SUMMARY_HOUR` | Local hour from `0` to `23`; the company timezone in Settings is used. |
| `SALES_SUMMARY_RECIPIENTS` | Comma-separated recipients. Falls back to `ADMIN_EMAIL`. |
| `SMTP_HOST` / `SMTP_PORT` | SMTP endpoint used only for the daily summary. |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | Optional SMTP credentials; keep secrets in the hosting provider, never in source control. |
| `SMTP_FROM_EMAIL` | Sender address. Falls back to `SMTP_USERNAME`, then `ADMIN_EMAIL`. |
| `SMTP_USE_TLS` / `SMTP_USE_SSL` | Transport controls. STARTTLS defaults to `true`; use SSL for providers that require port 465. |

## AI Assistant and daily summary

The dedicated `/ai` module is available from the sidebar and the **Ask AI** button. It reads current protected CRM records and returns explainable, ranked actions rather than sending customer data to a third-party model. The compatibility route `/api/copilot` remains available; new clients should use `/api/ai/ask`.

The daily summary includes achieved revenue, stuck leads, quotation follow-ups, overdue activities and pending payments. Enable it only after configuring SMTP. The scheduler runs in the web process, sends once per company-local date during the configured hour and stores sent/failed delivery records in the existing Email table. Use `GET /api/ai/sales-summary` to preview and `POST /api/ai/sales-summary/send` for an authenticated manual send.

The scheduler is suitable for a single Railway/Render web replica. If you scale to multiple replicas, move this job to a singleton worker or external scheduler to avoid concurrent send attempts.

The built-in HTTP Basic gate prevents anonymous access, but it is not per-user identity or authorization. Before using the CRM for a larger team or sensitive regulated data, put it behind an OIDC/SSO access proxy and add role-based authorization.

## Health and migrations

- `GET /health` is a process liveness check and does not touch the database.
- `GET /ready` verifies database connectivity and is Render's traffic health check.
- `python -m alembic upgrade head` applies schema changes.
- `python -m alembic check` verifies that model changes have a matching migration.

## Contract validation

With the app running locally:

```bash
python scripts/check_contracts.py
```

For an authenticated deployment, also set `YASH_CRM_USERNAME` and `YASH_CRM_PASSWORD`. The checks cover health, security headers, core and expanded CRUD behavior, activity subtypes, lead-to-account/contact/deal conversion, related records, automation execution, editable administrator profile data, audit history and recycle/restore.

## Preserved product behavior

- Lead conversion creates or reuses an account and contact and creates one linked deal.
- Deal stage changes keep probability and status coherent.
- The administrator name and email are editable from Settings.
- Deletes archive normal CRM records instead of physically removing them.
- The existing responsive UI is retained; the sidebar gloss is intentionally subtle and disabled for reduced-motion users.

## Honest scope boundary

This package is a functional Yash CRM foundation, not a claim of complete feature parity with any commercial CRM. Daily sales summaries can use deployment-provided SMTP, but general template delivery, document binary storage, webhook dispatch, durable distributed scheduling, OIDC/SSO, granular per-request authorization, accounting/payment gateways and arbitrary report-query execution require deployment-specific services or further product work. Configuration records and queue/audit foundations are present so those services can be added without replacing the CRM data model. See [IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md).
