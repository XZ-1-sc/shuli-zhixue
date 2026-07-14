import asyncio
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .agents.navigator import recommend
from .database.session import SessionLocal
from .negotiator import negotiate_strategy


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _row_to_record(row: Any) -> dict[str, Any]:
    return {
        key: _json_safe(value)
        for key, value in dict(row._mapping).items()
    }


def _fetch_recent_records(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    query = text(
        """
        SELECT
          pr.id AS record_id,
          pr.task_id,
          pr.question_id,
          q.module,
          q.knowledge_tag,
          q.difficulty,
          pr.selected_answer,
          q.correct_answer,
          pr.is_correct,
          pr.time_spent_seconds,
          pr.practice_mode,
          pr.answered_at
        FROM practice_records AS pr
        LEFT JOIN questions AS q ON q.id = pr.question_id
        WHERE pr.user_id = :user_id
        ORDER BY pr.answered_at DESC, pr.id DESC
        LIMIT :limit
        """
    )

    try:
        with SessionLocal() as db:
            rows = db.execute(query, {"user_id": user_id, "limit": limit}).fetchall()
    except SQLAlchemyError:
        return []

    return [_row_to_record(row) for row in rows]


async def run_pipeline(user_id: int) -> dict[str, Any]:
    user_records = await asyncio.to_thread(_fetch_recent_records, user_id)
    negotiation = await asyncio.to_thread(negotiate_strategy, user_id, user_records)
    strategy_text = negotiation["strategy"]
    recommended_questions = await asyncio.to_thread(recommend, strategy_text)
    recommended_question_ids = [
        int(question["id"])
        for question in recommended_questions
        if question.get("id") is not None
    ]

    return {
        "user_id": user_id,
        "recent_record_count": len(user_records),
        "diagnosis": negotiation["diagnosis"],
        "strategy": strategy_text,
        "recommended_question_ids": recommended_question_ids,
        "negotiation": {
            "conversation_id": negotiation["conversation_id"],
            "rounds_used": negotiation["rounds_used"],
            "log_count": negotiation["log_count"],
            "saved_log_count": negotiation["saved_log_count"],
        },
    }
