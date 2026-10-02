# Apex CRM change report

This package contains the Apex CRM AI performance tracking enhancement requested on 2026-10-02. The feature gives management a server-calculated, per-salesperson breakdown inside the `/ai` workspace.

## Feature delivered

- New `GET /api/ai/performance` endpoint.
- Detailed per-salesperson report inside Apex AI.
- Target, achieved, amount remaining, achievement percentage, conversions, incentive rate, threshold, eligibility and earned incentive.
- Transparent calculation rules shown under “How Apex calculates incentive”.
- Recalculate action to refresh the report after new payments, conversions or target changes.
- Apex chat fallback now returns a full salesperson-by-salesperson breakdown when asked about performance, targets, achievement or incentives.
- Existing cloud AI receives the richer performance context through the existing management context.
- Financial truth remains server-side: only Received/Cleared payments in the active target period count toward achievement.

## Files edited

These existing files from the uploaded ZIP were modified. They should be copied over the matching files in the Git repository.

| Relative path | Absolute path in this workspace | What changed |
|---|---|---|
| `app/main.py` | `/home/ubuntu/yash-crm-main/app/main.py` | Added detailed performance fields to server calculations and added `GET /api/ai/performance`. |
| `static/js/app.js` | `/home/ubuntu/yash-crm-main/static/js/app.js` | Added the Apex performance report UI, API loading, formula display, recalculate action and detailed performance fallback answers. |
| `static/css/app.css` | `/home/ubuntu/yash-crm-main/static/css/app.css` | Added responsive styles for the performance summary, detailed table, progress meters and formula disclosure. |
| `templates/index.html` | `/home/ubuntu/yash-crm-main/templates/index.html` | Existing Apex branding/template changes retained from the previous enhancement. |
| `public/manifest.webmanifest` | `/home/ubuntu/yash-crm-main/public/manifest.webmanifest` | Apex app metadata and Apex Helpdesk shortcut retained. |
| `public/manus-routes.json` | `/home/ubuntu/yash-crm-main/public/manus-routes.json` | Added Apex Helpdesk and journey routes; Apex titles retained. |
| `README.md` | `/home/ubuntu/yash-crm-main/README.md` | Added Apex AI sales performance documentation and calculation behavior. |
| `cloud-entrypoint.sh` | `/home/ubuntu/yash-crm-main/cloud-entrypoint.sh` | Updated startup log label from Yash CRM to Apex CRM. |

## Files replaced

**None.** No existing file was replaced wholesale or removed. The files above were edited in place.

## Files newly added

| Relative path | Absolute path in this workspace | Purpose |
|---|---|---|
| `APEX_CHANGE_REPORT.md` | `/home/ubuntu/yash-crm-main/APEX_CHANGE_REPORT.md` | This implementation, file-path and deployment report. |

No new runtime dependency, migration, environment variable or database table is required for this enhancement.

## Railway deployment

1. Extract the ZIP and copy the edited files into the Git repository, or replace the repository contents with the extracted `yash-crm-main` folder.
2. Commit the changes and push to the Railway-connected branch.
3. Keep the existing Railway build configuration: `railway.toml` uses the `Dockerfile`, and the health check remains `/ready`.
4. Keep production environment variables already documented in `README.md`, especially `DATABASE_URL`, `APP_PASSWORD`, `ADMIN_EMAIL`, `ALLOWED_HOSTS`, `APP_ENV=production`, and the optional `YASHCRM_AI_*` variables.
5. Deploy. The existing `cloud-entrypoint.sh` runs `alembic upgrade head` before starting Uvicorn.
6. Verify after deployment:
   - `GET /ready` returns HTTP 200.
   - `GET /api/ai/performance` returns `people`, `totals`, and `calculation_basis`.
   - Open `/ai` and confirm the “Sales performance & incentive report” appears.

The report uses the existing platform-record model, so target, payment and converted-lead records created through the current CRM UI are picked up automatically.

## Validation evidence

- `python3 -m py_compile app/main.py` passed.
- `node --check static/js/app.js` passed.
- `python3 -m pytest -q` passed: **22 tests passed**.
- Live `GET /api/ai/performance` verified successfully against the demo database.
