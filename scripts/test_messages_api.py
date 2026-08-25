"""Unified message system API, privacy and rich-message acceptance test."""

from __future__ import annotations

import json
import os
import sys
import time
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text


ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "backend"))

from app.database.session import BACKEND_DIR, SessionLocal, settings  # noqa: E402
from app.main import app  # noqa: E402
from app.utils.password import hash_password  # noqa: E402


PASSWORD = "Message-QA-2026!"


def expect(response, status_code: int = 200):
    assert response.status_code == status_code, (
        f"{response.request.method} {response.request.url}: {response.status_code} {response.text[:500]}"
    )
    return response.json() if "application/json" in response.headers.get("content-type", "") else response.content


def make_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (96, 72), (34, 123, 141)).save(output, format="PNG")
    return output.getvalue()


def main() -> None:
    marker = str(int(time.time() * 1000))
    clients = {name: TestClient(app) for name in ("teacher", "other_teacher", "student_a", "student_b", "student_c")}
    user_ids: list[int] = []
    uploaded_paths: list[Path] = []
    try:
        with SessionLocal() as db:
            ids: dict[str, int] = {}
            for name, role in {
                "teacher": "teacher", "other_teacher": "teacher",
                "student_a": "student", "student_b": "student", "student_c": "student",
            }.items():
                username = f"qa_msg_{name}_{marker}"
                result = db.execute(
                    text(
                        "INSERT INTO users (username,password_hash,nickname,role,current_stage,status) "
                        "VALUES (:username,:password_hash,:nickname,:role,'大一',1)"
                    ),
                    {"username": username, "password_hash": hash_password(PASSWORD), "nickname": f"消息验收{name}", "role": role},
                )
                ids[name] = int(result.lastrowid)
                if role == "teacher":
                    db.execute(text("INSERT INTO teacher_profiles (user_id,display_name) VALUES (:id,:name)"), {"id": ids[name], "name": username})
            question = db.execute(
                text("SELECT id,stage,course FROM questions WHERE deleted_at IS NULL AND publish_status='published' ORDER BY id LIMIT 1")
            ).mappings().one()
            classes: list[int] = []
            for owner, student, suffix in (
                ("teacher", "student_a", "A"), ("teacher", "student_b", "B"), ("other_teacher", "student_c", "C")
            ):
                result = db.execute(
                    text("INSERT INTO classes (teacher_id,name,stage,course,invite_code,status) VALUES (:teacher,:name,:stage,:course,:code,'active')"),
                    {"teacher": ids[owner], "name": f"消息验收班{suffix}-{marker}", "stage": question["stage"], "course": question["course"], "code": f"M{marker[-6:]}{suffix}"},
                )
                class_id = int(result.lastrowid)
                classes.append(class_id)
                db.execute(text("INSERT INTO class_members (class_id,student_id,status) VALUES (:class_id,:student_id,'active')"), {"class_id": class_id, "student_id": ids[student]})
            record = db.execute(
                text(
                    "INSERT INTO practice_records (task_id,user_id,question_id,answer_text,is_correct,score,time_spent_seconds,practice_mode,review_status) "
                    "VALUES (:task,:user_id,:question_id,'验收作答',0,0,30,'daily','auto_graded')"
                ),
                {"task": f"message-test-{marker}", "user_id": ids["student_a"], "question_id": question["id"]},
            )
            record_id = int(record.lastrowid)
            db.commit()
        user_ids.extend(ids.values())

        for name, client in clients.items():
            role = "teacher" if "teacher" in name else "student"
            expect(client.post("/api/login", json={"username": f"qa_msg_{name}_{marker}", "password": PASSWORD, "role": role}))

        teacher_contacts = expect(clients["teacher"].get("/api/messages/contacts"))
        teacher_contact_ids = {int(item["user_id"]) for item in teacher_contacts["items"]}
        assert {ids["student_a"], ids["student_b"]} <= teacher_contact_ids
        student_contacts = expect(clients["student_a"].get("/api/messages/contacts"))
        student_contact_ids = {int(item["user_id"]) for item in student_contacts["items"]}
        assert ids["teacher"] in student_contact_ids and ids["student_b"] in student_contact_ids
        assert ids["student_c"] not in student_contact_ids and ids["other_teacher"] not in student_contact_ids

        teacher_conversation = expect(
            clients["student_a"].post(
                "/api/messages/conversations/start",
                json={"target_user_id": ids["teacher"], "relation": "teacher_student"},
            )
        )
        peer_conversation = expect(
            clients["student_a"].post(
                "/api/messages/conversations/start",
                json={"target_user_id": ids["student_b"], "relation": "student_student"},
            )
        )
        expect(
            clients["student_a"].post(
                "/api/messages/conversations/start",
                json={"target_user_id": ids["student_c"], "relation": "student_student"},
            ),
            403,
        )
        expect(
            clients["student_a"].post(
                "/api/messages/conversations/start",
                json={"target_user_id": ids["other_teacher"], "relation": "teacher_student"},
            ),
            403,
        )

        teacher_conversation_id = int(teacher_conversation["conversation_id"])
        peer_conversation_id = int(peer_conversation["conversation_id"])
        shared = expect(
            clients["student_a"].post(
                f"/api/messages/conversations/{teacher_conversation_id}",
                json={
                    "content": "请老师帮我看这道错题。",
                    "question_ref": {"question_id": int(question["id"]), "record_id": record_id},
                },
            )
        )
        assert shared["question_ref"]["record_id"] == record_id
        assert expect(clients["teacher"].get("/api/messages/unread-count"))["unread_count"] == 1
        teacher_list = expect(clients["teacher"].get("/api/messages/conversations"))["items"]
        assert {item["id"] for item in teacher_list} == {teacher_conversation_id}
        expect(clients["teacher"].get(f"/api/messages/conversations/{peer_conversation_id}"), 404)
        expect(clients["teacher"].post(f"/api/messages/conversations/{teacher_conversation_id}/read", json={}))
        assert expect(clients["teacher"].get("/api/messages/unread-count"))["unread_count"] == 0

        upload = expect(
            clients["student_a"].post(
                "/api/uploads/message-images", files={"files": ("message.png", make_png(), "image/png")}
            ),
            201,
        )["files"][0]
        with SessionLocal() as db:
            storage_key = db.execute(text("SELECT storage_key FROM uploaded_files WHERE id=:id"), {"id": upload["id"]}).scalar_one()
        upload_root = Path(settings.upload_dir).expanduser()
        if not upload_root.is_absolute():
            upload_root = BACKEND_DIR / upload_root
        uploaded_paths.append((upload_root / str(storage_key)).resolve())
        image_message = expect(
            clients["student_a"].post(
                f"/api/messages/conversations/{peer_conversation_id}",
                json={"attachment_ids": [upload["id"]]},
            )
        )
        assert image_message["attachments"][0]["id"] == upload["id"]
        expect(clients["student_b"].get(upload["url"]))
        expect(clients["student_c"].get(upload["url"]), 403)
        assert expect(clients["student_b"].get("/api/messages/unread-count"))["unread_count"] == 1
        expect(clients["student_b"].post(f"/api/messages/conversations/{peer_conversation_id}/read", json={}))

        expect(clients["student_a"].post(f"/api/messages/conversations/{teacher_conversation_id}", json={}), 422)
        expect(
            clients["student_a"].post(
                f"/api/messages/conversations/{teacher_conversation_id}",
                json={"content": "伪造建议", "message_type": "advice"},
            ),
            403,
        )
        advice = expect(
            clients["teacher"].post(
                f"/api/messages/conversations/{teacher_conversation_id}",
                json={"content": "先复盘概念，再做两道同类题。", "message_type": "advice"},
            )
        )
        assert advice["message_type"] == "advice"
        page = expect(clients["student_a"].get(f"/api/messages/conversations/{teacher_conversation_id}", params={"limit": 1}))
        assert page["has_more"] is True and len(page["items"]) == 1

        summary = expect(clients["student_a"].get("/api/notifications/summary"))
        assert summary["message_unread_count"] >= 1
    finally:
        for client in clients.values():
            client.close()
        if user_ids:
            placeholders = ",".join(f":user_{index}" for index in range(len(user_ids)))
            params = {f"user_{index}": user_id for index, user_id in enumerate(user_ids)}
            with SessionLocal() as db:
                db.execute(text(f"DELETE FROM users WHERE id IN ({placeholders})"), params)
                db.commit()
        for path in uploaded_paths:
            path.unlink(missing_ok=True)

    print("MESSAGES_API_OK: 师生/跨班同学关系、隐私隔离、图文题目消息、未读回执与分页全部通过。")


if __name__ == "__main__":
    main()
