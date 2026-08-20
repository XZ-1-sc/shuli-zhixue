import os
from unittest.mock import MagicMock, patch

from backend.app.agents.schemas import ClarityReview, Diagnosis, WeakPoint, WeeklyPlan
from backend.app.negotiator import negotiate_strategy
from backend.app.utils import llm_client


def _diagnosis(knowledge: str = "极限") -> Diagnosis:
    return Diagnosis(
        weak_points=[
            WeakPoint(
                stage="大一",
                course="高等数学上",
                knowledge=knowledge,
                reason_type="概念混淆",
                suggestion="复习定义后完成五道基础题。",
            )
        ],
        confidence=0.8,
    )


def _plan() -> WeeklyPlan:
    return WeeklyPlan(
        focus_course="高等数学上",
        focus_knowledge="极限",
        daily_hours=1.5,
        priority_order=["极限", "导数"],
        give_up_types=["高难综合题"],
    )


def test_invalid_json_falls_back_after_one_retry() -> None:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "model": "mock-model",
        "choices": [{"message": {"content": "not-json"}}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
    }
    fallback = _diagnosis()
    with (
        patch.dict(os.environ, {"LLM_API_KEY": "test-key"}),
        patch.object(llm_client.requests, "post", side_effect=[response, response]) as post,
        patch.object(llm_client, "_record_call"),
    ):
        result, usage = llm_client.call_llm_json(
            [{"role": "user", "content": "test"}],
            Diagnosis,
            fallback=fallback,
            retries=1,
        )
    assert result == fallback
    assert usage.status == "fallback_invalid_json"
    assert post.call_count == 2


def test_rediagnosis_stops_when_review_becomes_clear() -> None:
    with (
        patch("backend.app.negotiator.diagnose", side_effect=[_diagnosis("极限"), _diagnosis("导数")]) as diagnose,
        patch(
            "backend.app.negotiator._review_diagnosis",
            side_effect=[
                ClarityReview(clear=False, missing=["knowledge"], feedback="知识点不够具体"),
                ClarityReview(clear=True, feedback="字段完整"),
            ],
        ),
        patch("backend.app.negotiator.plan", return_value=_plan()),
        patch("backend.app.negotiator._save_log", return_value=True),
    ):
        result = negotiate_strategy(1, [], max_rounds=3)
    assert result["rediagnosed"] is True
    assert result["rounds_used"] == 2
    assert diagnose.call_count == 2


def test_negotiation_never_exceeds_three_rounds() -> None:
    unclear = ClarityReview(clear=False, missing=["knowledge"], feedback="仍需补充")
    with (
        patch("backend.app.negotiator.diagnose", side_effect=[_diagnosis("极限"), _diagnosis("导数"), _diagnosis("积分")]) as diagnose,
        patch("backend.app.negotiator._review_diagnosis", return_value=unclear) as review,
        patch("backend.app.negotiator.plan", return_value=_plan()),
        patch("backend.app.negotiator._save_log", return_value=True),
    ):
        result = negotiate_strategy(1, [], max_rounds=99)
    assert result["rounds_used"] == 3
    assert review.call_count == 3
    assert diagnose.call_count == 3


def main() -> None:
    test_invalid_json_falls_back_after_one_retry()
    test_rediagnosis_stops_when_review_becomes_clear()
    test_negotiation_never_exceeds_three_rounds()
    print("STRUCTURED_AGENTS_OK")


if __name__ == "__main__":
    main()
