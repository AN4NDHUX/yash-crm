# Yash CRM — cloud deployment

This release is designed to run continuously on a cloud web service. End users need only a modern browser and the HTTPS URL; they do not run PowerShell, Python, BAT files, or a local server.

## Render Blueprint path
1. Push the contents of this folder to a Git repository.
2. In Render, create a Blueprint from that repository. `render.yaml` creates the web service and PostgreSQL database.
3. After Render assigns the web-service hostname, set these service environment variables to that hostname:
   - `PUBLIC_URL=https://<assigned-hostname>`
   - `ALLOWED_HOSTS=<assigned-hostname>`
   - `CORS_ORIGINS=https://<assigned-hostname>`
4. Keep `APP_PASSWORD` secret. Render generates it when the Blueprint is created; replace/rotate it if required.
5. Redeploy. Open the HTTPS service URL in Chrome, Edge, Firefox, Safari, Android, or iOS.

The container runs `alembic upgrade head` before Uvicorn starts. `/health` is the liveness endpoint and `/ready` checks database readiness.

## Important
`yashcrm.local`, `setup-local-domain.bat`, and the Windows launcher are retained only for optional local development/backward compatibility. They are not used by cloud clients.

A public URL does not exist until the repository is deployed to a hosting account. This source package cannot create or own a cloud account, DNS name, or TLS certificate by itself.
