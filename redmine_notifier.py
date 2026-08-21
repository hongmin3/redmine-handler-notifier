from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


APP_DIR = Path(__file__).resolve().parent
KST = timezone(timedelta(hours=9))
DEFAULT_STATE_FILE = APP_DIR / "runtime" / "state.json"
DEFAULT_CONTROL_FILE = APP_DIR / "runtime" / "notification_control.json"
DEFAULT_LOG_FILE = APP_DIR / "logs" / "redmine_notifier.log"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    return int(raw) if raw else default


def configure_logging() -> logging.Logger:
    log_path = Path(os.getenv("REDMINE_LOG_FILE", str(DEFAULT_LOG_FILE)))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("redmine_notifier")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    rotating = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    rotating.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(rotating)
    return logger


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def notifications_enabled(control_path: Path) -> bool:
    override = os.getenv("NOTIFICATIONS_ENABLED", "").strip().lower()
    if override:
        return override in {"1", "true", "yes", "on"}
    return bool(load_json(control_path).get("enabled", False))


def parse_redmine_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_kst_date(value: str) -> str:
    parsed = parse_redmine_datetime(value)
    return parsed.astimezone(KST).strftime("%Y-%m-%d") if parsed else "알 수 없음"


def issue_grade(issue: dict[str, Any]) -> str:
    for field in issue.get("custom_fields", []):
        if str(field.get("name", "")).strip().lower() in {"grade", "등급", "severity"}:
            return str(field.get("value", "")).strip() or "N/A"
    return "N/A"


def issue_assignee(issue: dict[str, Any]) -> str:
    return str(issue.get("assigned_to", {}).get("name") or "미지정")


def issue_status(issue: dict[str, Any]) -> str:
    return str(issue.get("status", {}).get("name") or "알 수 없음")


def status_rank(name: str) -> int:
    return {"신규": 0, "재오픈": 1, "수정완료": 2, "진행": 3, "보류": 9}.get(name, 5)


def build_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class RedmineClient:
    def __init__(self, base_url: str, project_id: str, api_key: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.project_id = project_id
        self.timeout = timeout
        self.session = build_session()
        self.session.headers.update({"X-Redmine-API-Key": api_key, "Accept": "application/json"})

    @property
    def issues_url(self) -> str:
        return f"{self.base_url}/projects/{self.project_id}/issues.json"

    def fetch_open_issues(self, updated_since: datetime | None = None) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        offset = 0
        while True:
            params: dict[str, Any] = {"status_id": "open", "limit": 100, "offset": offset}
            if updated_since:
                params["updated_on"] = ">=" + updated_since.strftime("%Y-%m-%dT%H:%M:%SZ")
            response = self.session.get(self.issues_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("issues", [])
            issues.extend(batch)
            total_count = int(payload.get("total_count", len(issues)))
            if not batch or len(issues) >= total_count:
                return issues
            offset += len(batch)


def daily_since(now_utc: datetime, state: dict[str, Any], override_hours: int | None) -> datetime:
    if override_hours:
        return now_utc - timedelta(hours=override_hours)
    previous = parse_redmine_datetime(str(state.get("daily_last_success_utc", "")))
    if previous:
        return max(previous - timedelta(minutes=5), now_utc - timedelta(days=7))
    return now_utc - timedelta(hours=72 if now_utc.astimezone(KST).weekday() == 0 else 24)


def filter_seen_daily(issues: Iterable[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    seen = set(state.get("daily_seen", []))
    return [issue for issue in issues if f"{issue.get('id')}:{issue.get('updated_on', '')}" not in seen]


def daily_issue_blocks(issues: list[dict[str, Any]], base_url: str) -> list[str]:
    ordered = sorted(
        issues,
        key=lambda issue: (status_rank(issue_status(issue)), issue_status(issue), -int(issue.get("id", 0))),
    )
    blocks = []
    for issue in ordered:
        issue_id = issue.get("id", "")
        blocks.append("\n".join([
            f"**[#{issue_id} {issue.get('subject', '제목 없음')}]({base_url}/issues/{issue_id})**",
            f"- 상태: **{issue_status(issue)}**",
            f"- Handler: **{issue_assignee(issue)}**",
            f"- Grade: **{issue_grade(issue)}**",
            f"- 최종 업데이트: {format_kst_date(str(issue.get('updated_on', '')))}",
        ]))
    return blocks


def weekly_groups(
    issues: Iterable[dict[str, Any]], excluded_grades: set[str], now_utc: datetime
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in issues:
        if issue_grade(issue).upper() in excluded_grades:
            continue
        updated = parse_redmine_datetime(str(issue.get("updated_on", "")))
        stale_days = max(0, (now_utc - updated).days) if updated else 9999
        groups[issue_assignee(issue)].append({
            "id": issue.get("id", ""),
            "subject": issue.get("subject", "제목 없음"),
            "status": issue_status(issue),
            "grade": issue_grade(issue),
            "updated_on": issue.get("updated_on", ""),
            "stale_days": stale_days,
        })
    for assignee in groups:
        groups[assignee].sort(key=lambda item: (
            item["status"] == "보류", -item["stale_days"], status_rank(item["status"]), -int(item["id"] or 0)
        ))
    return dict(groups)


def weekly_issue_blocks(groups: dict[str, list[dict[str, Any]]], base_url: str) -> list[str]:
    blocks: list[str] = []
    for assignee in sorted(groups, key=lambda name: (name != "미지정", name)):
        issues = groups[assignee]
        lines = [f"### {'⚠️' if assignee == '미지정' else '👤'} **{assignee}** ({len(issues)}건)"]
        for issue in issues:
            stale = issue["stale_days"]
            badge = " 🔴 30일+" if stale >= 30 else " 🟠 14일+" if stale >= 14 else ""
            lines.append(
                f"- **[[#{issue['id']}] {issue['subject']}]({base_url}/issues/{issue['id']})**{badge}\n"
                f"  - 업데이트: {format_kst_date(str(issue['updated_on']))} | 상태: {issue['status']} | Grade: {issue['grade']}"
            )
        blocks.append("\n".join(lines))
    return blocks


def split_blocks(blocks: list[str], max_chars: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    separator = "\n\n---\n\n"
    for block in blocks:
        block = block[:max_chars]
        projected = size + len(block) + (len(separator) if current else 0)
        if current and projected > max_chars:
            chunks.append(separator.join(current))
            current, size = [], 0
        current.append(block)
        size += len(block) + (len(separator) if len(current) > 1 else 0)
    if current:
        chunks.append(separator.join(current))
    return chunks


def teams_payload(title: str, summary: str, content: str, page: int, total: int) -> dict[str, Any]:
    suffix = f" ({page}/{total})" if total > 1 else ""
    return {"type": "message", "attachments": [{
        "contentType": "application/vnd.microsoft.card.adaptive",
        "contentUrl": None,
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard", "version": "1.2",
            "body": [
                {"type": "TextBlock", "text": title + suffix, "weight": "Bolder", "size": "Medium", "wrap": True},
                {"type": "TextBlock", "text": summary, "wrap": True},
                {"type": "TextBlock", "text": content, "wrap": True},
            ],
        },
    }]}


def send_payloads(webhook_url: str, payloads: list[dict[str, Any]], timeout: int) -> None:
    for payload in payloads:
        response = requests.post(webhook_url, json=payload, timeout=timeout)
        if response.status_code not in {200, 202}:
            raise RuntimeError(f"Teams webhook failed with HTTP {response.status_code}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Redmine Handler-centered Teams notifier")
    parser.add_argument("mode", choices=("daily", "weekly"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--lookback-hours", type=int, default=None)
    parser.add_argument("--preview-file", type=Path, default=None)
    return parser


def run(args: argparse.Namespace, logger: logging.Logger) -> int:
    load_dotenv(APP_DIR / ".env")
    control_path = Path(os.getenv("NOTIFICATION_CONTROL_FILE", str(DEFAULT_CONTROL_FILE)))
    if not notifications_enabled(control_path):
        logger.info("Notifications are OFF. Redmine lookup and Teams delivery skipped.")
        return 0

    base_url = require_env("REDMINE_BASE_URL").rstrip("/")
    project_id = require_env("REDMINE_PROJECT_ID")
    api_key = require_env("REDMINE_API_KEY")
    webhook_url = os.getenv("TEAMS_WEBHOOK_URL", "").strip()
    timeout = env_int("HTTP_TIMEOUT_SECONDS", 30)
    max_chars = env_int("TEAMS_MAX_CHARS", 16000)
    state_path = Path(os.getenv("REDMINE_STATE_FILE", str(DEFAULT_STATE_FILE)))
    state = load_json(state_path)
    now_utc = datetime.now(timezone.utc)
    client = RedmineClient(base_url, project_id, api_key, timeout)
    payloads: list[dict[str, Any]] = []
    processed: list[dict[str, Any]] = []

    if args.mode == "daily":
        since = daily_since(now_utc, state, args.lookback_hours)
        fetched = client.fetch_open_issues(updated_since=since)
        processed = filter_seen_daily(fetched, state)
        logger.info("Daily scan fetched=%d new=%d since=%s", len(fetched), len(processed), since.isoformat())
        if processed:
            statuses = Counter(issue_status(issue) for issue in processed)
            summary = " | ".join(f"{name} {count}건" for name, count in sorted(statuses.items()))
            chunks = split_blocks(daily_issue_blocks(processed, base_url), max_chars)
            payloads = [teams_payload("🚨 최근 Redmine 업데이트", summary, chunk, i, len(chunks)) for i, chunk in enumerate(chunks, 1)]
    else:
        fetched = client.fetch_open_issues()
        excluded = {value.strip().upper() for value in os.getenv("REDMINE_EXCLUDED_GRADES", "D").split(",") if value.strip()}
        groups = weekly_groups(fetched, excluded, now_utc)
        total = sum(len(items) for items in groups.values())
        unassigned = len(groups.get("미지정", []))
        stale_30 = sum(1 for items in groups.values() for item in items if item["stale_days"] >= 30)
        logger.info("Weekly scan fetched=%d included=%d handlers=%d unassigned=%d stale30=%d", len(fetched), total, len(groups), unassigned, stale_30)
        if total:
            summary = f"전체 {total}건 | Handler {len(groups)}명 | 미지정 {unassigned}건 | 30일 이상 {stale_30}건"
            chunks = split_blocks(weekly_issue_blocks(groups, base_url), max_chars)
            payloads = [teams_payload("📢 Handler별 Open 이슈 리마인드", summary, chunk, i, len(chunks)) for i, chunk in enumerate(chunks, 1)]

    if args.preview_file:
        args.preview_file.parent.mkdir(parents=True, exist_ok=True)
        args.preview_file.write_text(json.dumps(payloads, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Preview saved: %s", args.preview_file)
    if args.dry_run:
        logger.info("Dry-run complete. messages=%d", len(payloads))
        return 0
    if payloads:
        if not webhook_url:
            raise RuntimeError("Required environment variable is missing: TEAMS_WEBHOOK_URL")
        send_payloads(webhook_url, payloads, timeout)
        logger.info("Teams delivery complete. messages=%d", len(payloads))
    else:
        logger.info("No matching issues. Notification skipped.")

    if args.mode == "daily":
        seen = list(state.get("daily_seen", []))
        seen.extend(f"{issue.get('id')}:{issue.get('updated_on', '')}" for issue in processed)
        state["daily_seen"] = seen[-3000:]
        state["daily_last_success_utc"] = now_utc.isoformat()
        save_json(state_path, state)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logger = configure_logging()
    try:
        return run(args, logger)
    except Exception as exc:
        logger.exception("Notifier failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
