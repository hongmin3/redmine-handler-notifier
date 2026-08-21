"""Backward-compatible entry point for the daily notification."""
from redmine_notifier import main

if __name__ == "__main__":
    raise SystemExit(main(["daily"]))
