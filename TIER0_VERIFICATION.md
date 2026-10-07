# Tier 0 Production Verification

Tier 0 is complete only when both GitHub CI and the production verification workflow pass for the same commit.

## Automated gates

The main CI workflow verifies:

- dependency vulnerability audit with pip-audit
- Bandit security scan
- Python compilation
- frontend JavaScript syntax
- PostgreSQL migration upgrade to Alembic head
- the full pytest regression suite

After that workflow succeeds on main, `.github/workflows/tier0-production-verification.yml` runs against Railway.

The production verifier checks:

1. `/health` returns 200 and `status=ok`.
2. `/ready` returns 200 and `database=ready`.
3. the live application revision matches the commit that passed CI.
4. the live Alembic revision matches the repository migration head.
5. Administrator login succeeds.
6. `/owner` is available to the platform owner.
7. logout invalidates the session.
8. Tenant A can create a disposable lead.
9. Tenant B receives 404 when requesting Tenant A's lead.
10. Tenant B receives 403 from the administrator user endpoint.
11. the disposable lead is archived after the isolation check.
12. unsigned Stripe and Razorpay webhook requests are rejected with HTTP 400.

## GitHub Actions configuration

Set repository variable:

- `PRODUCTION_BASE_URL` — optional; defaults to `https://yashcrm-production.up.railway.app`.

Set these GitHub Actions secrets:

- `PRODUCTION_ADMIN_USERNAME`
- `PRODUCTION_ADMIN_PASSWORD`
- `PRODUCTION_SMOKE_USER_A_IDENTIFIER`
- `PRODUCTION_SMOKE_USER_A_PASSWORD`
- `PRODUCTION_SMOKE_USER_B_IDENTIFIER`
- `PRODUCTION_SMOKE_USER_B_PASSWORD`

The two smoke users must be normal active users belonging to two different organizations. Do not use real customer accounts.

## Railway revision evidence

`/ready` now reports:

- `migration_revision` from the production `alembic_version` table.
- `app_revision` from `APP_REVISION`, `RAILWAY_GIT_COMMIT_SHA`, or `GIT_COMMIT_SHA`.

Railway should expose its Git commit SHA through `RAILWAY_GIT_COMMIT_SHA`. If that is unavailable in a target environment, set `APP_REVISION` during deployment to the exact Git commit SHA.

No Tier 0 release should be marked complete when `app_revision` or `migration_revision` is `unknown`.
