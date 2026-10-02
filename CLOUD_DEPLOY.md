# Deploy Yash CRM on Render

This repository is cloud-ready source, not an already deployed service. A public URL exists only after a Render account deploys the Blueprint successfully.

## 1. Create the Blueprint

1. In Render, choose **New > Blueprint**.
2. Connect `AN4NDHUX/yash-crm` and select the `main` branch.
3. Confirm Render found the root `render.yaml`.
4. Enter the prompted values:
   - `APP_PASSWORD`: a unique random value of at least 12 characters.
   - `ADMIN_EMAIL`: the real email for the initial administrator record.
5. Create the Blueprint and wait for both `yashcrm-db` and `yashcrm` to become available.

The Blueprint keeps PostgreSQL off the public network, injects its private connection string into `DATABASE_URL`, and derives `ALLOWED_HOSTS` from Render's assigned external hostname.

## 2. Verify the first deploy

The deploy log must show the migration reaching `0001_initial`, followed by Uvicorn listening on Render's `PORT`. Then verify:

1. `https://<render-host>/health` returns HTTP 200 with `status: ok` without credentials.
2. `https://<render-host>/ready` returns HTTP 200 with `database: ready` without credentials.
3. Opening the root URL requests the `APP_USERNAME` / `APP_PASSWORD` credentials.
4. The dashboard loads after login.
5. Create a disposable lead and convert it; confirm an account, contact, and deal are linked.
6. In **Settings > Users & profile**, change the administrator email and save it.

For an automated check from a trusted machine:

```bash
YASH_CRM_URL=https://<render-host> \
YASH_CRM_USERNAME=admin \
YASH_CRM_PASSWORD='<secret>' \
python scripts/check_contracts.py
```

The validation script writes disposable records and archives them. Run it only against an environment where that is acceptable.

## Custom domains

Render terminates TLS and redirects HTTP to HTTPS. After adding a custom domain, add that hostname to the existing comma-separated `ALLOWED_HOSTS` value. Do not replace the Render hostname unless you have disabled the Render subdomain.

The UI calls the API on the same origin, so `CORS_ORIGINS` should remain empty. Set it only if a separate trusted web origin genuinely needs browser access to the API.

## Operations

- Enable automated PostgreSQL backups appropriate to the data's value.
- Take an on-demand database backup before applying later migrations.
- Rotate `APP_PASSWORD` in Render; never put it in Git or a local `.env` committed to the repository.
- Keep `SEED_DEMO_DATA=false` in production.
- Use `/health` for liveness and `/ready` for traffic readiness.
- Review Render deploy logs after every Blueprint sync or migration.

## Enable the quotation AI workspace

The deterministic quotation-exception queue is cloud code and runs inside the CRM service. The optional model call is also cloud-to-cloud; no local model server is required.

For Railway or Render, add these service variables in the provider dashboard:

- `YASHCRM_AI_EXCEPTIONS_ENABLED=true`
- `YASHCRM_AI_PROVIDER=Hugging Face Inference Providers`
- `YASHCRM_AI_BASE_URL=https://router.huggingface.co/v1`
- `YASHCRM_AI_MODEL=openai/gpt-oss-20b:cheapest`
- `YASHCRM_AI_API_KEY=<fine-grained Hugging Face token>`
- `YASHCRM_AI_TIMEOUT=90`

Deploy once with the exception flag disabled first. The existing cloud entrypoint automatically applies database migration `0003_ai_revenue_exceptions`. Confirm `/ready` is healthy, enable the exception flag, and redeploy. In the authenticated CRM, open `/ai` and confirm:

1. The readiness panel shows the deterministic queue ready.
2. An eligible open quotation appears without making an AI request.
3. **AI-ranked order** consumes one provider request and returns the exact same exception set.
4. The Task preview shows owner, due date, priority, source, subject, and description before approval.
5. Approving twice returns the original Task and does not create a duplicate.

The queue still works when the token is absent, exhausted, or the provider is unavailable. The `:cheapest` route does not guarantee a fixed inference provider; pin an approved provider route before sending real customer data where provider identity or region matters. Do not describe the free allowance as unlimited production capacity.

## Authentication boundary

The current production gate is shared HTTP Basic authentication. That is acceptable for a small, tightly controlled internal deployment, but it does not provide individual login accounts, audit-grade identity, password recovery, MFA, or role enforcement. For broader or sensitive use, put the service behind an OIDC/SSO access proxy and implement server-side authorization before treating the CRM's owner/role records as security identities.
