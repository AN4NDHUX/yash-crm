from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AIRevenueExceptionTests(unittest.TestCase):
    def test_deterministic_queue_rank_and_idempotent_task_approval(self) -> None:
        database_name = f"test-ai-exceptions-{uuid.uuid4().hex}.db"
        script = textwrap.dedent(
            """
            import json
            import socket
            import threading
            import time
            import urllib.error
            import urllib.request
            from datetime import date, timedelta
            import uvicorn
            import app.main as main

            def fake_cloud(body):
                content = json.loads(body["messages"][1]["content"])
                ranked = [{"ref": item["ref"], "rationale": "Validity needs follow-up.", "description": "Confirm the quotation remains current.", "intent": "quote_follow_up"} for item in reversed(content["EXCEPTIONS"])]
                return {"id": "fake-request", "choices": [{"message": {"content": json.dumps({"ranked": ranked})}}], "usage": {"prompt_tokens": 10, "completion_tokens": 10}}

            main.AI_API_KEY = "test-token"
            main._cloud_ai_json = fake_cloud
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            listener.close()
            server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="error"))
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{port}"

            def request(path, method="GET", payload=None, headers=None):
                data = json.dumps(payload).encode() if payload is not None else None
                request_headers = {"Content-Type": "application/json", **(headers or {})}
                call = urllib.request.Request(base + path, data=data, headers=request_headers, method=method)
                try:
                    with urllib.request.urlopen(call, timeout=5) as response:
                        return response.status, json.loads(response.read().decode())
                except urllib.error.HTTPError as error:
                    return error.code, json.loads(error.read().decode())

            deadline = time.time() + 10
            while not server.started and time.time() < deadline:
                time.sleep(0.02)
            assert server.started, "test server did not start"
            try:
                with main.SessionLocal() as db:
                    owner = db.scalar(main.select(main.User).where(main.User.status == "Active").order_by(main.User.id))
                    quote = main.PlatformRecord(
                        resource="quotes", title="Pilot Quote", status="Sent", owner_id=owner.id,
                        amount=2000000, version=1,
                        data={"quote_number": "QUO-PILOT", "valid_until": (date.today() + timedelta(days=2)).isoformat(), "currency": "INR"},
                    )
                    db.add(quote); db.commit()

                listing_status, body = request("/api/ai/exceptions")
                assert listing_status == 200, body
                pilot = next(item for item in body["items"] if item["quote_label"] == "QUO-PILOT")
                _, status = request("/api/ai/status")
                headers = {"X-Yash-CSRF": status["csrf_token"]}
                ranked_status, ranked = request("/api/ai/exceptions/rank", "POST", {"occurrence_ids": [pilot["id"]]}, headers)
                assert ranked_status == 200, ranked
                proposal = ranked["items"][0]["proposal"]
                assert proposal["activity_type"] == "Task"
                approved_status, approved = request(f"/api/ai/proposals/{proposal['id']}/approve", "POST", {}, headers)
                assert approved_status == 200, approved
                assert approved["duplicate"] is False
                repeated_status, repeated = request(f"/api/ai/proposals/{proposal['id']}/approve", "POST", {}, headers)
                assert repeated_status == 200, repeated
                assert repeated["duplicate"] is True
                with main.SessionLocal() as db:
                    tasks = db.scalars(main.select(main.Activity).where(main.Activity.related_type == "quotes", main.Activity.subject.like("Follow up quotation QUO-PILOT%"))).all()
                    assert len(tasks) == 1, tasks
                rejected_status, rejected = request("/api/ai/exceptions/rank", "POST", {"occurrence_ids": [pilot["id"]]})
                assert rejected_status == 403, rejected
            finally:
                server.should_exit = True
                thread.join(timeout=5)
            """
        )
        env = os.environ.copy()
        env.update({
            "APP_ENV": "development",
            "DATABASE_URL": f"sqlite:///./{database_name}",
            "ENABLE_AUTH": "false",
            "YASHCRM_AI_EXCEPTIONS_ENABLED": "true",
        })
        try:
            result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        finally:
            path = ROOT / database_name
            if path.exists():
                path.unlink()


if __name__ == "__main__":
    unittest.main()
