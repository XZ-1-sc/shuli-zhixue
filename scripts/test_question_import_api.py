"""Opt-in API regression for preview, commit, deduplication, and paper reuse."""

from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.database.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402


TEACHER_USERNAME = os.environ.get("E2E_TEACHER_USERNAME", "")
TEACHER_PASSWORD = os.environ.get("E2E_TEACHER_PASSWORD", "")


def expect(response, status_code: int = 200):
    assert response.status_code == status_code, (
        f"{response.request.method} {response.request.url}: "
        f"expected {status_code}, got {response.status_code}: {response.text}"
    )
    return response.json() if "application/json" in response.headers.get("content-type", "") else response.content


def main() -> None:
    if not TEACHER_USERNAME or not TEACHER_PASSWORD:
        raise RuntimeError("请设置 E2E_TEACHER_USERNAME 和 E2E_TEACHER_PASSWORD。")
    client = TestClient(app)
    expect(client.post("/api/login", json={"username": TEACHER_USERNAME, "password": TEACHER_PASSWORD, "role": "teacher"}))
    marker = f"IMPORT-API-{int(time.time())}"
    created_ids: list[int] = []
    try:
        template = expect(client.get("/api/teacher/question-imports/template"))
        frame = pd.read_excel(io.BytesIO(template)).iloc[:2].copy()
        frame.loc[0, "题干"] = f"{marker}：选择题"
        frame.loc[1, "题干"] = f"{marker}：计算题"
        output = io.BytesIO()
        frame.to_excel(output, index=False)

        preview = expect(
            client.post(
                "/api/teacher/question-imports/preview",
                files={"file": ("paper.xlsx", output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        )
        assert preview["valid_count"] == 2 and preview["invalid_count"] == 0, preview

        first = expect(
            client.post(
                "/api/teacher/question-imports/commit",
                json={
                    "questions": preview["questions"],
                    "publish_status": "draft",
                    "visibility": "public",
                    "source_file_name": f"{marker}.xlsx",
                },
            ),
            201,
        )
        created_ids.extend(first["question_ids"])
        assert first["created_count"] == 2

        bank_repeat = expect(
            client.post(
                "/api/teacher/question-imports/commit",
                json={
                    "questions": preview["questions"],
                    "source_file_name": f"{marker}.xlsx",
                },
            ),
            201,
        )
        assert bank_repeat["created_count"] == 0 and bank_repeat["duplicate_count"] == 2

        paper_repeat = expect(
            client.post(
                "/api/teacher/question-imports/commit",
                json={
                    "questions": preview["questions"],
                    "publish_status": "published",
                    "visibility": "class",
                    "source_file_name": f"{marker}.xlsx",
                    "reuse_duplicates": True,
                },
            ),
            201,
        )
        assert paper_repeat["created_count"] == 0 and paper_repeat["reused_count"] == 2
        assert {item["publish_status"] for item in paper_repeat["questions"]} == {"published"}
        print("QUESTION_IMPORT_API_OK")
    finally:
        with SessionLocal() as db:
            for question_id in created_ids:
                db.execute(text("DELETE FROM question_attachments WHERE question_id=:id"), {"id": question_id})
                db.execute(text("DELETE FROM questions WHERE id=:id"), {"id": question_id})
                db.execute(text("DELETE FROM audit_logs WHERE entity_type='question' AND entity_id=:id"), {"id": question_id})
            db.execute(
                text("DELETE FROM audit_logs WHERE actor_user_id=(SELECT id FROM users WHERE username=:username) AND entity_type='question_import' AND payload LIKE :marker"),
                {"username": TEACHER_USERNAME, "marker": f"%{marker}%"},
            )
            db.commit()


if __name__ == "__main__":
    main()
