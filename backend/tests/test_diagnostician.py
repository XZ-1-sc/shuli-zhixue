import json
import unittest
from decimal import Decimal
from unittest.mock import patch

from backend.app.agents.diagnostician import diagnose
from backend.app.agents.schemas import Diagnosis


class DiagnosticianTests(unittest.TestCase):
    def test_decimal_scores_are_serialized_for_the_llm_payload(self) -> None:
        result = Diagnosis(weak_points=[], confidence=0.8, needs_first_test=False)
        records = [
            {
                "question_id": 17,
                "stage": "大一",
                "course": "高等数学上",
                "knowledge_tag": "极限与连续",
                "fine_tag": "函数极限",
                "question_type": "choice",
                "is_correct": 0,
                "score": Decimal("0.00"),
                "mistake_tags": ["概念混淆"],
                "time_spent_seconds": 95,
            }
        ]

        with patch(
            "backend.app.agents.diagnostician.call_llm_json",
            return_value=(result, {"source": "test"}),
        ) as mocked_call:
            actual = diagnose(records)

        payload = json.loads(mocked_call.call_args.args[0][1]["content"])
        self.assertEqual(payload["records"][0]["score"], 0.0)
        self.assertEqual(actual, result)


if __name__ == "__main__":
    unittest.main()
