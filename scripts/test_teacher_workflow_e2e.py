"""Run the complete teacher-to-student assignment workflow against the local app.

This is an opt-in integration check. It uses the configured MySQL database, creates
timestamped records, and removes them before exiting.
"""

from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.database.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.api.routes.uploads import _upload_root  # noqa: E402
from app.utils.password import hash_password  # noqa: E402


TEACHER_USERNAME = os.environ.get("E2E_TEACHER_USERNAME", "")
TEACHER_PASSWORD = os.environ.get("E2E_TEACHER_PASSWORD", "")
STUDENT_USERNAME = os.environ.get("E2E_STUDENT_USERNAME", "")
STUDENT_PASSWORD = os.environ.get("E2E_STUDENT_PASSWORD", "")


def require_test_credentials() -> None:
    if not all((TEACHER_USERNAME, TEACHER_PASSWORD, STUDENT_USERNAME, STUDENT_PASSWORD)):
        raise RuntimeError(
            "请设置 E2E_TEACHER_USERNAME、E2E_TEACHER_PASSWORD、"
            "E2E_STUDENT_USERNAME、E2E_STUDENT_PASSWORD 后运行教师端回归。"
        )


def expect(response, status_code: int = 200):
    assert response.status_code == status_code, (
        f"{response.request.method} {response.request.url}: "
        f"expected {status_code}, got {response.status_code}: {response.text}"
    )
    if "application/json" in response.headers.get("content-type", ""):
        return response.json()
    return response.content


def image_bytes(color: tuple[int, int, int]) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (180, 120), color).save(output, format="PNG")
    return output.getvalue()


def main() -> None:
    require_test_credentials()
    marker = str(int(time.time()))
    class_name = f"教师闭环回归班-{marker}"
    teacher = TestClient(app)
    student = TestClient(app)
    peer_teacher = TestClient(app)
    outsider = TestClient(app)
    class_id = assignment_id = peer_teacher_id = peer_class_id = None
    peer_username = f"隔离教师-{marker}"
    peer_password = f"Peer-{marker}-Aa9!"
    peer_class_name = f"权限隔离班-{marker}"
    question_ids: list[int] = []
    copied_question_id: int | None = None
    upload_ids: list[int] = []

    try:
        teacher_user = expect(
            teacher.post(
                "/api/login",
                json={"username": TEACHER_USERNAME, "password": TEACHER_PASSWORD, "role": "teacher"},
            )
        )
        student_user = expect(
            student.post(
                "/api/login",
                json={"username": STUDENT_USERNAME, "password": STUDENT_PASSWORD, "role": "student"},
            )
        )
        assert teacher_user["role"] == "teacher"
        assert student_user["role"] == "student"

        with SessionLocal() as db:
            result = db.execute(
                text(
                    "INSERT INTO users (username,password_hash,nickname,role,current_stage,status) "
                    "VALUES (:username,:password_hash,:nickname,'teacher','大一',1)"
                ),
                {
                    "username": peer_username,
                    "password_hash": hash_password(peer_password),
                    "nickname": peer_username,
                },
            )
            peer_teacher_id = int(result.lastrowid)
            db.execute(
                text("INSERT INTO teacher_profiles (user_id,display_name) VALUES (:id,:name)"),
                {"id": peer_teacher_id, "name": peer_username},
            )
            db.commit()
        expect(
            peer_teacher.post(
                "/api/login",
                json={"username": peer_username, "password": peer_password, "role": "teacher"},
            )
        )
        peer_class = expect(
            peer_teacher.post(
                "/api/teacher/classes",
                json={"name": peer_class_name, "stage": "大一", "course": "高等数学（上）"},
            ),
            201,
        )
        peer_class_id = int(peer_class["id"])
        expect(
            peer_teacher.post(
                f"/api/teacher/classes/{peer_class_id}/members",
                json={"username": STUDENT_USERNAME},
            )
        )

        created_class = expect(
            teacher.post(
                "/api/teacher/classes",
                json={"name": class_name, "stage": "大一", "course": "高等数学（上）"},
            ),
            201,
        )
        class_id = int(created_class["id"])
        edited_class = expect(
            teacher.put(
                f"/api/teacher/classes/{class_id}",
                json={"name": class_name, "stage": "大一", "course": "高等数学（上）"},
            )
        )
        old_invite = edited_class["invite_code"]
        regenerated = expect(
            teacher.post(f"/api/teacher/classes/{class_id}/regenerate-invite")
        )
        assert regenerated["class"]["invite_code"] != old_invite
        members = expect(
            teacher.post(
                f"/api/teacher/classes/{class_id}/members",
                json={"username": STUDENT_USERNAME},
            )
        )
        assert any(item["username"] == STUDENT_USERNAME for item in members["members"])
        exported = expect(teacher.get(f"/api/teacher/classes/{class_id}/export"))
        assert exported.startswith(b"\xef\xbb\xbf")
        assert STUDENT_USERNAME in exported.decode("utf-8-sig")

        question_upload = expect(
            teacher.post(
                "/api/uploads/question-images",
                files={"files": ("函数图像.png", image_bytes((27, 110, 139)), "image/png")},
            ),
            201,
        )["files"][0]
        upload_ids.append(int(question_upload["id"]))

        choice = expect(
            teacher.post(
                "/api/teacher/questions",
                json={
                    "question_type": "choice",
                    "stage": "大一",
                    "course": "高等数学（上）",
                    "knowledge_tag": "函数与极限",
                    "fine_tag": "函数连续性",
                    "difficulty": 2,
                    "question_text": "若函数在 x=0 处连续，则下列结论正确的是？",
                    "option_a": "函数在 x=0 处必有定义",
                    "option_b": "函数在 x=0 处必可导",
                    "option_c": "函数在 x=0 处必单调",
                    "option_d": "函数在 x=0 处必有极值",
                    "correct_answer": "A",
                    "standard_answer": "A",
                    "analysis_text": "连续要求函数值存在，并且极限等于该函数值。",
                    "key_steps": ["确认连续定义", "排除可导、单调和极值等更强条件"],
                    "common_errors": ["把连续误认为必然可导"],
                    "mistake_tags": ["概念混淆"],
                    "attachment_ids": [question_upload["id"]],
                    "analysis_attachment_ids": [],
                    "visibility": "public",
                    "publish_status": "published",
                },
            ),
            201,
        )
        question_ids.append(int(choice["id"]))
        assert len(choice["attachments"]) == 1
        copied = expect(teacher.post(f"/api/teacher/questions/{choice['id']}/copy"), 201)
        copied_question_id = int(copied["id"])
        assert copied["publish_status"] == "draft"
        assert copied["question_text"].endswith("（副本）")
        assert copied["copied_from"] == choice["id"]

        proof = expect(
            teacher.post(
                "/api/teacher/questions",
                json={
                    "question_type": "proof",
                    "stage": "大一",
                    "course": "高等数学（上）",
                    "knowledge_tag": "函数与极限",
                    "fine_tag": "极限唯一性",
                    "difficulty": 3,
                    "question_text": "证明：若数列收敛，则它的极限唯一。",
                    "standard_answer": "使用反证法和极限定义证明两个候选极限必相等。",
                    "analysis_text": "假设存在两个不同极限，取二者距离的一半构造矛盾。",
                    "key_steps": ["假设极限分别为 a 与 b", "取 epsilon=|a-b|/3", "利用三角不等式推出矛盾"],
                    "common_errors": ["没有明确选取 epsilon"],
                    "mistake_tags": ["证明不完整"],
                    "attachment_ids": [],
                    "analysis_attachment_ids": [],
                    "visibility": "class",
                    "publish_status": "published",
                },
            ),
            201,
        )
        question_ids.append(int(proof["id"]))
        default_pool = expect(
            teacher.get(
                "/api/teacher/questions",
                params={"scope": "all", "page_size": 100},
            )
        )
        assert default_pool["items"]
        assert all(item["source_name"] != "WeBWorK Open Problem Library" for item in default_pool["items"])
        random_pool = expect(
            teacher.get(
                "/api/teacher/questions/random",
                params={"count": 8, "stage": "大一"},
            )
        )
        assert random_pool["selected_count"] > 0
        assert all(item["source_name"] != "WeBWorK Open Problem Library" for item in random_pool["items"])
        expect(
            student.post(
                "/api/practice/submit",
                json={
                    "user_id": student_user["user_id"],
                    "task_id": f"private-question-{marker}",
                    "question_id": proof["id"],
                    "answer_text": "自由练习不应读取班级私有题。",
                    "practice_mode": "custom",
                },
            ),
            404,
        )

        assignment = expect(
            teacher.post(
                "/api/teacher/assignments",
                json={
                    "class_id": class_id,
                    "title": f"教师闭环回归作业-{marker}",
                    "description": "验证出题、提交、批改和订正链路。",
                    "question_ids": question_ids,
                    "points": [40, 60],
                    "time_limit_minutes": 5,
                    "max_attempts": 2,
                    "show_analysis_after_submit": True,
                    "publish": False,
                },
            ),
            201,
        )
        assignment_id = int(assignment["assignment"]["id"])
        assert assignment["assignment"]["status"] == "draft"
        expect(teacher.post(f"/api/teacher/assignments/{assignment_id}/publish"))
        expect(teacher.post(f"/api/teacher/questions/{question_ids[0]}/archive"))

        listed = expect(student.get("/api/assignments"))
        assert any(item["id"] == assignment_id for item in listed["items"])
        started = expect(student.post(f"/api/assignments/{assignment_id}/start"))
        assert started["attempt"]["status"] == "in_progress"
        questions = {item["id"]: item for item in started["questions"]}
        assert questions[question_ids[0]]["attachments"]["question"]
        expect(student.get(questions[question_ids[0]]["attachments"]["question"][0]["url"]))

        choice_item = questions[question_ids[0]]
        proof_item = questions[question_ids[1]]
        expect(
            student.put(
                f"/api/assignments/{assignment_id}/answers",
                json={
                    "assignment_question_id": choice_item["assignment_question_id"],
                    "selected_answer": "A",
                },
            )
        )
        answer_upload = expect(
            student.post(
                "/api/uploads/answer-images",
                data={"user_id": str(student_user["user_id"])},
                files={"files": ("证明过程.png", image_bytes((235, 228, 205)), "image/png")},
            ),
            201,
        )["files"][0]
        upload_ids.append(int(answer_upload["id"]))
        saved_proof = expect(
            student.put(
                f"/api/assignments/{assignment_id}/answers",
                json={
                    "assignment_question_id": proof_item["assignment_question_id"],
                    "answer_text": "设有两个极限 a、b，取 epsilon=|a-b|/3，再由三角不等式推出矛盾。",
                    "attachment_ids": [answer_upload["id"]],
                },
            )
        )
        assert saved_proof["review_status"] == "pending"
        submitted = expect(student.post(f"/api/assignments/{assignment_id}/submit"))
        assert submitted["attempt"]["status"] == "grading"

        peer_pending = expect(
            peer_teacher.get(
                "/api/teacher/review-queue",
                params={"assignment_id": assignment_id, "review_status": "pending"},
            )
        )
        assert peer_pending["total"] == 0

        pending = expect(
            teacher.get(
                "/api/teacher/review-queue",
                params={"assignment_id": assignment_id, "review_status": "pending"},
            )
        )
        assert pending["total"] == 1
        record_id = int(pending["items"][0]["id"])
        expect(
            peer_teacher.post(
                f"/api/teacher/submissions/{record_id}/grade",
                json={"score": 100, "feedback": "越权批改应被拒绝。", "correction_required": False},
            ),
            404,
        )
        expect(teacher.get(pending["items"][0]["attachments"][0]["url"]))
        expect(
            teacher.post(
                f"/api/teacher/submissions/{record_id}/grade",
                json={
                    "score": 55,
                    "feedback": "思路正确，但三角不等式的矛盾步骤需要完整写出。",
                    "correction_required": True,
                },
            )
        )
        returned = expect(student.get(f"/api/assignments/{assignment_id}/result"))
        assert returned["attempt"]["status"] == "returned"

        restarted = expect(student.post(f"/api/assignments/{assignment_id}/start"))
        assert restarted["attempt"]["status"] == "in_progress"
        restarted_questions = {item["id"]: item for item in restarted["questions"]}
        expect(
            student.put(
                f"/api/assignments/{assignment_id}/answers",
                json={
                    "assignment_question_id": restarted_questions[question_ids[0]]["assignment_question_id"],
                    "selected_answer": "A",
                },
            )
        )
        corrected = expect(
            student.put(
                f"/api/assignments/{assignment_id}/answers",
                json={
                    "assignment_question_id": restarted_questions[question_ids[1]]["assignment_question_id"],
                    "answer_text": "设 a、b 均为极限且 a 不等于 b。取 epsilon=|a-b|/3，充分大 n 时有 |x_n-a| 与 |x_n-b| 均小于 epsilon，于是 |a-b|<2|a-b|/3，矛盾，故 a=b。",
                },
            )
        )
        assert corrected["review_status"] == "pending"
        expect(student.post(f"/api/assignments/{assignment_id}/submit"))
        second_queue = expect(
            teacher.get(
                "/api/teacher/review-queue",
                params={"assignment_id": assignment_id, "review_status": "pending"},
            )
        )
        assert second_queue["total"] == 1
        expect(
            teacher.post(
                f"/api/teacher/submissions/{second_queue['items'][0]['id']}/grade",
                json={
                    "score": 95,
                    "feedback": "订正完整，反证结构和 epsilon 的选取都准确。",
                    "correction_required": False,
                },
            )
        )
        final_result = expect(student.get(f"/api/assignments/{assignment_id}/result"))
        assert final_result["attempt"]["status"] == "graded"
        assert float(final_result["attempt"]["total_score"]) == 97.0

        second_attempt = expect(student.post(f"/api/assignments/{assignment_id}/start"))
        assert second_attempt["attempt"]["attempt_no"] == 2
        with SessionLocal() as db:
            db.execute(
                text(
                    "UPDATE assignment_attempts SET started_at=DATE_SUB(NOW(), INTERVAL 6 MINUTE) "
                    "WHERE id=:id"
                ),
                {"id": second_attempt["attempt"]["id"]},
            )
            db.commit()
        expired_detail = expect(student.get(f"/api/assignments/{assignment_id}"))
        assert expired_detail["attempt"]["time_expired"] is True
        expired_result = expect(student.post(f"/api/assignments/{assignment_id}/submit"))
        assert expired_result["attempt"]["status"] == "graded"
        assert float(expired_result["attempt"]["total_score"]) == 0.0
        expect(student.post(f"/api/assignments/{assignment_id}/start"), 409)

        assignment_list = expect(teacher.get("/api/teacher/assignments"))
        assignment_summary = next(item for item in assignment_list["items"] if item["id"] == assignment_id)
        assert assignment_summary["started_count"] == 1
        assert assignment_summary["submitted_count"] == 1
        assert assignment_summary["graded_count"] == 1

        expect(student.get("/api/teacher/classes"), 403)
        expect(outsider.get("/api/teacher/classes"), 401)
        print("TEACHER_WORKFLOW_E2E_OK")
    finally:
        storage_keys: list[str] = []
        with SessionLocal() as db:
            if upload_ids:
                storage_keys = [
                    str(row[0])
                    for row in db.execute(
                        text("SELECT storage_key FROM uploaded_files WHERE id IN :ids"),
                        {"ids": tuple(upload_ids)},
                    ).all()
                ]
            if assignment_id:
                db.execute(
                    text(
                        "DELETE aa FROM answer_attachments aa JOIN practice_records pr "
                        "ON pr.id=aa.practice_record_id WHERE pr.assignment_id=:id"
                    ),
                    {"id": assignment_id},
                )
                db.execute(
                    text("UPDATE assignment_answers SET practice_record_id=NULL WHERE attempt_id IN (SELECT id FROM assignment_attempts WHERE assignment_id=:id)"),
                    {"id": assignment_id},
                )
                db.execute(text("DELETE FROM practice_records WHERE assignment_id=:id"), {"id": assignment_id})
                db.execute(
                    text("DELETE FROM assignment_answers WHERE attempt_id IN (SELECT id FROM assignment_attempts WHERE assignment_id=:id)"),
                    {"id": assignment_id},
                )
                db.execute(text("DELETE FROM assignment_attempts WHERE assignment_id=:id"), {"id": assignment_id})
                db.execute(text("DELETE FROM assignment_questions WHERE assignment_id=:id"), {"id": assignment_id})
                db.execute(text("DELETE FROM assignments WHERE id=:id"), {"id": assignment_id})
                db.execute(
                    text("DELETE FROM user_notifications WHERE action_url IN (:student_url,:teacher_url)"),
                    {"student_url": f"/assignments/{assignment_id}", "teacher_url": f"/teacher/assignments/{assignment_id}"},
                )
            cleanup_question_ids = question_ids + ([copied_question_id] if copied_question_id else [])
            for question_id in cleanup_question_ids:
                db.execute(text("DELETE FROM question_attachments WHERE question_id=:id"), {"id": question_id})
                db.execute(text("DELETE FROM questions WHERE id=:id"), {"id": question_id})
                db.execute(
                    text("DELETE FROM audit_logs WHERE entity_type='question' AND entity_id=:id"),
                    {"id": question_id},
                )
            for upload_id in upload_ids:
                db.execute(text("DELETE FROM uploaded_files WHERE id=:id"), {"id": upload_id})
            if class_id:
                db.execute(text("DELETE FROM class_members WHERE class_id=:id"), {"id": class_id})
                db.execute(text("DELETE FROM classes WHERE id=:id"), {"id": class_id})
                db.execute(
                    text("DELETE FROM audit_logs WHERE entity_type IN ('class','assignment') AND entity_id IN (:class_id,:assignment_id)"),
                    {"class_id": class_id, "assignment_id": assignment_id or 0},
                )
                db.execute(
                    text("DELETE FROM user_notifications WHERE content LIKE :content"),
                    {"content": f"%{class_name}%"},
                )
            if peer_class_id:
                db.execute(text("DELETE FROM class_members WHERE class_id=:id"), {"id": peer_class_id})
                db.execute(text("DELETE FROM classes WHERE id=:id"), {"id": peer_class_id})
                db.execute(
                    text("DELETE FROM audit_logs WHERE entity_type='class' AND entity_id=:id"),
                    {"id": peer_class_id},
                )
                db.execute(
                    text("DELETE FROM user_notifications WHERE content LIKE :content"),
                    {"content": f"%{peer_class_name}%"},
                )
            if peer_teacher_id:
                db.execute(text("DELETE FROM audit_logs WHERE actor_user_id=:id"), {"id": peer_teacher_id})
                db.execute(text("DELETE FROM auth_sessions WHERE user_id=:id"), {"id": peer_teacher_id})
                db.execute(text("DELETE FROM teacher_profiles WHERE user_id=:id"), {"id": peer_teacher_id})
                db.execute(text("DELETE FROM users WHERE id=:id"), {"id": peer_teacher_id})
            db.commit()
        for storage_key in storage_keys:
            (_upload_root() / storage_key).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
