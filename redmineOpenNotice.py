"""Deprecated entry point. Use redmine_notifier.py daily."""
from redmine_notifier import main

if __name__ == "__main__":
    raise SystemExit(main(["daily"]))
