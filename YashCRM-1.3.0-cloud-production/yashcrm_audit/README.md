# Yash CRM

A minimalist CRM workspace for leads, contacts, accounts, deals, products, activities and settings. FastAPI + SQLAlchemy on the back end, a dependency-free single-page front end (`static/js/app.js`).

## Install and run

You need **Python 3.10 to 3.14** ([python.org](https://www.python.org/downloads/)); **3.12 is recommended**. Nothing else. If several Pythons are installed, the launchers pick a supported one automatically, and refuse versions outside that range instead of failing later.

| Platform | Start it |
| --- | --- |
| Windows | Double-click `start.bat` |
| macOS | Double-click `start.command` (if macOS blocks it: right-click, Open) |
| Linux / any | `python3 launch.py` |

The first run creates a private environment and installs the dependencies (needs internet, takes a minute). After that it starts in seconds, opens <http://localhost:3000>, and keeps your data in `yashcrm.db` next to the app. Press Ctrl+C in the terminal window to stop it.

Options: `python launch.py --port 8080`, `--no-browser`, and `--lan` (share on your network; there is no login, so only on a network you trust).

### Windows: build `YashCRM.exe`

With Python installed, double-click **`build_exe.bat`**. It installs the build tool, produces `YashCRM.exe` in this folder (one file, runs without Python), and puts a **Yash CRM** shortcut on your desktop. Double-clicking it starts the server and opens the app in its own Edge/Chrome window; a small console window stays open while it runs, and closing it quits the app. Running it again while it is already open just opens another window. Data is kept in `yashcrm.db` next to the exe, so move or back up the two together.

Windows SmartScreen may warn about an unsigned app you built yourself: choose More info, then Run anyway. Rebuild after any code change.

### Make it a desktop app

With the server running, open <http://localhost:3000> in Chrome or Edge and click the **Install** icon in the address bar (or menu, Install Yash CRM). It gets its own window plus a Start menu / Dock / Launchpad entry, without browser chrome. In Safari on macOS use File, Add to Dock. The installed app is a window onto the local server, so start the server first (`start.bat` / `start.command`).

### Phone or tablet

Install prompts on phones require HTTPS, which a plain `http://192.168...` address does not provide. To use it on a phone, host it somewhere with HTTPS (see Docker below plus a reverse proxy such as Caddy), then use the browser's Add to Home Screen. Add authentication in front first, since the app has no login.

### Always-on with Docker

```bash
docker compose up -d      # http://localhost:3000, data kept in the crm-data volume
```

### Manual setup

```bash
python3 -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 3000
```

`DATABASE_URL` selects the database. Without it the app uses `sqlite:///./yashcrm.db`; `mysql://...` URLs are rewritten for PyMySQL (a `ssl=true` query flag is honoured).

## Verify

With the server running:

```bash
python scripts/check_contracts.py
```

This checks health, the route manifest, the installable-app files, the dashboard contract, and the write paths (blank-field creates, deal stage filter and stage/status sync, archive visibility, notes, validation and conflict responses). The write checks archive everything they create.

## Useful endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Readiness probe |
| `GET /manus-routes.json` | Front-end route manifest |
| `GET /api/dashboard` | Dashboard metrics |
| `GET/POST /api/{resource}` | List / create (`leads`, `contacts`, `accounts`, `deals`, `products`, `notes`, `attachments`, `emails`, `activities`, `users`, `approval_processes`, `blueprints`) |
| `GET/PATCH/DELETE /api/{resource}/{id}` | Read / update / archive |
| `POST /api/leads/{id}/convert` | Convert a lead into account, contact and optional deal |

## Behaviour worth knowing

- Delete archives records (they disappear from lists, search and detail pages). Users are deactivated instead, and approval rules and blueprints are deleted permanently.
- Moving a deal to a new stage updates its probability and status unless you changed those fields yourself in the same edit.
- Date-times are stored and shown as entered (wall-clock), with no timezone conversion.
- There is no authentication. The app assumes a single trusted workspace; put it behind your own access control before exposing it publicly.

## Migrations

`alembic upgrade head` creates the schema from the model metadata; the app also creates and additively upgrades tables on startup.

## Windows release build (1.1.0)
Use **CPython 3.12**. Other Python versions are intentionally rejected for release builds. Install Inno Setup 6, then run `build_installer.bat`. This first builds `YashCRM.exe` with PyInstaller and then creates the normal Windows installer under `release\\`. Installed application data is stored under `%LOCALAPPDATA%\\YashCRM\\data` so Program Files permissions do not block writes.

# Cloud deployment (1.2.0)

The cloud build keeps the same FastAPI/SPA CRM but runs against a managed PostgreSQL database. Desktop SQLite remains available for local use only.

## Production requirements

- Python 3.12 or the included Dockerfile.
- PostgreSQL 14+ (PostgreSQL 16 is used by the local Compose stack).
- HTTPS termination at the hosting platform/reverse proxy.
- Set `APP_ENV=production`, `DATABASE_URL`, `APP_USERNAME`, `APP_PASSWORD`, and `ALLOWED_HOSTS`.
- `APP_PASSWORD` must be at least 12 characters. Store it in the provider's secret manager, never in Git.

Copy `.env.example` to `.env` only for local testing and replace every placeholder. Do not commit `.env`.

## Run the cloud stack locally

```bash
export POSTGRES_PASSWORD='replace-with-a-random-db-password'
export APP_PASSWORD='replace-with-a-long-random-login-password'
docker compose up --build
```

Open `http://localhost:8000`. The browser will request the Basic Auth credentials (`APP_USERNAME` / `APP_PASSWORD`). `/health` is a liveness endpoint; `/ready` also verifies database connectivity.

## Database lifecycle

`cloud-entrypoint.sh` runs `alembic upgrade head` before starting Uvicorn. Production startup does not call `create_all` or perform ad-hoc `ALTER TABLE` operations. Create future schema changes as Alembic revisions and test them against a backup before deployment.

For an existing desktop SQLite database, do **not** point multiple cloud workers at the SQLite file. Provision PostgreSQL first, run the migrations, then migrate/validate records in a controlled one-time import. Keep the original SQLite file as a backup until row counts and key relationships are verified.

## Render

`render.yaml` describes a Docker web service plus managed PostgreSQL. In Render, create the Blueprint, then review the generated hostname and update `ALLOWED_HOSTS` if Render assigned a different service hostname. The generated `APP_PASSWORD` is secret; set your own known strong value if you need browser login credentials. Add a custom domain in Render when ready; TLS is terminated by the platform.

## Railway

`railway.toml` uses the Dockerfile. Add a PostgreSQL service and set these variables on the application service: `APP_ENV=production`, `DATABASE_URL` (from Railway PostgreSQL), `ENABLE_AUTH=true`, `APP_USERNAME`, a 12+ character `APP_PASSWORD`, `ADMIN_NAME`, `ADMIN_EMAIL`, and `ALLOWED_HOSTS` for the assigned/custom domain.

## Authentication note

The cloud baseline includes application-level HTTP Basic protection so the CRM is not anonymously exposed. For an organization with multiple independently authenticated staff, replace the gateway authentication with an identity provider (OIDC/SSO) and per-user authorization before treating the CRM's `users` table as login identities. The current CRM `users` records represent owners/roles, not password-bearing authentication accounts.

## Backups

Use the managed PostgreSQL provider's automated backups. Before migrations or major releases, also take an on-demand database snapshot/dump. Application containers are stateless; CRM records belong in PostgreSQL, not the container filesystem.

## Friendly local domain: `yashcrm.local`

This release uses **`http://yashcrm.local`** as the friendly local address (the launcher adds the selected port, normally `:3000`; Docker Compose normally uses `:8000`). It is intentionally local-only and is **not a public Internet domain**.

On Windows, run `setup-local-domain.bat` once. Windows will request Administrator permission because the script adds `127.0.0.1 yashcrm.local` to the system hosts file and flushes the DNS cache. The script is idempotent and will not add duplicate entries. `remove-local-domain.bat` removes that mapping. `start-local-domain.bat` performs the setup when needed and then starts Yash CRM.

Fallback diagnostics remain available through `http://localhost:<port>` and `http://127.0.0.1:<port>`. The PostgreSQL/cloud deployment files remain in the project for a future real public hostname.

> Note: `.local` is conventionally used by mDNS/Bonjour. The explicit Windows hosts-file entry normally resolves it locally, but if another network component overrides `.local`, use `localhost` or change the friendly hostname to a reserved testing name such as `yashcrm.test`.

## Browser-only cloud operation (v1.3)
For production, deploy the Docker service and PostgreSQL database described in `CLOUD_DEPLOY.md`. Users then open the provider-assigned HTTPS URL directly in any modern browser. Client computers do not run PowerShell, Python, `start.bat`, or `start-local-domain.bat`. The `yashcrm.local` scripts remain local-development helpers only.
