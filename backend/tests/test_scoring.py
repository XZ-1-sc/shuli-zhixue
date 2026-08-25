import unittest

from backend.app.services.scoring import _normalize_math_answer, _score_subjective


class SubjectiveScoringTests(unittest.TestCase):
    def test_normalizes_equivalent_math_symbols(self) -> None:
        self.assertEqual(_normalize_math_answer("答案：π × 2"), "pi*2")

    def test_exact_blank_answer_scores_full_marks(self) -> None:
        correct, score = _score_subjective(
            "π/2",
            {"standard_answer": "π / 2", "key_steps": [], "knowledge_tag": "定积分", "fine_tag": "积分计算"},
            "blank",
        )
        self.assertTrue(correct)
        self.assertEqual(score, 100.0)

    def test_empty_subjective_answer_is_not_graded_correct(self) -> None:
        self.assertEqual(_score_subjective("", {"standard_answer": "1"}, "calculation"), (False, 0.0))


if __name__ == "__main__":
    unittest.main()
