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
你是行测学习系统里的策略规划师，负责先审查诊断专家给出的薄弱点是否足够清晰。

判断标准：
1. 是否说明具体模块和知识点，例如“判断推理-逻辑判断-加强削弱”。
2. 是否说明薄弱原因属于哪一类，例如“知识点不会”“做题慢”“审题错误”“方法选择错误”“计算错误”“粗心”。
3. 是否能直接据此制定一周学习优先级。

如果诊断结果不够清晰，只输出：
NEED_REDIAGNOSIS
问题：...
补充要求：...

如果诊断结果已经清晰，只输出：
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
    if "NEED_REDIAGNOSIS" in normalized:
        return True
    return any(
        keyword in review_text
        for keyword in ("不够清晰", "需要重新诊断", "无法制定", "缺少原因")
    )


def _build_rediagnosis_input(
    user_records: Any,
    previous_diagnosis: str,
    strategist_feedback: str,
) -> str:
    return (
        "策略规划师认为上一版诊断还不够清晰，请重新分析。\n\n"
        f"策略规划师反馈：\n{strategist_feedback}\n\n"
        f"上一版诊断：\n{previous_diagnosis}\n\n"
        "原始做题记录：\n"
        f"{_format_records(user_records)}\n\n"
        "重新输出时，每个薄弱点必须同时说明：模块、具体知识点、薄弱原因类型"
        "（知识点不会/做题慢/审题错误/方法选择错误/计算错误/粗心）。"
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
          conversation_id,
          user_id,
          round_no,
          speaker,
          message_type,
          content,
          needs_rediagnosis
        )
        VALUES (
          :conversation_id,
          :user_id,
          :round_no,
          :speaker,
          :message_type,
          :content,
          :needs_rediagnosis
        )
        """
    )
    params = {
        "conversation_id": conversation_id,
        "user_id": user_id,
        "round_no": round_no,
        "speaker": speaker,
        "message_type": message_type,
        "content": content,
        "needs_rediagnosis": 1 if needs_rediagnosis else 0,
    }

    try:
        with SessionLocal() as db:
            db.execute(query, params)
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


def negotiate_strategy(
    user_id: int,
    user_records: Any,
    max_rounds: int = MAX_NEGOTIATION_ROUNDS,
) -> dict[str, Any]:
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
            _append_log(
                logs,
                user_id=user_id,
                conversation_id=conversation_id,
                round_no=round_no,
                speaker="orchestrator",
                message_type="max_rounds_reached",
                content="已达到最多3轮协商，使用当前诊断结果继续生成策略。",
            )
            break

        rediagnosis_input = _build_rediagnosis_input(
            user_records=user_records,
            previous_diagnosis=diagnosis_text,
            strategist_feedback=review_text,
        )
        _append_log(
            logs,
            user_id=user_id,
            conversation_id=conversation_id,
            round_no=round_no,
            speaker="orchestrator",
            message_type="rediagnosis_request",
            content=rediagnosis_input,
            needs_rediagnosis=True,
        )

        diagnosis_text = diagnose(rediagnosis_input)
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
