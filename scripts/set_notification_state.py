"""Cross-platform control command; preserves the Windows command's control format."""
import argparse
import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from redmine_notifier import DEFAULT_CONTROL_FILE, load_json, save_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("state", choices=("on", "off", "status"))
    parser.add_argument("--control-file", type=Path, default=DEFAULT_CONTROL_FILE)
    args = parser.parse_args()
    if args.state != "status":
        save_json(args.control_file, {"enabled": args.state == "on",
                                     "changed_at": datetime.now(timezone.utc).isoformat(),
                                     "changed_by": getpass.getuser()})
    print("ON" if load_json(args.control_file).get("enabled", False) else "OFF")


if __name__ == "__main__":
    main()
