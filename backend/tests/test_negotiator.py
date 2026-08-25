import unittest
from unittest.mock import patch

from backend.app.agents.schemas import ClarityReview, Diagnosis, WeeklyPlan
from backend.app.negotiator import negotiate_strategy


class NegotiatorTests(unittest.TestCase):
    def test_clear_diagnosis_runs_one_round_and_builds_plan(self) -> None:
        diagnosis = Diagnosis(weak_points=[], confidence=0.8, needs_first_test=True)
        strategy = WeeklyPlan(
            focus_course="高等数学上",
            focus_knowledge="极限",
            daily_hours=1,
            priority_order=["完成首测"],
            give_up_types=[],
        )
        with (
            patch("backend.app.negotiator.diagnose", return_value=diagnosis),
            patch("backend.app.negotiator._review_diagnosis", return_value=ClarityReview(clear=True, feedback="信息完整")),
            patch("backend.app.negotiator.plan", return_value=strategy),
            patch("backend.app.negotiator._save_log", return_value=True),
        ):
            result = negotiate_strategy(7, [], max_rounds=3)
        self.assertEqual(result["rounds_used"], 1)
        self.assertFalse(result["rediagnosed"])
        self.assertEqual(result["saved_log_count"], 3)
        self.assertEqual(result["strategy"].focus_knowledge, "极限")


if __name__ == "__main__":
    unittest.main()
