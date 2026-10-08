"""Write the new URL from stdin to a private systemd environment file, never .env."""
import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path,
                        default=Path(__file__).resolve().parents[1] / "runtime/teams-webhook.env")
    args = parser.parse_args()
    value = sys.stdin.read().strip()
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or any(char.isspace() or char in '\\"' for char in value)):
        parser.error("HTTPS Webhook URL 한 개를 표준 입력으로 전달하세요.")
    args.file.parent.mkdir(parents=True, exist_ok=True)
    if args.file.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        backup = args.file.with_name(args.file.name + "." + stamp + ".bak")
        shutil.copyfile(args.file, backup)
        backup.chmod(0o600)
    temporary = args.file.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(f'TEAMS_WEBHOOK_URL="{value}"\n')
    temporary.chmod(0o600)
    temporary.replace(args.file)
    print("서버 Webhook 보호 설정 저장 완료. URL은 출력하지 않습니다.")


if __name__ == "__main__":
    main()
