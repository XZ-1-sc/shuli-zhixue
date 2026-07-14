from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..database.session import SessionLocal


def _accuracy(correct: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return correct / total


def _percent(value: float) -> str:
    return f"{value * 100:.0f}%"


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    return row._mapping.get(key, default)


def evaluate(user_id: int, task_id: str | int) -> str:
    try:
        with SessionLocal() as db:
            current_row = db.execute(
                text(
                    """
                    SELECT
                      COUNT(*) AS total,
                      COALESCE(SUM(is_correct), 0) AS correct,
                      MIN(answered_at) AS started_at
                    FROM practice_records
                    WHERE user_id = :user_id AND task_id = :task_id
                    """
                ),
                {"user_id": user_id, "task_id": str(task_id)},
            ).one()

            current_total = int(_row_value(current_row, "total", 0) or 0)
            current_correct = int(_row_value(current_row, "correct", 0) or 0)
            started_at = _row_value(current_row, "started_at")

            if current_total == 0:
                return "本次任务暂无做题记录，暂时无法评估。"

            history_row = db.execute(
                text(
                    """
                    SELECT
                      COUNT(*) AS total,
                      COALESCE(SUM(is_correct), 0) AS correct
                    FROM practice_records
                    WHERE user_id = :user_id
                      AND task_id <> :task_id
                      AND (:started_at IS NULL OR answered_at < :started_at)
                    """
                ),
                {
                    "user_id": user_id,
                    "task_id": str(task_id),
                    "started_at": started_at,
                },
            ).one()

            history_total = int(_row_value(history_row, "total", 0) or 0)
            history_correct = int(_row_value(history_row, "correct", 0) or 0)
    except SQLAlchemyError:
        return "暂时无法读取做题记录，请检查数据库连接或practice_records.task_id字段。"

    current_rate = _accuracy(current_correct, current_total)
    if history_total == 0:
        return f"本次正确率为{_percent(current_rate)}，暂无历史记录可比较，继续保持练习节奏！"

    history_rate = _accuracy(history_correct, history_total)
    improvement = current_rate - history_rate
    improvement_points = abs(improvement) * 100

    if improvement > 0.005:
        return f"本次正确率为{_percent(current_rate)}，比历史平均提升了{improvement_points:.0f}%，继续加油！"
    if improvement < -0.005:
        return f"本次正确率为{_percent(current_rate)}，比历史平均下降了{improvement_points:.0f}%，建议复盘错题并放慢节奏。"
    return f"本次正确率为{_percent(current_rate)}，与历史平均基本持平，继续稳扎稳打。"
