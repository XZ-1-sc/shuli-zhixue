from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..database.session import SessionLocal


def _accuracy(correct: int, total: int) -> float:
    return 0.0 if total <= 0 else correct / total


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
                      AVG(score) AS avg_score,
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
                    SELECT COUNT(*) AS total, COALESCE(SUM(is_correct), 0) AS correct
                    FROM practice_records
                    WHERE user_id = :user_id
                      AND task_id <> :task_id
                      AND (:started_at IS NULL OR answered_at < :started_at)
                    """
                ),
                {"user_id": user_id, "task_id": str(task_id), "started_at": started_at},
            ).one()

            history_total = int(_row_value(history_row, "total", 0) or 0)
            history_correct = int(_row_value(history_row, "correct", 0) or 0)
    except SQLAlchemyError:
        return "暂时无法读取做题记录，请检查数据库连接。"

    current_rate = _accuracy(current_correct, current_total)
    if history_total == 0:
        return f"本次正确率为 {_percent(current_rate)}，已经形成第一批数学学习记录，可以开始生成薄弱点规划。"

    history_rate = _accuracy(history_correct, history_total)
    improvement = current_rate - history_rate
    if improvement > 0.005:
        return f"本次正确率为 {_percent(current_rate)}，比历史平均提升 {abs(improvement) * 100:.0f} 个百分点，继续沿当前节奏推进。"
    if improvement < -0.005:
        return f"本次正确率为 {_percent(current_rate)}，比历史平均下降 {abs(improvement) * 100:.0f} 个百分点，建议先复盘错因再进入新知识点。"
    return f"本次正确率为 {_percent(current_rate)}，与历史平均基本持平，下一步要提高解题速度和步骤稳定性。"
