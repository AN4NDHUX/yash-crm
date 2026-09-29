# YashCRM 1.2.1 Local Domain Release

## Canonical local URL
`http://yashcrm.local`

The source launcher normally uses port 3000 (`http://yashcrm.local:3000`). Docker Compose exposes port 8000 (`http://yashcrm.local:8000`). The hostname is local-only and maps to `127.0.0.1`; it is not publicly routable.

## Changes
- Launcher and desktop wrapper open `yashcrm.local` instead of `localhost`.
- Added `setup-local-domain.bat` with Windows elevation, duplicate detection and DNS-cache flush.
- Added `remove-local-domain.bat` cleanup script.
- Added `start-local-domain.bat` convenience launcher.
- `.env.example` and Docker Compose allow `yashcrm.local` while preserving localhost/127.0.0.1 fallbacks.
- PostgreSQL/cloud deployment support remains intact for later assignment of a real public hostname.

## Verification performed in this environment
- Python compile check: PASS.
- Local-domain configuration assertions: PASS.
- FastAPI TestClient smoke checks with Host `yashcrm.local`: `/health`, `/ready`, `/`, `/leads`, `/deals`, `/contacts`, `/accounts` all returned HTTP 200.
- The package has no pytest `tests/` directory, so no pytest suite was claimed.
- Windows hosts-file scripts were statically reviewed but cannot be executed in this Linux environment.

## Windows use
1. Extract the ZIP.
2. Run `setup-local-domain.bat` once and approve the Administrator prompt.
3. Start with `start-local-domain.bat` (or the normal launcher).
4. If needed, remove the mapping with `remove-local-domain.bat`.

`.local` is conventionally associated with mDNS. The explicit hosts mapping normally works on Windows; `localhost` remains the fallback.
