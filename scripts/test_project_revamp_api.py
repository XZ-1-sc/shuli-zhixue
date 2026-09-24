"""Live acceptance checks for PROJECT_REVAMP_PLAN.md.

The script creates only isolated test rows and removes them in ``finally``.
"""
import os
import uuid

import requests
from sqlalchemy import text

from backend.app.database.session import SessionLocal
from backend.app.utils.password import hash_password


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080").rstrip("/")


def expect(response: requests.Response, status: int = 200) -> dict:
    if response.status_code != status:
        raise AssertionError(f"{response.request.method} {response.url}: {response.status_code} {response.text[:500]}")
    return response.json()


def main() -> None:
    student = requests.Session()
    teacher = requests.Session()
    created_question_ids: list[int] = []
    record_ids: list[int] = []
    comment_ids: list[int] = []
    original_notify: bool | None = None
    temporary_teacher_id: int | None = None
    temporary_teacher_username = f"revamp_teacher_{uuid.uuid4().hex[:10]}"
    try:
        with SessionLocal.begin() as db:
            result = db.execute(text("""
                INSERT INTO users(username,password_hash,nickname,role,current_stage,status)
                VALUES(:username,:password_hash,'整改验收教师','teacher','大一',1)
            """), {"username": temporary_teacher_username, "password_hash": hash_password("RevampTest!2026")})
            temporary_teacher_id = int(result.lastrowid)
            db.execute(text("INSERT INTO teacher_profiles(user_id,display_name) VALUES(:user_id,'整改验收教师')"), {"user_id": temporary_teacher_id})
        student_user = expect(student.post(f"{BASE_URL}/api/login", json={"username": "树虫", "password": "123456", "role": "student"}))
        teacher_user = expect(teacher.post(f"{BASE_URL}/api/login", json={"username": temporary_teacher_username, "password": "RevampTest!2026", "role": "teacher"}))
        original_notify = bool(expect(student.get(f"{BASE_URL}/api/preferences"))["notify_xiaoluo"])
        expect(student.put(f"{BASE_URL}/api/preferences", json={"notify_xiaoluo": False}))

        catalogue = expect(student.get(f"{BASE_URL}/api/courses"))["courses"]
        assert catalogue and all("stage" not in item for item in catalogue)
        user_courses = expect(student.get(f"{BASE_URL}/api/user-courses"))
        selected = user_courses["courses"] or [catalogue[0]["course_name"]]
        saved = expect(student.put(f"{BASE_URL}/api/user-courses", json={"courses": selected, "primary_course": selected[0]}))
        assert saved["courses"] == selected
        overview = expect(student.get(f"{BASE_URL}/api/knowledge-graph-v2"))
        focused = expect(student.get(f"{BASE_URL}/api/knowledge-graph-v2", params={"course": selected[0]}))
        assert any(item["category"] == "course" for item in overview["nodes"])
        assert focused["focus_course"] == selected[0]

        token = uuid.uuid4().hex[:10]
        question = expect(teacher.post(f"{BASE_URL}/api/teacher/questions", json={
            "question_type": "choice", "stage": "大一", "course": selected[0],
            "knowledge_tag": f"验收知识点-{token}", "fine_tag": f"权限边界-{token}", "difficulty": 1,
            "question_text": f"PROJECT_REVAMP_PLAN 自动验收题 {token}：1+1 等于多少？",
            "option_a": "2", "option_b": "3", "option_c": "4", "option_d": "5", "correct_answer": "A",
            "standard_answer": "2", "analysis_text": "基础加法。", "key_steps": ["计算 1+1"],
            "common_errors": ["误选其他项"], "mistake_tags": ["计算"], "visibility": "public", "publish_status": "draft"
        }), 201)
        question_id = int(question["id"])
        created_question_ids.append(question_id)
        expect(teacher.post(f"{BASE_URL}/api/teacher/questions/{question_id}/publish"))

        blocked = student.get(f"{BASE_URL}/api/questions/{question_id}/comments")
        assert blocked.status_code == 403, blocked.text
        submitted = expect(student.post(f"{BASE_URL}/api/practice/submit", json={
            "task_id": f"revamp-{token}", "question_id": question_id, "selected_answer": "A",
            "answer_steps": ["识别为基础加法", "得到 2"], "time_spent_seconds": 1, "practice_mode": "custom"
        }))
        record_ids.append(int(submitted["record_id"]))
        assert expect(student.get(f"{BASE_URL}/api/questions/{question_id}/comments"))["can_comment"] is True
        comment = expect(student.post(f"{BASE_URL}/api/questions/{question_id}/comments", json={"content": f"自动验收讨论 {token}"}), 201)
        comment_id = int(comment["id"])
        comment_ids.append(comment_id)
        first_vote = expect(student.post(f"{BASE_URL}/api/comments/{comment_id}/upvote"))
        second_vote = expect(student.post(f"{BASE_URL}/api/comments/{comment_id}/upvote"))
        assert first_vote["created"] is True and second_vote["created"] is False
        expect(teacher.put(f"{BASE_URL}/api/comments/{comment_id}/best"))
        expect(teacher.put(f"{BASE_URL}/api/comments/{comment_id}/hide"))

        ai = expect(teacher.post(f"{BASE_URL}/api/teacher/ai/generate-question", json={
            "course": selected[0], "knowledge_tag": "函数极限", "question_type": "choice",
            "difficulty": 2, "count": 1, "requirements": "用于接口验收，结果必须可核对"
        }))
        ai_ids = [int(item["id"]) for item in ai["items"]]
        created_question_ids.extend(ai_ids)
        assert all(item["ai_generated"] and item["publish_status"] == "draft" for item in ai["items"])

        instant = expect(student.post(f"{BASE_URL}/api/practice/ai-similar", json={
            "course": selected[0], "knowledge_tag": "函数极限", "count": 3
        }))
        assert 1 <= len(instant["questions"]) <= 3 and instant["persisted"] is False
        assert all("不计入诊断统计" in item["disclaimer"] for item in instant["questions"])

        print(f"PROJECT_REVAMP_API_OK: student={student_user['user_id']} teacher={teacher_user['user_id']} graph={len(overview['nodes'])} nodes")
    finally:
        if original_notify is not None:
            try:
                student.put(f"{BASE_URL}/api/preferences", json={"notify_xiaoluo": original_notify}, timeout=10)
            except requests.RequestException:
                pass
        with SessionLocal.begin() as db:
            for comment_id in comment_ids:
                db.execute(text("DELETE FROM comment_upvotes WHERE comment_id=:id"), {"id": comment_id})
                db.execute(text("DELETE FROM question_comments WHERE id=:id"), {"id": comment_id})
            for record_id in record_ids:
                db.execute(text("DELETE FROM practice_records WHERE id=:id"), {"id": record_id})
            for question_id in reversed(created_question_ids):
                db.execute(text("DELETE FROM questions WHERE id=:id AND (question_text LIKE 'PROJECT_REVAMP_PLAN%' OR ai_generated=1)"), {"id": question_id})
            if temporary_teacher_id is not None:
                db.execute(text("DELETE FROM users WHERE id=:id AND username=:username"), {"id": temporary_teacher_id, "username": temporary_teacher_username})


if __name__ == "__main__":
    main()
