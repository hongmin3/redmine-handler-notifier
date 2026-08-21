import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from redmine_notifier import daily_since, notifications_enabled, save_json, split_blocks, status_rank, weekly_groups


class RedmineNotifierTests(unittest.TestCase):
    def test_notifications_default_to_off(self):
        with TemporaryDirectory() as directory:
            self.assertFalse(notifications_enabled(Path(directory) / "missing.json"))

    def test_control_file_can_enable_notifications(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "control.json"
            save_json(path, {"enabled": True})
            self.assertTrue(notifications_enabled(path))

    def test_daily_since_uses_previous_success_with_overlap(self):
        now = datetime(2026, 8, 21, 1, 0, tzinfo=timezone.utc)
        previous = now - timedelta(hours=2)
        result = daily_since(now, {"daily_last_success_utc": previous.isoformat()}, None)
        self.assertEqual(result, previous - timedelta(minutes=5))

    def test_split_blocks_respects_limit(self):
        self.assertEqual(split_blocks(["a" * 8, "b" * 8], 10), ["a" * 8, "b" * 8])

    def test_unassigned_stale_issue_is_preserved(self):
        now = datetime(2026, 8, 21, tzinfo=timezone.utc)
        issue = {
            "id": 1,
            "subject": "Example",
            "status": {"name": "신규"},
            "custom_fields": [{"name": "Grade", "value": "A"}],
            "updated_on": (now - timedelta(days=31)).isoformat(),
        }
        groups = weekly_groups([issue], {"D"}, now)
        self.assertEqual(groups["미지정"][0]["stale_days"], 31)

    def test_status_priority(self):
        self.assertLess(status_rank("신규"), status_rank("보류"))


if __name__ == "__main__":
    unittest.main()
