import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None

def _json(value: list[str]) -> str:
    return json.dumps([str(item).strip() for item in value if str(item).strip()], ensure_ascii=False)

def _managed_student(db: Any, teacher_id: int, student_id: int) -> None:
    exists = db.execute(
        text(
            """
            SELECT 1
            FROM class_members AS cm
            JOIN classes AS c ON c.id = cm.class_id
            WHERE c.teacher_id = :teacher_id AND c.status = 'active'
              AND cm.student_id = :student_id AND cm.status = 'active'
            LIMIT 1
            """
        ),
        {"teacher_id": teacher_id, "student_id": student_id},
    ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="学生不存在，或不在你管理的班级中。")

