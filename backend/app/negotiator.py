import json
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .agents.diagnostician import diagnose
from .agents.schemas import ClarityReview, Diagnosis
from .agents.strategist import plan
from .database.session import SessionLocal
from .utils.llm_client import call_llm_json


MAX_NEGOTIATION_ROUNDS = 3

STRATEGY_REVIEW_SYSTEM_PROMPT = """
你是大学数学学习系统里的策略审查员。请检查结构化诊断能否直接转为学习计划。
每个薄弱点都必须包含阶段、课程、具体知识点、原因类型和可执行建议。
如果学生没有记录且 needs_first_test=true，应视为信息明确，不要重复要求诊断。
""".strip()


def _fallback_review(diagnosis: Diagnosis) -> ClarityReview:
    if diagnosis.needs_first_test:
        return ClarityReview(clear=True, feedback="学生需要先完成首测，当前诊断已足够明确。")
    missing = []
    if not diagnosis.weak_points:
        missing.append("weak_points")
    for index, point in enumerate(diagnosis.weak_points, start=1):
        for field in ("stage", "course", "knowledge", "reason_type", "suggestion"):
            if not getattr(point, field, None):
                missing.append(f"weak_points[{index}].{field}")
    return ClarityReview(
        clear=not missing,
        missing=missing,
        feedback="诊断字段完整，可以生成学习计划。" if not missing else "请补全缺失字段后重新诊断。",
    )


def _review_diagnosis(diagnosis: Diagnosis, conversation_id: str) -> ClarityReview:
    messages = [
        {"role": "system", "content": STRATEGY_REVIEW_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(diagnosis.model_dump(), ensure_ascii=False, indent=2)},
    ]
    review, _ = call_llm_json(
        messages,
        ClarityReview,
        fallback=_fallback_review(diagnosis),
        conversation_id=conversation_id,
        agent_name="clarity_reviewer",
        temperature=0.1,
        max_tokens=500,
    )
    return review


def _save_log(
    *,
    user_id: int,
    conversation_id: str,
    round_no: int,
    speaker: str,
    message_type: str,
    content: str,
    needs_rediagnosis: bool = False,
) -> bool:
    try:
        with SessionLocal() as db:
            db.execute(
                text(
                    """
                    INSERT INTO negotiation_log (
                      conversation_id, user_id, round_no, speaker, message_type, content, needs_rediagnosis
                    ) VALUES (
                      :conversation_id, :user_id, :round_no, :speaker, :message_type, :content, :needs_rediagnosis
                    )
                    """
                ),
                {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "round_no": round_no,
                    "speaker": speaker,
                    "message_type": message_type,
                    "content": content,
                    "needs_rediagnosis": 1 if needs_rediagnosis else 0,
                },
            )
            db.commit()
    except SQLAlchemyError:
        return False
    return True


def _append_log(
    logs: list[dict[str, Any]],
    *,
    user_id: int,
    conversation_id: str,
    round_no: int,
    speaker: str,
    message_type: str,
    content: str,
    needs_rediagnosis: bool = False,
) -> None:
    saved = _save_log(
        user_id=user_id,
        conversation_id=conversation_id,
        round_no=round_no,
        speaker=speaker,
        message_type=message_type,
        content=content,
        needs_rediagnosis=needs_rediagnosis,
    )
    logs.append(
        {
            "round_no": round_no,
            "speaker": speaker,
            "message_type": message_type,
            "needs_rediagnosis": needs_rediagnosis,
            "saved": saved,
        }
    )


def negotiate_strategy(user_id: int, user_records: Any, max_rounds: int = MAX_NEGOTIATION_ROUNDS) -> dict[str, Any]:
    conversation_id = str(uuid4())
    logs: list[dict[str, Any]] = []
    max_rounds = max(1, min(MAX_NEGOTIATION_ROUNDS, max_rounds))
    diagnosis = diagnose(user_records, conversation_id=conversation_id)
    _append_log(
        logs,
        user_id=user_id,
        conversation_id=conversation_id,
        round_no=1,
        speaker="diagnostician",
        message_type="diagnosis",
        content=diagnosis.model_dump_json(),
    )

    rounds_used = 1
    rediagnosed = False
    final_review = _fallback_review(diagnosis)
    for round_no in range(1, max_rounds + 1):
        rounds_used = round_no
        final_review = _review_diagnosis(diagnosis, conversation_id)
        needs_rediagnosis = not final_review.clear
        _append_log(
            logs,
            user_id=user_id,
            conversation_id=conversation_id,
            round_no=round_no,
            speaker="strategist",
            message_type="clarity_review",
            content=final_review.model_dump_json(),
            needs_rediagnosis=needs_rediagnosis,
        )
        if final_review.clear or round_no >= max_rounds:
            break
        feedback = json.dumps(final_review.model_dump(), ensure_ascii=False)
        diagnosis = diagnose(user_records, conversation_id=conversation_id, feedback=feedback)
        rediagnosed = True
        _append_log(
            logs,
            user_id=user_id,
            conversation_id=conversation_id,
            round_no=round_no + 1,
            speaker="diagnostician",
            message_type="rediagnosis",
            content=diagnosis.model_dump_json(),
        )

    weekly_plan = plan(diagnosis, conversation_id=conversation_id)
    _append_log(
        logs,
        user_id=user_id,
        conversation_id=conversation_id,
        round_no=rounds_used,
        speaker="strategist",
        message_type="final_strategy",
        content=weekly_plan.model_dump_json(),
    )
    return {
        "conversation_id": conversation_id,
        "diagnosis": diagnosis,
        "strategy": weekly_plan,
        "review": final_review,
        "rounds_used": rounds_used,
        "rediagnosed": rediagnosed,
        "log_count": len(logs),
        "saved_log_count": sum(1 for item in logs if item["saved"]),
    }
