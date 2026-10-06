# Deploy Yash CRM on Railway

Yash CRM is deployed as a Dockerized FastAPI service backed by PostgreSQL. The browser uses database-backed user sessions; production HTTP Basic authentication is disabled.

## 1. Railway services

Create or keep these Railway services in the same project:

1. **yashcrm** — GitHub-connected service from `AN4NDHUX/yash-crm`, branch `main`.
2. **PostgreSQL** — Railway PostgreSQL service.

The web service uses the root `Dockerfile` and `railway.toml`. On every deploy, `cloud-entrypoint.sh` runs:

```text
alembic upgrade head
uvicorn app.main:app
```

The deploy must fail rather than start the application if a migration fails.

## 2. Required production variables

Configure these on the `yashcrm` Railway service:

```text
APP_ENV=production
ENABLE_AUTH=true
DATABASE_URL=<Railway PostgreSQL connection string>
ALLOWED_HOSTS=yashcrm-production.up.railway.app
APP_PUBLIC_URL=https://yashcrm-production.up.railway.app
APP_USERNAME=admin
APP_PASSWORD=<unique random password, 12+ characters>
ADMIN_NAME=Administrator
ADMIN_EMAIL=<real owner email>
SEED_DEMO_DATA=false
```

Do not commit secrets. Rotate any secret that has appeared in screenshots, logs, chat messages, tickets, or source control.

### Owner MFA

Administrator TOTP MFA is supported. Provision a Base32 secret in your authenticator workflow and set:

```text
YASHCRM_ADMIN_TOTP_SECRET=<base32 secret>
```

When this variable is set, Administrator login requires the current 6-digit authenticator code. Normal user accounts are not forced through the owner MFA secret.

### Proxy trust

The entrypoint no longer trusts arbitrary `X-Forwarded-*` headers. It defaults to:

```text
FORWARDED_ALLOW_IPS=127.0.0.1
```

Only change this to Railway's actual trusted proxy range if required. Do not use `*` unless the service is otherwise network-isolated and the risk is explicitly accepted.

## 3. Security model

Production browser authentication is:

```text
username / email / phone + password
            ↓
database-backed account
            ↓
HttpOnly + Secure session cookie
            ↓
tenant-scoped CRM access
```

Additional controls include:

- 12-character minimum for newly created/reset passwords.
- Login, signup and reset throttling.
- Same-origin protection on cookie-authenticated state-changing requests.
- Administrator-only user administration and security overview.
- Owner MFA when `YASHCRM_ADMIN_TOTP_SECRET` is configured.
- CSP, HSTS, frame denial, MIME-sniffing protection and restricted browser permissions.
- Password-reset session revocation.
- Owner controls to suspend accounts, revoke sessions, trigger password resets and export account data.
- Tenant-authorized document downloads.
- Document content stored durably in PostgreSQL instead of relying on Railway's ephemeral filesystem.
- Subscription record, storage, custom-module and AI feature limits.

Development-only Basic authentication remains available to existing automated tests and local compatibility tooling. It is not accepted as the production authentication path.

## 4. Verify a deployment

Wait until Railway shows the service as healthy. Then verify:

1. `GET /health` returns HTTP 200.
2. `GET /ready` returns HTTP 200 and reports the database ready.
3. `/login` loads without authentication.
4. Owner login succeeds using the configured Administrator account.
5. `/owner` loads only for the Administrator.
6. Create a disposable non-admin account and confirm it cannot access `/api/users`, `/api/security/overview` or `/owner`.
7. Create a lead, contact, account and deal and confirm a second account cannot see them.
8. Upload a disposable document and confirm another account receives 404 from the document download endpoint.
9. Confirm logout invalidates the session.
10. Confirm password reset invalidates existing sessions.

## 5. CI gates

Every push and pull request to `main` now validates:

- Python compilation.
- JavaScript syntax.
- Full pytest regression suite.
- Real Chromium signup/login/navigation smoke flow with Playwright.
- `pip-audit` against production dependencies.
- high-severity Bandit findings.
- a clean PostgreSQL `alembic upgrade head`.

A green SQLite-only test run is not sufficient for release. PostgreSQL migration verification is required because production uses PostgreSQL.

## 6. Database operations

Before a risky production migration:

1. Verify Railway PostgreSQL backups are enabled.
2. Take an on-demand backup/snapshot when the data warrants it.
3. Check that CI has applied the full migration chain successfully.
4. Deploy one version at a time.
5. Verify `/ready` immediately after deployment.

The current migration chain includes durable document blobs, owner subscription data, user sessions and tenant workspace settings.

## 7. Cloud AI

The deterministic quotation-exception workflow remains available without an AI provider. To enable cloud ranking/explanation, set:

```text
YASHCRM_AI_EXCEPTIONS_ENABLED=true
YASHCRM_AI_PROVIDER=Hugging Face Inference Providers
YASHCRM_AI_BASE_URL=https://router.huggingface.co/v1
YASHCRM_AI_MODEL=openai/gpt-oss-20b:cheapest
YASHCRM_AI_API_KEY=<fine-grained provider token>
YASHCRM_AI_TIMEOUT=90
```

Use a pinned, approved provider route before sending real customer data if provider identity or data region matters.

## 8. Operational checks

Periodically review:

- Owner Console login history and active sessions.
- Failed login bursts.
- Account status and subscription assignments.
- PostgreSQL backup health.
- Railway deployment and restart logs.
- AI provider errors and quota use.
- SMTP/SMS delivery configuration if those integrations are enabled.

SMTP, SMS and external AI delivery depend on provider credentials and cannot be proven healthy by repository CI alone. Validate them in the target Railway environment after secrets are configured.
