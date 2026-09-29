# Yash CRM

Yash CRM is a browser-based FastAPI CRM for leads, contacts, accounts, deals, products, activities, settings, approvals, and blueprints. The production deployment is a stateless Docker web service backed by PostgreSQL.

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

For an authenticated deployment, also set `YASH_CRM_USERNAME` and `YASH_CRM_PASSWORD`. The checks cover health, security headers, CRUD behavior, lead-to-account/contact/deal conversion, and editable administrator profile data.

## Preserved product behavior

- Lead conversion creates or reuses an account and contact and creates one linked deal.
- Deal stage changes keep probability and status coherent.
- The administrator name and email are editable from Settings.
- Deletes archive normal CRM records instead of physically removing them.
- The existing responsive UI is retained; the sidebar gloss is intentionally subtle and disabled for reduced-motion users.
