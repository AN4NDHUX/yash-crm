from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
USERNAME = "admin"
PASSWORD = "supersecretpass123"


def run_app_script(body: str, **env_overrides: str) -> dict:
    """Run `body` in a fresh interpreter with a throwaway SQLite DB; it must set `out`."""
    script = (
        "import base64, json\n"
        "from fastapi.testclient import TestClient\n"
        "import app.main as main\n"
        "def basic(user, password, scheme='Basic', pad=True):\n"
        "    token = base64.b64encode(f'{user}:{password}'.encode()).decode()\n"
        "    return {'Authorization': f\"{scheme} {token if pad else token.rstrip('=')}\"}\n"
        "out = {}\n"
        + textwrap.dedent(body)
        + "\nprint('RESULT' + json.dumps(out))\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env.update(
            {
                "APP_ENV": "development",
                "DATABASE_URL": f"sqlite:///{tmp}/test.db",
                "ENABLE_AUTH": "true",
                "APP_USERNAME": USERNAME,
                "APP_PASSWORD": PASSWORD,
                "PYTHONPATH": str(ROOT),
            }
        )
        env.update(env_overrides)
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120
        )
    if result.returncode != 0:
        raise AssertionError(result.stderr[-2000:])
    line = [row for row in result.stdout.splitlines() if row.startswith("RESULT")][-1]
    return json.loads(line[len("RESULT"):])


class PublicAssetTests(unittest.TestCase):
    """Public auth/brand surfaces load without credentials; CRM data stays protected."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.out = run_app_script(
            """
            with TestClient(main.app, follow_redirects=False) as c:
                def probe(method, path, headers=None):
                    r = c.request(method, path, headers=headers or {})
                    return [r.status_code, r.headers.get('content-type', '')]
                out['manifest'] = probe('GET', '/manifest.webmanifest')
                out['manifest_head'] = probe('HEAD', '/manifest.webmanifest')
                out['favicon_ico'] = probe('GET', '/favicon.ico')
                out['favicon_svg'] = probe('GET', '/favicon.svg')
                out['icon_192'] = probe('GET', '/static/icons/icon-192.png')
                out['health'] = probe('GET', '/health')
                out['css'] = probe('GET', '/static/css/app.css')
                out['js'] = probe('GET', '/static/js/app.js')
                out['traversal'] = probe('GET', '/static/icons/%2e%2e/%2e%2e/app/main.py')
                out['post_manifest'] = probe('POST', '/manifest.webmanifest')
                out['dashboard'] = probe('GET', '/api/dashboard')
                out['ai_page'] = probe('GET', '/ai')
                out['login_page'] = probe('GET', '/login')
                out['signup_page'] = probe('GET', '/signup')
            """
        )

    def test_manifest_is_public(self) -> None:
        self.assertEqual(self.out["manifest"][0], 200)
        self.assertIn("manifest+json", self.out["manifest"][1])
        self.assertEqual(self.out["manifest_head"][0], 200)

    def test_favicon_ico_is_a_real_icon_and_public(self) -> None:
        self.assertEqual(self.out["favicon_ico"][0], 200)
        self.assertIn("image/x-icon", self.out["favicon_ico"][1])  # not the SPA's text/html

    def test_other_browser_fetched_assets_are_public(self) -> None:
        self.assertEqual(self.out["favicon_svg"][0], 200)
        self.assertEqual(self.out["icon_192"][0], 200)
        self.assertEqual(self.out["health"][0], 200)

    def test_exemption_is_exact_not_a_prefix(self) -> None:
        self.assertEqual(self.out["css"][0], 401)
        self.assertEqual(self.out["js"][0], 401)
        self.assertEqual(self.out["traversal"][0], 401)
        self.assertEqual(self.out["post_manifest"][0], 401)  # only GET/HEAD are exempt

    def test_auth_pages_are_public_and_app_surfaces_redirect(self) -> None:
        self.assertEqual(self.out["login_page"][0], 200)
        self.assertEqual(self.out["signup_page"][0], 200)
        self.assertEqual(self.out["dashboard"][0], 401)
        self.assertEqual(self.out["ai_page"][0], 303)


class AiRouteAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.out = run_app_script(
            """
            good = basic('admin', 'supersecretpass123')
            with TestClient(main.app, follow_redirects=False) as c:
                def code(method, path, headers=None):
                    return c.request(method, path, headers=headers or {}).status_code
                r = c.get('/api/ai/status')
                out['status_noauth'] = [r.status_code, r.json(), r.headers.get('www-authenticate', '')]
                out['status'] = code('GET', '/api/ai/status', good)
                out['status_slash'] = code('GET', '/api/ai/status/', good)
                out['status_head'] = code('HEAD', '/api/ai/status', good)
                out['ready'] = code('GET', '/api/ai/exceptions/readiness', good)
                out['ready_slash'] = code('GET', '/api/ai/exceptions/readiness/', good)
                out['ready_head'] = code('HEAD', '/api/ai/exceptions/readiness', good)
                out['lower_scheme'] = code('GET', '/api/ai/status', basic('admin', 'supersecretpass123', scheme='basic'))
                out['unpadded'] = code('GET', '/api/ai/status', basic('admin', 'supersecretpass123', pad=False))
                out['wrong_password'] = code('GET', '/api/ai/status', basic('admin', 'wrong-password-123'))
                out['garbage_header'] = code('GET', '/api/ai/status', {'Authorization': 'Basic !!!not-base64'})
                out['bearer'] = code('GET', '/api/ai/status', {'Authorization': 'Bearer abc'})
                out['ai_page'] = code('GET', '/ai', good)
                out['ai_page_slash'] = code('GET', '/ai/', good)
                out['unknown_api'] = code('GET', '/api/ai/nope', good)
                out['unknown_api_slash'] = code('GET', '/api/ai/nope/', good)
            """
        )

    def test_missing_credentials_get_session_aware_json_401(self) -> None:
        status, body, challenge = self.out["status_noauth"]
        self.assertEqual(status, 401)
        self.assertEqual(body, {"detail": "Sign in to continue"})
        self.assertEqual(challenge, "")

    def test_status_and_readiness_return_200(self) -> None:
        for key in ("status", "ready", "status_head", "ready_head", "ai_page", "ai_page_slash"):
            self.assertEqual(self.out[key], 200, key)

    def test_trailing_slash_no_longer_404s(self) -> None:
        self.assertEqual(self.out["status_slash"], 200)
        self.assertEqual(self.out["ready_slash"], 200)

    def test_unknown_api_paths_still_404(self) -> None:
        self.assertEqual(self.out["unknown_api"], 404)
        self.assertEqual(self.out["unknown_api_slash"], 404)

    def test_basic_parsing_is_tolerant_but_not_permissive(self) -> None:
        self.assertEqual(self.out["lower_scheme"], 200)
        self.assertEqual(self.out["unpadded"], 200)
        for key in ("wrong_password", "garbage_header", "bearer"):
            self.assertEqual(self.out[key], 401, key)


class ConfigRobustnessTests(unittest.TestCase):
    def test_malformed_ai_base_url_is_reported_not_422(self) -> None:
        out = run_app_script(
            """
            with TestClient(main.app) as c:
                h = basic('admin', 'supersecretpass123')
                s = c.get('/api/ai/status', headers=h)
                r = c.get('/api/ai/exceptions/readiness', headers=h)
                out['status'] = [s.status_code, s.json().get('configured'), s.json().get('detail')]
                out['ready'] = [r.status_code, r.json().get('ai_ready')]
            """,
            YASHCRM_AI_BASE_URL="https://[router.huggingface.co/v1",
            YASHCRM_AI_API_KEY="x",
        )
        self.assertEqual(out["status"][0], 200)
        self.assertFalse(out["status"][1])
        self.assertIn("YASHCRM_AI_BASE_URL", out["status"][2])
        self.assertEqual(out["ready"], [200, False])

    def test_bad_port_is_a_config_error(self) -> None:
        out = run_app_script(
            """
            with TestClient(main.app) as c:
                s = c.get('/api/ai/status', headers=basic('admin', 'supersecretpass123'))
                out['status'] = [s.status_code, s.json().get('configured')]
            """,
            YASHCRM_AI_BASE_URL="https://router.huggingface.co:abc/v1",
            YASHCRM_AI_API_KEY="x",
        )
        self.assertEqual(out["status"], [200, False])

    def test_non_numeric_timeout_does_not_crash_startup(self) -> None:
        out = run_app_script(
            "with TestClient(main.app) as c:\n    out['code'] = c.get('/health').status_code\n",
            YASHCRM_AI_TIMEOUT="ninety",
        )
        self.assertEqual(out["code"], 200)

    def test_empty_timezone_is_a_setup_state_not_a_422(self) -> None:
        out = run_app_script(
            """
            with TestClient(main.app) as c:
                with main.SessionLocal() as db:
                    setting = main.get_or_create_settings(db)
                    setting.timezone = ''
                    db.commit()
                h = basic('admin', 'supersecretpass123')
                r = c.get('/api/ai/exceptions/readiness', headers=h)
                e = c.get('/api/ai/exceptions', headers=h)
                out['ready'] = [r.status_code, r.json()['checks'][0]['ready']]
                out['list'] = e.status_code
            """
        )
        self.assertEqual(out["ready"], [200, False])
        self.assertEqual(out["list"], 409)


class SessionStabilityTests(unittest.TestCase):
    def test_trailing_newline_in_password_secret_still_authenticates(self) -> None:
        out = run_app_script(
            "with TestClient(main.app) as c:\n    out['code'] = c.get('/api/ai/status', headers=basic('admin', 'supersecretpass123')).status_code\n",
            APP_PASSWORD=PASSWORD + "\n",
        )
        self.assertEqual(out["code"], 200)

    def test_csrf_token_is_stable_across_restarts_and_secret_bound(self) -> None:
        body = "with TestClient(main.app) as c:\n    out['token'] = c.get('/api/ai/status', headers=basic('admin', 'supersecretpass123')).json()['csrf_token']\n"
        first = run_app_script(body)["token"]
        second = run_app_script(body)["token"]
        rotated = run_app_script(body, YASHCRM_CSRF_SECRET="a-different-server-secret")["token"]
        self.assertEqual(first, second)
        self.assertNotEqual(first, rotated)
        self.assertNotIn(PASSWORD, first)

    def test_csrf_still_enforced_with_the_stable_token(self) -> None:
        out = run_app_script(
            """
            with TestClient(main.app) as c:
                h = basic('admin', 'supersecretpass123')
                token = c.get('/api/ai/status', headers=h).json()['csrf_token']
                body = {'occurrence_ids': ['x']}
                out['no_token'] = c.post('/api/ai/exceptions/rank', json=body, headers=h).status_code
                out['bad_token'] = c.post('/api/ai/exceptions/rank', json=body, headers={**h, 'X-Yash-CSRF': 'nope'}).status_code
                out['cross_origin'] = c.post('/api/ai/exceptions/rank', json=body, headers={**h, 'X-Yash-CSRF': token, 'Origin': 'https://evil.example'}).status_code
            """
        )
        self.assertEqual(out["no_token"], 403)
        self.assertEqual(out["bad_token"], 403)
        self.assertEqual(out["cross_origin"], 403)


if __name__ == "__main__":
    unittest.main()
