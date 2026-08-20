from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..database.session import SessionLocal
from .schemas import EvaluationResult


def _accuracy(correct: int, total: int) -> float:
    return 0.0 if total <= 0 else correct / total


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    return default if row is None else row._mapping.get(key, default)


def evaluate(user_id: int, task_id: str | int) -> EvaluationResult:
    try:
        with SessionLocal() as db:
            current_row = db.execute(
                text(
                    """
                    SELECT COUNT(*) AS total, COALESCE(SUM(is_correct), 0) AS correct, MIN(answered_at) AS started_at
                    FROM practice_records
                    WHERE user_id=:user_id AND task_id=:task_id AND is_correct IS NOT NULL
                    """
                ),
                {"user_id": user_id, "task_id": str(task_id)},
            ).one()
            current_total = int(_row_value(current_row, "total", 0) or 0)
            current_correct = int(_row_value(current_row, "correct", 0) or 0)
            started_at = _row_value(current_row, "started_at")
            history_row = db.execute(
                text(
                    """
                    SELECT COUNT(*) AS total, COALESCE(SUM(is_correct), 0) AS correct
                    FROM practice_records
                    WHERE user_id=:user_id AND task_id<>:task_id AND is_correct IS NOT NULL
                      AND (:started_at IS NULL OR answered_at < :started_at)
                    """
                ),
                {"user_id": user_id, "task_id": str(task_id), "started_at": started_at},
            ).one()
            history_total = int(_row_value(history_row, "total", 0) or 0)
            history_correct = int(_row_value(history_row, "correct", 0) or 0)
    except SQLAlchemyError:
        return EvaluationResult(
            accuracy=0,
            delta=0,
            trend="stable",
            current_total=0,
            summary="暂时无法读取做题记录，请稍后重试。",
        )

    current_rate = _accuracy(current_correct, current_total)
    if current_total == 0:
        return EvaluationResult(
            accuracy=0,
            delta=0,
            trend="stable",
            current_total=0,
            summary="本次任务暂无已评分记录。",
        )
    if history_total == 0:
        return EvaluationResult(
            accuracy=current_rate,
            delta=0,
            trend="first_record",
            current_total=current_total,
            summary=f"本次正确率为 {current_rate * 100:.0f}%，已形成首批可复盘记录。",
        )

    delta = current_rate - _accuracy(history_correct, history_total)
    trend = "improving" if delta > 0.005 else "declining" if delta < -0.005 else "stable"
    direction = "提升" if delta > 0 else "下降" if delta < 0 else "持平"
    return EvaluationResult(
        accuracy=current_rate,
        delta=delta,
        trend=trend,
        current_total=current_total,
        summary=f"本次正确率为 {current_rate * 100:.0f}%，较历史{direction} {abs(delta) * 100:.0f} 个百分点。",
    )
