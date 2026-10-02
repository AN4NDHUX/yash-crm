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

## Authentication boundary

The current production gate is shared HTTP Basic authentication. That is acceptable for a small, tightly controlled internal deployment, but it does not provide individual login accounts, audit-grade identity, password recovery, MFA, or role enforcement. For broader or sensitive use, put the service behind an OIDC/SSO access proxy and implement server-side authorization before treating the CRM's owner/role records as security identities.
