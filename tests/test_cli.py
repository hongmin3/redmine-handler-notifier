"""Real CLI checks with disposable files and loopback HTTP, never production settings."""
import json
import os
import shutil
import subprocess
import sys
import threading
import unittest
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse


# Validates: REQ-QUERY-001, REQ-DAILY-001, REQ-WEEKLY-001,
# REQ-DELIVERY-001, NFR-SECURITY-001
class CliTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        shutil.copyfile(Path(__file__).resolve().parents[1] / "redmine_notifier.py",
                        self.root / "redmine_notifier.py")
        self.issues = [{"id": 1, "subject": "First issue", "status": {"name": "신규"},
                        "updated_on": datetime.now(timezone.utc).isoformat(),
                        "custom_fields": [{"name": "Grade", "value": "A"}]}]
        self.posts = []
        self.queries = []
        self.post_status = 202
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                owner.assertEqual(self.headers.get("X-Redmine-API-Key"), "fixture-key")
                query = parse_qs(urlparse(self.path).query)
                owner.queries.append(query)
                offset = int(query.get("offset", ["0"])[0])
                batch = owner.issues[offset:offset + 1]
                content = json.dumps({"issues": batch, "total_count": len(owner.issues)}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(content)

            def do_POST(self):
                owner.posts.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(owner.post_status)
                self.end_headers()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.environment = dict(os.environ)
        for key in list(self.environment):
            if key.startswith(("REDMINE_", "TEAMS_", "NOTIFICATION")):
                self.environment.pop(key)
        self.environment.update({"NOTIFICATIONS_ENABLED": "true", "REDMINE_BASE_URL": self.url,
                                 "REDMINE_PROJECT_ID": "fixture", "REDMINE_API_KEY": "fixture-key",
                                 "TEAMS_WEBHOOK_URL": self.url + "/webhook", "HTTP_TIMEOUT_SECONDS": "1"})

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def invoke(self, *args):
        return subprocess.run([sys.executable, str(self.root / "redmine_notifier.py"), *args],
                              cwd=self.root, env=self.environment, capture_output=True,
                              text=True, encoding="utf-8", timeout=15)

    @property
    def state_file(self):
        return self.root / "runtime/state.json"

    def test_daily_success_pages_and_repeat_does_not_resend(self):
        self.issues.append({**self.issues[0], "id": 2, "subject": "Last page issue"})
        result = self.invoke("daily")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([q["offset"] for q in self.queries], [["0"], ["1"]])
        self.assertTrue(all(q["status_id"] == ["open"] for q in self.queries))
        content = json.dumps(self.posts, ensure_ascii=False)
        self.assertIn("Last page issue", content)
        self.assertNotIn("fixture-key", content)
        state = json.loads(self.state_file.read_text())
        self.assertEqual(len(state["daily_seen"]), 2)
        self.assertIn("daily_last_success_utc", state)
        sent = len(self.posts)
        repeat = self.invoke("daily")
        self.assertEqual(repeat.returncode, 0, repeat.stderr)
        self.assertEqual(len(self.posts), sent)
        self.assertIn("Notification skipped", repeat.stderr)

    def test_dry_run_generates_preview_without_send_or_state_change(self):
        self.state_file.parent.mkdir(parents=True)
        original = b'{"daily_seen":[]}'
        self.state_file.write_bytes(original)
        preview = self.root / "preview.json"
        result = self.invoke("daily", "--dry-run", "--preview-file", str(preview))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("First issue", preview.read_text(encoding="utf-8"))
        self.assertEqual(self.posts, [])
        self.assertEqual(self.state_file.read_bytes(), original)

    def test_failed_delivery_does_not_advance_success_state(self):
        self.post_status = 503
        self.state_file.parent.mkdir(parents=True)
        original = b'{"daily_seen":[]}'
        self.state_file.write_bytes(original)
        result = self.invoke("daily")
        self.assertEqual(result.returncode, 1)
        self.assertIn("HTTP 503", result.stderr)
        self.assertEqual(self.state_file.read_bytes(), original)

    def test_off_never_queries_or_posts(self):
        self.environment["NOTIFICATIONS_ENABLED"] = "false"
        self.environment.pop("REDMINE_API_KEY")
        result = self.invoke("daily")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Notifications are OFF", result.stderr)
        self.assertEqual(self.queries, [])
        self.assertEqual(self.posts, [])
        self.assertFalse(self.state_file.exists())

    def test_weekly_preserves_last_issue_of_long_handler_and_excludes_grade_d(self):
        now = self.issues[0]["updated_on"]
        self.issues = [{**self.issues[0], "id": i, "subject": f"Issue-{i}-" + "x" * 90,
                        "assigned_to": {"name": "Handler"}} for i in range(1, 8)]
        self.issues.append({"id": 99, "subject": "excluded-marker", "updated_on": now,
                            "custom_fields": [{"name": "Grade", "value": "D"}]})
        self.environment["TEAMS_MAX_CHARS"] = "400"
        result = self.invoke("weekly")
        self.assertEqual(result.returncode, 0, result.stderr)
        text = "".join(p["attachments"][0]["content"]["body"][2]["text"] for p in self.posts)
        for i in range(1, 8):
            self.assertIn(f"Issue-{i}-", text)
        self.assertNotIn("excluded-marker", text)
        self.assertGreater(len(self.posts), 1)
        self.assertTrue(all(len(p["attachments"][0]["content"]["body"][2]["text"]) <= 400
                            for p in self.posts))
        self.assertFalse(self.state_file.exists())

    def test_webhook_network_error_does_not_leak_url(self):
        self.environment["TEAMS_WEBHOOK_URL"] = "http://127.0.0.1:1/secret-webhook-marker"
        result = self.invoke("daily")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("secret-webhook-marker", result.stderr)
        self.assertNotIn("fixture-key", result.stderr)
        self.assertNotIn("secret-webhook-marker", (self.root / "logs/redmine_notifier.log").read_text())
        self.assertFalse(self.state_file.exists())


if __name__ == "__main__":
    unittest.main()
