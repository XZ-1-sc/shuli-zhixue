import json
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .agents.diagnostician import diagnose
from .agents.strategist import plan
from .database.session import SessionLocal
from .utils.llm_client import call_llm


MAX_NEGOTIATION_ROUNDS = 3

STRATEGY_REVIEW_SYSTEM_PROMPT = """
你是大学数学学习系统里的策略审查员。
你需要判断诊断体给出的薄弱点是否足够清晰，能否直接转成一周学习计划。
合格标准：
1. 说明阶段，例如大一/大二/大三/大四。
2. 说明课程，例如高等数学上、线性代数上、概率论与数理统计。
3. 说明具体知识点。
4. 说明薄弱原因，例如概念混淆、计算失误、证明思路断点、做题慢。

如果不够清晰，只输出：
NEED_REDIAGNOSIS
问题：...
补充要求：...

如果足够清晰，只输出：
CLEAR
理由：...
""".strip()


def _format_records(user_records: Any) -> str:
    if isinstance(user_records, str):
        return user_records.strip()
    if not user_records:
        return "暂无做题记录。"
    try:
        return json.dumps(user_records, ensure_ascii=False, indent=2)
    except TypeError:
        return str(user_records)


def _review_diagnosis_with_strategist(diagnosis_text: str) -> str:
    messages = [
        {"role": "system", "content": STRATEGY_REVIEW_SYSTEM_PROMPT},
        {"role": "user", "content": f"请审查以下诊断结果：\n{diagnosis_text}"},
    ]
    return call_llm(messages, temperature=0.2, max_tokens=512)


def _needs_rediagnosis(review_text: str) -> bool:
    normalized = review_text.upper()
    return "NEED_REDIAGNOSIS" in normalized


def _build_rediagnosis_input(user_records: Any, previous_diagnosis: str, strategist_feedback: str) -> str:
    return (
        "策略审查员认为上一版诊断不够清晰，请重新分析。\n\n"
        f"审查反馈：\n{strategist_feedback}\n\n"
        f"上一版诊断：\n{previous_diagnosis}\n\n"
        f"原始做题记录：\n{_format_records(user_records)}\n\n"
        "重新输出时，每个薄弱点必须同时说明阶段、课程、知识点和薄弱原因。"
    )


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
    query = text(
        """
        INSERT INTO negotiation_log (
          conversation_id, user_id, round_no, speaker, message_type, content, needs_rediagnosis
        )
        VALUES (
          :conversation_id, :user_id, :round_no, :speaker, :message_type, :content, :needs_rediagnosis
        )
        """
    )
    try:
        with SessionLocal() as db:
            db.execute(
                query,
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
            "content": content,
            "needs_rediagnosis": needs_rediagnosis,
            "saved": saved,
        }
    )


def negotiate_strategy(user_id: int, user_records: Any, max_rounds: int = MAX_NEGOTIATION_ROUNDS) -> dict[str, Any]:
    conversation_id = str(uuid4())
    logs: list[dict[str, Any]] = []
    diagnosis_text = diagnose(user_records)
    _append_log(
        logs,
        user_id=user_id,
        conversation_id=conversation_id,
        round_no=1,
        speaker="diagnostician",
        message_type="diagnosis",
        content=diagnosis_text,
    )

    rounds_used = 1
    for round_no in range(1, max_rounds + 1):
        rounds_used = round_no
        review_text = _review_diagnosis_with_strategist(diagnosis_text)
        needs_rediagnosis = _needs_rediagnosis(review_text)
        _append_log(
            logs,
            user_id=user_id,
            conversation_id=conversation_id,
            round_no=round_no,
            speaker="strategist",
            message_type="clarity_review",
            content=review_text,
            needs_rediagnosis=needs_rediagnosis,
        )
        if not needs_rediagnosis:
            break
        if round_no >= max_rounds:
            break
        diagnosis_text = diagnose(_build_rediagnosis_input(user_records, diagnosis_text, review_text))
        _append_log(
            logs,
            user_id=user_id,
            conversation_id=conversation_id,
            round_no=round_no + 1,
            speaker="diagnostician",
            message_type="rediagnosis",
            content=diagnosis_text,
        )

    strategy_text = plan(diagnosis_text)
    _append_log(
        logs,
        user_id=user_id,
        conversation_id=conversation_id,
        round_no=rounds_used,
        speaker="strategist",
        message_type="final_strategy",
        content=strategy_text,
    )
    return {
        "conversation_id": conversation_id,
        "diagnosis": diagnosis_text,
        "strategy": strategy_text,
        "rounds_used": rounds_used,
        "log_count": len(logs),
        "saved_log_count": sum(1 for item in logs if item["saved"]),
    }
