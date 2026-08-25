import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from ..utils.llm_client import call_llm_json
from .schemas import Diagnosis, ReasonType, WeakPoint


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "diagnostician.txt"


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def _records_as_list(user_records: Any) -> list[dict[str, Any]]:
    if not isinstance(user_records, list):
        return []
    return [dict(record) for record in user_records if isinstance(record, dict)]


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _reason_type(item: dict[str, Any]) -> ReasonType:
    question_types = set(item["question_types"])
    mistake_text = " ".join(item["mistake_tags"])
    average_time = item["time_spent"] / max(item["total"], 1)
    accuracy = item["correct"] / max(item["graded"], 1)
    if average_time >= 240:
        return "做题慢"
    if "proof" in question_types:
        return "证明思路断点"
    if "概念" in mistake_text:
        return "概念混淆"
    if accuracy <= 0.25 and item["graded"] >= 2:
        return "知识点不会"
    return "计算失误"


def _fallback_diagnosis(user_records: Any) -> Diagnosis:
    records = _records_as_list(user_records)
    graded = [record for record in records if record.get("is_correct") is not None]
    if not graded:
        return Diagnosis(weak_points=[], confidence=0.25 if records else 0.15, needs_first_test=not records)

    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in graded:
        key = (
            str(record.get("stage") or "大一"),
            str(record.get("course") or "高等数学上"),
            str(record.get("knowledge_tag") or record.get("fine_tag") or "基础知识"),
        )
        item = groups.setdefault(
            key,
            {"total": 0, "graded": 0, "correct": 0, "time_spent": 0, "question_types": [], "mistake_tags": []},
        )
        item["total"] += 1
        item["graded"] += 1
        item["correct"] += int(bool(record.get("is_correct")))
        item["time_spent"] += int(record.get("time_spent_seconds") or 0)
        item["question_types"].append(str(record.get("question_type") or ""))
        tags = record.get("mistake_tags") or []
        item["mistake_tags"].extend(tags if isinstance(tags, list) else [str(tags)])

    ranked = sorted(
        groups.items(),
        key=lambda pair: (pair[1]["correct"] / max(pair[1]["graded"], 1), -pair[1]["graded"]),
    )
    weak_points = []
    for (stage, course, knowledge), item in ranked[:3]:
        reason = _reason_type(item)
        weak_points.append(
            WeakPoint(
                stage=stage,
                course=course,
                knowledge=knowledge,
                reason_type=reason,
                suggestion=f"先复习 {knowledge} 的核心定义，再完成 5 道同类题并按“{reason}”复盘。",
            )
        )
    confidence = min(0.92, 0.45 + len(graded) * 0.02)
    return Diagnosis(weak_points=weak_points, confidence=confidence, needs_first_test=False)


def diagnose(
    user_records: Any,
    *,
    conversation_id: str | None = None,
    feedback: str | None = None,
) -> Diagnosis:
    fallback = _fallback_diagnosis(user_records)
    payload = {
        "records": _records_as_list(user_records),
        "previous_review_feedback": feedback or "",
    }
    messages = [
        {"role": "system", "content": _load_prompt()},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default)},
    ]
    result, _ = call_llm_json(
        messages,
        Diagnosis,
        fallback=fallback,
        conversation_id=conversation_id,
        agent_name="diagnostician",
        temperature=0.2,
        max_tokens=900,
    )
    return result
