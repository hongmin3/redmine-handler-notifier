"""Backward-compatible entry point for the weekly notification."""
from redmine_notifier import main

if __name__ == "__main__":
    raise SystemExit(main(["weekly"]))
