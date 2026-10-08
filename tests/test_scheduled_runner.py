"""The scheduler must stop after four real failed invocations, including timeouts."""
import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class ScheduledRunnerTests(unittest.TestCase):
    # Validates: REQ-OPS-001
    def test_four_failures_stop_retrying(self):
        path = Path(__file__).resolve().parents[1] / "scripts/run_scheduled.py"
        self.assertTrue(path.exists(), "bounded scheduler runner is missing")
        spec = importlib.util.spec_from_file_location("scheduled_runner", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with TemporaryDirectory() as directory:
            count = Path(directory) / "attempts.txt"
            command = [sys.executable, "-c",
                       "import sys;from pathlib import Path;p=Path(sys.argv[1]);"
                       "p.write_text(p.read_text()+'x' if p.exists() else 'x');sys.exit(75)", str(count)]
            result = module.run_with_retries(command, delay_seconds=0, timeout_seconds=2)
            self.assertEqual(result, 75)
            self.assertEqual(count.read_text(), "xxxx")

    def test_success_stops_retrying(self):
        path = Path(__file__).resolve().parents[1] / "scripts/run_scheduled.py"
        self.assertTrue(path.exists(), "bounded scheduler runner is missing")
        spec = importlib.util.spec_from_file_location("scheduled_runner", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with TemporaryDirectory() as directory:
            count = Path(directory) / "attempts.txt"
            command = [sys.executable, "-c",
                       "import sys;from pathlib import Path;p=Path(sys.argv[1]);"
                       "s=p.read_text() if p.exists() else '';p.write_text(s+'x');"
                       "sys.exit(0 if len(s)==1 else 1)", str(count)]
            result = module.run_with_retries(command, delay_seconds=0, timeout_seconds=2)
            self.assertEqual(result, 0)
            self.assertEqual(count.read_text(), "xx")

    def test_four_timeouts_stop_retrying(self):
        path = Path(__file__).resolve().parents[1] / "scripts/run_scheduled.py"
        self.assertTrue(path.exists(), "bounded scheduler runner is missing")
        spec = importlib.util.spec_from_file_location("scheduled_runner", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with TemporaryDirectory() as directory:
            count = Path(directory) / "attempts.txt"
            command = [sys.executable, "-c",
                       "import sys,time;from pathlib import Path;p=Path(sys.argv[1]);"
                       "p.write_text(p.read_text()+'x' if p.exists() else 'x');time.sleep(10)", str(count)]
            result = module.run_with_retries(command, delay_seconds=0, timeout_seconds=2)
            self.assertEqual(result, 124)
            self.assertEqual(count.read_text(), "xxxx")
