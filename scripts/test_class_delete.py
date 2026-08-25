"""Class hard-delete protection and cascade acceptance test."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import bindparam, text


ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "backend"))

from app.database.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.utils.password import hash_password  # noqa: E402


PASSWORD = "Class-Delete-QA-2026!"


def expect(response, status_code: int = 200) -> dict:
    assert response.status_code == status_code, (
        f"{response.request.method} {response.request.url}: {response.status_code} {response.text[:800]}"
    )
    return response.json()


def main() -> None:
    marker = str(int(time.time() * 1000))
    teacher = TestClient(app)
    other_teacher = TestClient(app)
    user_ids: list[int] = []

    try:
        with SessionLocal() as db:
            question = db.execute(
                text(
                    "SELECT id,stage,course FROM questions "
                    "WHERE deleted_at IS NULL AND publish_status='published' ORDER BY id LIMIT 1"
                )
            ).mappings().first()
            assert question, "班级删除验收至少需要一道已发布题目。"

            accounts: dict[str, int] = {}
            for name, role in (("teacher", "teacher"), ("other", "teacher"), ("student", "student")):
                username = f"qa_class_delete_{name}_{marker}"
                result = db.execute(
                    text(
                        "INSERT INTO users (username,password_hash,nickname,role,current_stage,status) "
                        "VALUES (:username,:password_hash,:nickname,:role,'大一',1)"
                    ),
                    {
                        "username": username,
                        "password_hash": hash_password(PASSWORD),
                        "nickname": f"班级删除验收{name}",
                        "role": role,
                    },
                )
                accounts[name] = int(result.lastrowid)
                if role == "teacher":
                    db.execute(
                        text("INSERT INTO teacher_profiles (user_id,display_name) VALUES (:id,:display_name)"),
                        {"id": accounts[name], "display_name": username},
                    )
            db.commit()
        user_ids.extend(accounts.values())

        expect(
            teacher.post(
                "/api/login",
                json={"username": f"qa_class_delete_teacher_{marker}", "password": PASSWORD, "role": "teacher"},
            )
        )
        expect(
            other_teacher.post(
                "/api/login",
                json={"username": f"qa_class_delete_other_{marker}", "password": PASSWORD, "role": "teacher"},
            )
        )

        class_index = 0

        def create_class(label: str) -> dict:
            nonlocal class_index
            class_index += 1
            return expect(
                teacher.post(
                    "/api/teacher/classes",
                    json={
                        "name": f"{label}-{marker}",
                        "stage": str(question["stage"]),
                        "course": str(question["course"]),
                    },
                ),
                201,
            )

        empty_class = create_class("空班级删除验收")
        empty_impact = expect(teacher.get(f"/api/teacher/classes/{empty_class['id']}/delete-impact"))
        assert not empty_impact["has_data"] and not empty_impact["has_published_assignment"]
        empty_deleted = expect(teacher.delete(f"/api/teacher/classes/{empty_class['id']}"))
        assert empty_deleted == {"deleted": True, "member_count": 0, "assignment_count": 0, "record_count": 0}
        expect(teacher.get(f"/api/teacher/classes/{empty_class['id']}"), 404)

        data_class = create_class("数据班级删除验收")
        expect(
            teacher.post(
                f"/api/teacher/classes/{data_class['id']}/members",
                json={"username": f"qa_class_delete_student_{marker}"},
            )
        )
        with SessionLocal() as db:
            assignment = db.execute(
                text(
                    "INSERT INTO assignments (teacher_id,class_id,title,status,total_score,published_at) "
                    "VALUES (:teacher_id,:class_id,:title,'closed',10,NOW())"
                ),
                {
                    "teacher_id": accounts["teacher"],
                    "class_id": data_class["id"],
                    "title": f"级联删除验收作业-{marker}",
                },
            )
            assignment_id = int(assignment.lastrowid)
            assignment_question = db.execute(
                text(
                    "INSERT INTO assignment_questions (assignment_id,question_id,sort_order,points) "
                    "VALUES (:assignment_id,:question_id,1,10)"
                ),
                {"assignment_id": assignment_id, "question_id": int(question["id"])},
            )
            assignment_question_id = int(assignment_question.lastrowid)
            attempt = db.execute(
                text(
                    "INSERT INTO assignment_attempts "
                    "(assignment_id,user_id,status,submitted_at,total_score,max_score,graded_at) "
                    "VALUES (:assignment_id,:student_id,'graded',NOW(),0,10,NOW())"
                ),
                {"assignment_id": assignment_id, "student_id": accounts["student"]},
            )
            attempt_id = int(attempt.lastrowid)
            record = db.execute(
                text(
                    "INSERT INTO practice_records "
                    "(task_id,user_id,question_id,answer_text,is_correct,score,time_spent_seconds,practice_mode,"
                    "assignment_id,assignment_attempt_id,review_status) "
                    "VALUES (:task_id,:student_id,:question_id,'验收答案',0,0,30,'assignment',"
                    ":assignment_id,:attempt_id,'auto_graded')"
                ),
                {
                    "task_id": f"class-delete-{marker}",
                    "student_id": accounts["student"],
                    "question_id": int(question["id"]),
                    "assignment_id": assignment_id,
                    "attempt_id": attempt_id,
                },
            )
            record_id = int(record.lastrowid)
            answer = db.execute(
                text(
                    "INSERT INTO assignment_answers "
                    "(attempt_id,assignment_question_id,practice_record_id,answer_text,is_correct,score,review_status,answered_at) "
                    "VALUES (:attempt_id,:assignment_question_id,:record_id,'验收答案',0,0,'auto_graded',NOW())"
                ),
                {
                    "attempt_id": attempt_id,
                    "assignment_question_id": assignment_question_id,
                    "record_id": record_id,
                },
            )
            answer_id = int(answer.lastrowid)
            db.commit()

        data_impact = expect(teacher.get(f"/api/teacher/classes/{data_class['id']}/delete-impact"))
        assert data_impact["class_name"] == data_class["name"]
        assert data_impact["has_data"] and not data_impact["has_published_assignment"]
        assert {key: data_impact[key] for key in ("member_count", "assignment_count", "record_count")} == {
            "member_count": 1,
            "assignment_count": 1,
            "record_count": 1,
        }

        protected = expect(teacher.delete(f"/api/teacher/classes/{data_class['id']}"), 409)
        assert all(fragment in protected["detail"] for fragment in ("1 名学生", "1 份作业", "1 条关联作答记录", "请输入班级名称"))

        deleted = expect(teacher.delete(f"/api/teacher/classes/{data_class['id']}?confirm=true"))
        assert deleted["deleted"] and deleted["member_count"] == deleted["assignment_count"] == deleted["record_count"] == 1
        with SessionLocal() as db:
            for table_name, entity_id in (
                ("classes", int(data_class["id"])),
                ("assignments", assignment_id),
                ("assignment_questions", assignment_question_id),
                ("assignment_attempts", attempt_id),
                ("assignment_answers", answer_id),
            ):
                remaining = db.execute(
                    text(f"SELECT COUNT(*) FROM {table_name} WHERE id=:entity_id"),
                    {"entity_id": entity_id},
                ).scalar_one()
                assert int(remaining) == 0, f"{table_name} 未按预期级联删除"
            kept_record = db.execute(
                text("SELECT assignment_id,assignment_attempt_id FROM practice_records WHERE id=:record_id"),
                {"record_id": record_id},
            ).mappings().one()
            assert kept_record["assignment_id"] is None and kept_record["assignment_attempt_id"] is None

        published_class = create_class("进行中作业班级删除验收")
        with SessionLocal() as db:
            assignment = db.execute(
                text(
                    "INSERT INTO assignments (teacher_id,class_id,title,status,total_score,published_at) "
                    "VALUES (:teacher_id,:class_id,:title,'published',10,NOW())"
                ),
                {
                    "teacher_id": accounts["teacher"],
                    "class_id": published_class["id"],
                    "title": f"进行中作业-{marker}",
                },
            )
            published_assignment_id = int(assignment.lastrowid)
            db.commit()
        published_impact = expect(teacher.get(f"/api/teacher/classes/{published_class['id']}/delete-impact"))
        assert published_impact["has_published_assignment"]
        for suffix in ("", "?confirm=true"):
            blocked = expect(teacher.delete(f"/api/teacher/classes/{published_class['id']}{suffix}"), 409)
            assert "请先结束作业再删除班级" in blocked["detail"]
        with SessionLocal() as db:
            db.execute(
                text("UPDATE assignments SET status='closed' WHERE id=:assignment_id"),
                {"assignment_id": published_assignment_id},
            )
            db.commit()
        expect(teacher.delete(f"/api/teacher/classes/{published_class['id']}?confirm=true"))

        owned_class = create_class("权限隔离班级删除验收")
        expect(other_teacher.get(f"/api/teacher/classes/{owned_class['id']}/delete-impact"), 404)
        expect(other_teacher.delete(f"/api/teacher/classes/{owned_class['id']}"), 404)
        expect(teacher.delete(f"/api/teacher/classes/{owned_class['id']}"))
        expect(teacher.delete("/api/teacher/classes/9223372036854775000"), 404)

        archive_class = create_class("归档功能回归验收")
        archived = expect(teacher.post(f"/api/teacher/classes/{archive_class['id']}/archive"))
        assert archived == {"archived": True}
        active_ids = {int(item["id"]) for item in expect(teacher.get("/api/teacher/classes"))["items"]}
        assert int(archive_class["id"]) not in active_ids

        print("CLASS_DELETE_API_OK")
    finally:
        teacher.close()
        other_teacher.close()
        if user_ids:
            with SessionLocal() as db:
                db.execute(
                    text(
                        "UPDATE practice_records SET assignment_id=NULL,assignment_attempt_id=NULL "
                        "WHERE user_id IN :ids"
                    ).bindparams(bindparam("ids", expanding=True)),
                    {"ids": user_ids},
                )
                db.execute(
                    text("DELETE FROM users WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)),
                    {"ids": user_ids},
                )
                db.commit()


if __name__ == "__main__":
    main()
