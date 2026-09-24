"""Scan all active teachers for auditable teaching-risk signals.

Schedule this command once daily in the deployment environment.  The unique
fingerprints make each scan idempotent and prevent duplicate notifications.
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.risk_service import scan_all_teachers_sync  # noqa: E402


if __name__ == "__main__":
    print(scan_all_teachers_sync())
