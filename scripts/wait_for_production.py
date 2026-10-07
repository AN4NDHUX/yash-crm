from __future__ import annotations

import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

BASE_URL = os.getenv("PRODUCTION_BASE_URL", "https://yashcrm-production.up.railway.app").rstrip("/")
EXPECTED_APP_REVISION = os.getenv("EXPECTED_APP_REVISION", "").strip()
EXPECTED_MIGRATION_REVISION = os.getenv("EXPECTED_MIGRATION_REVISION", "").strip()
ATTEMPTS = max(1, min(int(os.getenv("PRODUCTION_VERIFY_ATTEMPTS", "30")), 60))
INTERVAL_SECONDS = max(5, min(int(os.getenv("PRODUCTION_VERIFY_INTERVAL_SECONDS", "20")), 60))


def revision_matches(live: str, expected: str) -> bool:
    return bool(live and live != "unknown" and expected and (
        live.startswith(expected) or expected.startswith(live)
    ))


def check() -> tuple[bool, dict]:
    try:
        with urlopen(BASE_URL + "/ready", timeout=15) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        return False, {"error": f"{error.__class__.__name__}: {error}"}

    live_revision = str(payload.get("app_revision") or "")
    live_migration = str(payload.get("migration_revision") or "")
    ready = (
        response.status == 200
        and payload.get("status") == "ok"
        and payload.get("database") == "ready"
        and revision_matches(live_revision, EXPECTED_APP_REVISION)
        and (not EXPECTED_MIGRATION_REVISION or live_migration == EXPECTED_MIGRATION_REVISION)
    )
    return ready, payload


def main() -> int:
    if not EXPECTED_APP_REVISION:
        raise RuntimeError("EXPECTED_APP_REVISION is required")
    last: dict = {}
    for attempt in range(1, ATTEMPTS + 1):
        ok, last = check()
        if ok:
            print(json.dumps({"ok": True, "attempt": attempt, "ready": last}, indent=2))
            return 0
        print(
            json.dumps({"ok": False, "attempt": attempt, "ready": last}, sort_keys=True),
            file=sys.stderr,
        )
        if attempt < ATTEMPTS:
            time.sleep(INTERVAL_SECONDS)
    raise RuntimeError(
        f"Railway did not serve expected revision {EXPECTED_APP_REVISION} "
        f"and migration {EXPECTED_MIGRATION_REVISION or '<any>'}: {last}"
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        raise
