from typing import Any

from sqlalchemy import text


def _get_user_exists(db: Any, user_id: int) -> bool:
    return bool(
        db.execute(text("SELECT 1 FROM users WHERE id = :user_id LIMIT 1"), {"user_id": user_id}).first()
    )

