import asyncio
import time
from typing import Any

from .agents.navigator import recommend
from .database.repositories.diagnosis import _recent_records_sync
from .negotiator import negotiate_strategy


async def run_pipeline(user_id: int, *, recommendation_limit: int = 10) -> dict[str, Any]:
    started = time.perf_counter()
    user_records = await asyncio.to_thread(_recent_records_sync, user_id, 50)
    negotiation = await asyncio.to_thread(negotiate_strategy, user_id, user_records)
    diagnosis = negotiation["diagnosis"]
    weekly_plan = negotiation["strategy"]
    recommended_questions = await asyncio.to_thread(
        recommend,
        weekly_plan,
        recommendation_limit,
        conversation_id=negotiation["conversation_id"],
    )
    duration_ms = max(0, round((time.perf_counter() - started) * 1000))
    return {
        "user_id": user_id,
        "recent_record_count": len(user_records),
        "diagnosis": diagnosis.model_dump(),
        "strategy": weekly_plan.model_dump(),
        "recommended_question_ids": [int(item["id"]) for item in recommended_questions if item.get("id")],
        "recommended_questions": recommended_questions,
        "negotiation": {
            "conversation_id": negotiation["conversation_id"],
            "rounds_used": negotiation["rounds_used"],
            "rediagnosed": negotiation["rediagnosed"],
            "needs_rediagnosis": not negotiation["review"].clear,
            "log_count": negotiation["log_count"],
            "saved_log_count": negotiation["saved_log_count"],
            "duration_ms": duration_ms,
        },
    }
