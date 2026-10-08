import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class ServerWebhookTests(unittest.TestCase):
    def setUp(self):
        self.environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    # Validates: NFR-SECURITY-001
    def test_stdin_url_is_saved_without_stdout_disclosure(self):
        script = Path(__file__).resolve().parents[1] / "scripts/set_server_webhook.py"
        self.assertTrue(script.exists(), "protected webhook setup command is missing")
        with TemporaryDirectory() as directory:
            output = Path(directory) / "teams-webhook.env"
            value = "https://fixture.api.powerplatform.com/invoke?sig=fixture-secret&sv=1"
            result = subprocess.run([sys.executable, str(script), "--file", str(output)],
                                    input=value + "\n", text=True, encoding="utf-8", capture_output=True,
                                    env=self.environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_text(), f'TEAMS_WEBHOOK_URL="{value}"\n')
            self.assertNotIn(value, result.stdout + result.stderr)
            if os.name == "posix":
                self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_invalid_url_does_not_replace_existing_setting(self):
        script = Path(__file__).resolve().parents[1] / "scripts/set_server_webhook.py"
        self.assertTrue(script.exists(), "protected webhook setup command is missing")
        with TemporaryDirectory() as directory:
            output = Path(directory) / "teams-webhook.env"
            output.write_text("existing-value")
            for value in ("http://fixture/invoke", "https://fixture/invoke\nOTHER=value"):
                result = subprocess.run([sys.executable, str(script), "--file", str(output)],
                                        input=value, text=True, encoding="utf-8", capture_output=True,
                                        env=self.environment)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output.read_text(), "existing-value")
