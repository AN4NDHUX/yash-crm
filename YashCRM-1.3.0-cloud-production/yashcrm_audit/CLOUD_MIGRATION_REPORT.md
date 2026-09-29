# Yash CRM 1.2.0 Cloud Migration Report

## Changes
- Added PostgreSQL via `psycopg` and normalization of managed `postgres://` / `postgresql://` URLs.
- Production rejects accidental SQLite use unless explicitly overridden.
- Added production connection-pool configuration and pre-ping.
- Production schema lifecycle is Alembic-first; local/desktop mode retains self-initialization.
- Production does not seed demo CRM data by default; it creates only an initial administrator record/workspace defaults.
- Added liveness `/health` and database readiness `/ready` endpoints.
- Added optional/configurable application-level HTTP Basic access protection, enabled by default in production.
- Added trusted-host validation, configurable CORS, HSTS, clickjacking/content-type/referrer/permissions headers.
- Added Python 3.12 Docker image, non-root runtime, migration-first cloud entrypoint, and PostgreSQL Docker Compose stack.
- Added `.env.example`, Render Blueprint, Railway configuration, and cloud deployment/migration/backup guidance.
- Preserved desktop launcher/installer path and existing CRM/UI/lead-conversion fixes.

## Important limitation
The CRM's existing `users` module is an ownership/role directory, not a password-based identity system. This release protects the entire cloud workspace with one gateway credential. For independent staff logins, password reset/MFA/SSO and per-user authorization, a dedicated identity layer is still required.

## External deployment
No public cloud account was accessed and no external deployment was performed. Provider-specific files are prepared for deployment but require the user's account, hostname and secrets.

## Verification performed in this environment
- Python syntax compilation: PASS (`app/main.py`, launcher, Alembic environment/migration).
- Development SQLite compatibility smoke test: PASS for `/health`, `/ready`, SPA root, dashboard, leads, deals and profile routes.
- Lead conversion regression: PASS; second conversion reused the first conversion Deal ID.
- Administrator email persistence: PASS.
- Production-mode migration test: PASS; `alembic upgrade head` created a clean schema.
- Production access-control test: PASS; unauthenticated root returned 401, authenticated root returned 200, health/readiness remained available for probes.
- Clean production bootstrap: PASS; configured `ADMIN_EMAIL` created the initial administrator without demo CRM records.
- Static execution-pattern scan: no `eval(`, `exec(`, `os.system`, `shell=True`, or subprocess execution in cloud application/migration/static paths checked.
- Docker image build: NOT RUN because Docker is not installed in this execution environment.
- Real PostgreSQL/provider deployment: NOT RUN because this environment has no provisioned external PostgreSQL/cloud account. PostgreSQL support is configured through SQLAlchemy + psycopg and deployment files, but should receive a final provider smoke test after deployment.
