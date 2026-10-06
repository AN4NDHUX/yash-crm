from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_app_script(body: str) -> dict:
    script = (
        "import base64, json\n"
        "from fastapi.testclient import TestClient\n"
        "import app.main as main\n"
        "from app.platform_catalog import PLATFORM_RESOURCES\n"
        "token = base64.b64encode(b'admin:supersecretpass123').decode()\n"
        "auth = {'Authorization': 'Basic ' + token}\n"
        "out = {}\n" + textwrap.dedent(body) + "\nprint('RESULT' + json.dumps(out, default=str))\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env.update({
            "APP_ENV": "development",
            "DATABASE_URL": f"sqlite:///{tmp}/test.db",
            "ENABLE_AUTH": "true",
            "APP_USERNAME": "admin",
            "APP_PASSWORD": "supersecretpass123",
            "PYTHONPATH": str(ROOT),
        })
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise AssertionError(result.stderr[-5000:])
    line = [row for row in result.stdout.splitlines() if row.startswith("RESULT")][-1]
    return json.loads(line[6:])


def test_all_core_and_platform_module_list_apis_respond():
    out = run_app_script("""
    with TestClient(main.app) as c:
        failures = {}
        for resource in ['leads','contacts','accounts','deals','activities','products']:
            r = c.get(f'/api/{resource}?limit=1', headers=auth)
            if r.status_code != 200:
                failures[f'core:{resource}'] = [r.status_code, r.text[:200]]
        for resource in PLATFORM_RESOURCES:
            r = c.get(f'/api/platform/{resource}?limit=1', headers=auth)
            if r.status_code != 200:
                failures[f'platform:{resource}'] = [r.status_code, r.text[:200]]
        out['failures'] = failures
    """)
    assert out["failures"] == {}


def test_critical_administration_and_ai_surfaces_respond():
    out = run_app_script("""
    with TestClient(main.app) as c:
        paths = [
            '/api/platform/catalog',
            '/api/settings/general',
            '/api/settings/profile',
            '/api/users?limit=1',
            '/api/audit?limit=1',
            '/api/administration/recycle-bin?limit=1',
            '/api/ai/status',
            '/api/ai/exceptions/readiness',
            '/api/admin/metadata/modules',
        ]
        failures = {}
        for path in paths:
            r = c.get(path, headers=auth)
            if r.status_code != 200:
                failures[path] = [r.status_code, r.text[:200]]
        out['failures'] = failures
    """)
    assert out["failures"] == {}
