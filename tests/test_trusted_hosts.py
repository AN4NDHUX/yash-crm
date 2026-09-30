from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TrustedHostTests(unittest.TestCase):
    def run_request(self, path: str, host: str, method: str = "GET") -> int:
        script = textwrap.dedent(
            f"""
            from fastapi.testclient import TestClient
            from app.main import app

            with TestClient(app) as client:
                response = client.request({method!r}, {path!r}, headers={{"host": {host!r}}})
                print(response.status_code)
            """
        )
        env = os.environ.copy()
        env.update(
            {
                "APP_ENV": "development",
                "DATABASE_URL": "sqlite:///./test-trusted-hosts.db",
                "ALLOWED_HOSTS": "yashcrm-production.up.railway.app",
                "ENABLE_AUTH": "false",
            }
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=env,
            capture_output=True,
            check=True,
            text=True,
        )
        return int(result.stdout.strip().splitlines()[-1])

    def test_ready_accepts_internal_healthcheck_host(self) -> None:
        self.assertEqual(self.run_request("/ready", "railway-internal"), 200)

    def test_normal_route_rejects_internal_host(self) -> None:
        self.assertEqual(self.run_request("/", "railway-internal"), 400)

    def test_other_health_routes_reject_internal_host(self) -> None:
        self.assertEqual(self.run_request("/health", "railway-internal"), 400)
        self.assertEqual(self.run_request("/ready/", "railway-internal"), 400)
        self.assertEqual(self.run_request("/ready", "railway-internal", "POST"), 400)

    def test_ready_accepts_public_host(self) -> None:
        self.assertEqual(
            self.run_request("/ready", "yashcrm-production.up.railway.app"),
            200,
        )


if __name__ == "__main__":
    unittest.main()
