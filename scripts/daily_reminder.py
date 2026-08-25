"""Generate idempotent Xiaoluo care reminders for an external daily scheduler."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.reminder_service import run_daily_reminders_sync  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily Xiaoluo notifications once per type and user.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect candidates without writing notifications.")
    args = parser.parse_args()
    result = run_daily_reminders_sync(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
