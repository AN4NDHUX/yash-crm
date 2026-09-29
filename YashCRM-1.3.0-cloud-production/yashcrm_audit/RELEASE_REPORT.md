# Yash CRM 1.3.0 Cloud Production Release

## Changes
- Reworked sidebar gloss into a single low-opacity, low-density highlight with a 22-second continuous GPU-friendly pass.
- Main background retains a slightly denser two-layer gloss at low opacity with a slower 28-second pass.
- Added reduced-motion behavior and kept overlays non-interactive.
- Production runtime is browser-only for clients: Docker + FastAPI + PostgreSQL + Alembic.
- Render Blueprint provisions the web service and PostgreSQL connection; production accepts the provider's `*.onrender.com` hostname.
- Local-domain/Windows scripts remain only as optional development/backward-compatibility helpers.

## Verification performed here
- Python syntax/import compilation passed.
- Existing running-instance contract checker passed against a clean temporary SQLite development database.
- Contract coverage exercised health, route manifest, dashboard, Leads, Contacts, Accounts, Deals, Activities, CRUD/search and validation behavior.
- Docker/Render deployment itself was not executed in this environment, so no live public URL is claimed.

## Production use
Deploy this repository using `render.yaml`, then use the HTTPS URL assigned by Render. No client-side PowerShell, Python, BAT file, hosts-file entry, or locally running backend is required.
