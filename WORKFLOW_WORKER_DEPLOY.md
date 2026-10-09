# Workflow worker deployment

The web app and the worker are separate Railway services using the same PostgreSQL database.

## Deploying the worker on Railway
1. Ensure the web service has migrated PostgreSQL to the **current Alembic head** (check `python -m alembic heads`; do not assume an older hardcoded revision).
2. Add a **new Railway service** from the same `AN4NDHUX/yash-crm` repository.
3. Configure its Dockerfile path to **Dockerfile.worker**. No public domain or HTTP health check is required.
4. Configure the same `DATABASE_URL` as the CRM web service (reference the existing PostgreSQL service variable), and set `APP_ENV=production`.
5. Set `WORKFLOW_POLL_SECONDS=15` (minimum five seconds). One worker process is sufficient initially. PostgreSQL `FOR UPDATE SKIP LOCKED` allows safe multiworker claims.
6. Deploy and inspect the worker logs. Run a workflow with a scheduled action and verify status transitions `queued -> running -> completed`.
7. Execute `APP_ENV=production DATABASE_URL=... python -m scripts.check_worker_readiness` in the worker environment. It checks PostgreSQL connectivity, the migration head, and queue schema without claiming or sending any jobs. The same check runs in GitHub CI against PostgreSQL 17.
8. Confirm that Railway actually has a **second running service** configured with `Dockerfile.worker`. A successful web deployment or CI preflight does not prove the separate worker is deployed.
9. For `invokeurl` OAuth connections, configure `DELUGE_HTTP_CONNECTIONS_JSON` and referenced secret environment variables on the worker, scoped to the exact organization ID (see `DELUGE_INTEGRATIONS.md`).

## Optional email configuration
- `WORKFLOW_SMTP_HOST`, `WORKFLOW_SMTP_PORT` (default `587`), `WORKFLOW_SMTP_USER`, `WORKFLOW_SMTP_PASSWORD`
- `WORKFLOW_EMAIL_FROM`
- `WORKFLOW_EMAIL_RECIPIENTS`: comma-separated explicit allowlist of permitted destination email addresses.

SMTP uses STARTTLS and never accepts workflow-provided SMTP servers.

## Optional webhook configuration
- `WORKFLOW_WEBHOOK_URL`: the fixed, trusted, HTTPS URL set by the deployer, not by the workflow rule.
- `WORKFLOW_WEBHOOK_SECRET`: at least 32 characters, stored only in Railway environment variables.
- Recipient should verify the `X-CRM-Signature` HMAC-SHA256 over the raw request body and deduplicate by `X-CRM-Idempotency-Key`.
- Redirects are disabled and arbitrary user-provided URLs are ignored. Configure the endpoint to a trusted controlled receiver.

## Reliability and security limitations
- Queue, lease and retry state is durable in PostgreSQL. Retry delay is exponential and bounded, with a maximum of five attempts.
- **Delivery is at-least-once, not exactly-once.** A crash after SMTP/webhook success and before the database commit can cause duplicate delivery. Webhook receivers must implement idempotency; SMTP recipients may receive duplicates.
- A combination of immediate and external actions in one execution is not transactionally atomic with external delivery; design rules to avoid repeated non-idempotent actions.
- Failed executions are visible in Workflow Rules execution history and may be explicitly requeued by organization administrators.
- Email recipient selection is intentionally restricted; webhook targets are centrally configured. Fully dynamic recipient/endpoint administration is **not implemented**.
- A deployed web service does **not** imply the separate worker is deployed. Verify the Railway worker service independently.
