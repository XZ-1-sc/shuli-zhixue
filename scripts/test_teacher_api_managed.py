"""Run credential-based teacher API regressions with temporary accounts."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from test_teacher_browser_managed import cleanup_accounts, create_accounts  # noqa: E402


def main() -> None:
    user_ids = create_accounts()
    try:
        import test_question_import_api
        import test_ai_features_api
        import test_teacher_workflow_e2e

        test_teacher_workflow_e2e.main()
        test_question_import_api.main()
        test_ai_features_api.main()
    finally:
        cleanup_accounts(user_ids)


if __name__ == "__main__":
    main()
