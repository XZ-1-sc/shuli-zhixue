"""Run the teacher browser regression with isolated temporary accounts."""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

from sqlalchemy import text


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.database.session import SessionLocal  # noqa: E402
from app.utils.password import hash_password  # noqa: E402


def create_accounts() -> tuple[int, int]:
    marker = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"
    teacher_username = f"qa_teacher_{marker}"
    student_username = f"qa_student_{marker}"
    teacher_password = f"QaTeacher-{marker}-Aa9!"
    student_password = f"QaStudent-{marker}-Aa9!"

    with SessionLocal() as db:
        teacher_result = db.execute(
            text(
                "INSERT INTO users (username,password_hash,nickname,role,current_stage,status) "
                "VALUES (:username,:password_hash,:username,'teacher','大一',1)"
            ),
            {"username": teacher_username, "password_hash": hash_password(teacher_password)},
        )
        teacher_id = int(teacher_result.lastrowid)
        db.execute(
            text("INSERT INTO teacher_profiles (user_id,display_name) VALUES (:id,:username)"),
            {"id": teacher_id, "username": teacher_username},
        )
        student_result = db.execute(
            text(
                "INSERT INTO users (username,password_hash,nickname,role,current_stage,status) "
                "VALUES (:username,:password_hash,:username,'student','大一',1)"
            ),
            {"username": student_username, "password_hash": hash_password(student_password)},
        )
        student_id = int(student_result.lastrowid)
        db.commit()

    os.environ.update(
        {
            "E2E_TEACHER_USERNAME": teacher_username,
            "E2E_TEACHER_PASSWORD": teacher_password,
            "E2E_STUDENT_USERNAME": student_username,
            "E2E_STUDENT_PASSWORD": student_password,
        }
    )
    return teacher_id, student_id


def cleanup_accounts(user_ids: tuple[int, int]) -> None:
    with SessionLocal() as db:
        for user_id in user_ids:
            db.execute(text("DELETE FROM users WHERE id=:id"), {"id": user_id})
        db.commit()


def main() -> None:
    user_ids = create_accounts()
    try:
        import test_teacher_browser

        test_teacher_browser.main()
    finally:
        cleanup_accounts(user_ids)


if __name__ == "__main__":
    main()
