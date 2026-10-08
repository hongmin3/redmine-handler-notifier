"""Bounded retries; each attempt runs under the same daily/weekly file lock."""
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def run_with_retries(command, delay_seconds=900, timeout_seconds=1800):
    result = 1
    for attempt in range(1, 5):
        print(f"예약 실행 시도 {attempt}/4", flush=True)
        process = subprocess.Popen(command, start_new_session=os.name == "posix")
        try:
            result = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait()
            result = 124
        if result == 0:
            return 0
        print(f"예약 실행 실패: 종료 코드 {result}", flush=True)
        if attempt < 4:
            time.sleep(delay_seconds)
    return result if result > 0 else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("daily", "weekly"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    command = ["/usr/bin/flock", "--nonblock", "--conflict-exit-code", "75",
               str(root / "runtime/notifier.lock"), sys.executable,
               str(root / "redmine_notifier.py"), args.mode]
    return run_with_retries(command)


if __name__ == "__main__":
    sys.exit(main())
