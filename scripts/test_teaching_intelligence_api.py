"""Live acceptance checks for TEACHING_INTELLIGENCE_PLAN.md.

Only UUID-scoped test rows are created. They are removed in ``finally``.
"""
from __future__ import annotations

import os
import uuid

import requests
from sqlalchemy import text

from backend.app.database.session import SessionLocal
from backend.app.utils.password import hash_password


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080").rstrip("/")
PASSWORD = "TeachingTest!2026"


def expect(response: requests.Response, status: int = 200) -> dict:
    if response.status_code != status:
        raise AssertionError(f"{response.request.method} {response.url}: {response.status_code} {response.text[:800]}")
    return response.json()


def main() -> None:
    token = uuid.uuid4().hex[:10]
    teacher_name = f"ti_teacher_{token}"
    student_names = [f"ti_student_{token}_{index}" for index in range(1, 4)]
    teacher = requests.Session()
    students = [requests.Session() for _ in student_names]
    teacher_id: int | None = None
    student_ids: list[int] = []
    class_id: int | None = None
    question_ids: list[int] = []
    record_ids: list[int] = []
    assignment_ids: list[int] = []
    try:
        with SessionLocal.begin() as db:
            result = db.execute(
                text("INSERT INTO users(username,password_hash,nickname,role,current_stage,status) VALUES(:username,:password,'教学智能验收教师','teacher','大一',1)"),
                {"username": teacher_name, "password": hash_password(PASSWORD)},
            )
            teacher_id = int(result.lastrowid)
            db.execute(text("INSERT INTO teacher_profiles(user_id,display_name) VALUES(:id,'教学智能验收教师')"), {"id": teacher_id})
            for index, username in enumerate(student_names, start=1):
                result = db.execute(
                    text("INSERT INTO users(username,password_hash,nickname,role,current_stage,status) VALUES(:username,:password,:nickname,'student','大一',1)"),
                    {"username": username, "password": hash_password(PASSWORD), "nickname": f"验收学生{index}"},
                )
                student_ids.append(int(result.lastrowid))

        expect(teacher.post(f"{BASE_URL}/api/login", json={"username": teacher_name, "password": PASSWORD, "role": "teacher"}))
        for session, username in zip(students, student_names):
            expect(session.post(f"{BASE_URL}/api/login", json={"username": username, "password": PASSWORD, "role": "student"}))

        courses = expect(teacher.get(f"{BASE_URL}/api/courses"))["courses"]
        course = courses[0]["course_name"]
        created_class = expect(teacher.post(f"{BASE_URL}/api/teacher/classes", json={"name": f"教学智能验收班-{token}", "stage": "大一", "course": course}), 201)
        class_id = int(created_class["id"])
        for username in student_names:
            expect(teacher.post(f"{BASE_URL}/api/teacher/classes/{class_id}/members", json={"username": username}))

        question = expect(teacher.post(f"{BASE_URL}/api/teacher/questions", json={
            "question_type": "choice", "stage": "大一", "course": course,
            "knowledge_tag": f"教学智能-{token}", "fine_tag": f"分步解题-{token}", "difficulty": 2,
            "question_text": f"TEACHING_INTELLIGENCE_PLAN 验收题 {token}：1+1 等于多少？",
            "option_a": "2", "option_b": "3", "option_c": "4", "option_d": "5", "correct_answer": "A",
            "standard_answer": "2", "analysis_text": "先识别加法关系，再计算得到 2。",
            "key_steps": ["识别 1+1", "计算得到 2"], "common_errors": ["误选干扰项"], "mistake_tags": ["概念边界"],
            "visibility": "public", "publish_status": "published",
        }), 201)
        question_id = int(question["id"])
        question_ids.append(question_id)

        solution = expect(teacher.get(f"{BASE_URL}/api/teacher/questions/{question_id}/solution-steps"))
        assert solution["steps"], solution
        reviewed_solution = expect(teacher.put(f"{BASE_URL}/api/teacher/questions/{question_id}/solution-steps", json={"steps": [
            {"step_no": 1, "title": "识别运算", "explanation": "确认题目要求执行整数加法。", "formula": "1 + 1", "caution": "不要误读题意。"},
            {"step_no": 2, "title": "完成计算", "explanation": "把两个一相加得到二。", "formula": "1 + 1 = 2", "caution": "核对结果。"},
        ]}))
        assert reviewed_solution["source"] == "teacher"

        for index, session in enumerate(students):
            repeats = 3 if index == 0 else 1
            for repeat in range(repeats):
                submitted = expect(session.post(f"{BASE_URL}/api/practice/submit", json={
                    "task_id": f"ti-{token}-{index}-{repeat}", "question_id": question_id,
                    "selected_answer": "B", "answer_steps": ["误把结果算成 3"],
                    "time_spent_seconds": 12, "practice_mode": "custom",
                }))
                record_ids.append(int(submitted["record_id"]))
                assert submitted["solution_steps"] and submitted["step_feedback"]["wrong_steps"]

        dashboard = expect(teacher.get(f"{BASE_URL}/api/teacher/classes/{class_id}/dashboard"))
        assert dashboard["heatmap"]["rows"] and dashboard["knowledge_bottom"]
        common = expect(teacher.get(f"{BASE_URL}/api/teacher/classes/{class_id}/common-issues"))
        assert common["items"] and common["items"][0]["student_count"] == 3
        insight = expect(teacher.get(f"{BASE_URL}/api/teacher/questions/{question_id}/insight"))
        assert insight["attempts"] >= 5 and insight["wrong_options"][0]["option"] == "B"
        profile = expect(students[0].get(f"{BASE_URL}/api/profile/analytics"))
        assert profile["mastery_evidence"]["formal"] >= 2

        selfcheck = expect(students[0].post(f"{BASE_URL}/api/practice/ai-selfcheck/submit", json={
            "task_id": f"selfcheck-{token}", "source_question_id": question_id,
            "generated_question": "2+2 等于多少？", "expected_answer": "4", "selected_answer": "4",
            "knowledge_tag": f"教学智能-{token}", "evidence_type": "selfcheck", "time_spent_seconds": 20,
        }))
        record_ids.append(int(selfcheck["record_id"]))
        assert selfcheck["counts_toward_formal_stats"] is False and selfcheck["mastery_evidence"] == "selfcheck"
        profile_after = expect(students[0].get(f"{BASE_URL}/api/profile/analytics"))
        assert profile_after["mastery_evidence"]["formal"] == profile["mastery_evidence"]["formal"]
        recovery = expect(students[0].post(f"{BASE_URL}/api/recommend/chain-recovery", json={"record_id": record_ids[0]}))
        assert recovery["strategy"] in {"repair_prerequisite", "reinforce_current"}

        experience = expect(teacher.post(f"{BASE_URL}/api/teacher/experiences", json={
            "question_id": question_id, "knowledge_tag": f"教学智能-{token}",
            "experience_text": "学生常被选项 B 干扰，讲解时先核对加法定义。",
        }), 201)
        assert experience["status"] == "active"
        preferences = expect(teacher.put(f"{BASE_URL}/api/teacher/ai/preferences", json={
            "tone": "简洁、先证据后建议", "scoring_strictness": "balanced", "preferred_types": ["choice"],
            "style_notes": "指出第一处偏差。", "assistant_enabled": True,
        }))
        assert preferences["ai_disclosure_required"] is True

        parsed = expect(teacher.post(f"{BASE_URL}/api/teacher/ai/assignment-intent", json={"class_id": class_id, "message": "出一份 1 题的基础验收卷，限时 10 分钟"}))
        intent = parsed["intent"]
        draft = expect(teacher.post(f"{BASE_URL}/api/teacher/ai/assignment-draft", json={
            **intent, "class_id": class_id, "knowledge_tags": [f"教学智能-{token}"], "count": 1,
            "types": ["choice"], "allow_ai_supplement": False,
        }), 201)
        assignment_id = int(draft["assignment"]["id"])
        assignment_ids.append(assignment_id)
        assert draft["assignment"]["status"] == "draft"
        review = expect(teacher.post(f"{BASE_URL}/api/teacher/ai/assignment-review", json={"assignment_id": assignment_id}))
        assert review["advisory_only"] is True
        commentary = expect(teacher.post(f"{BASE_URL}/api/teacher/ai/assignment-commentary", json={"assignment_id": assignment_id}))
        assert commentary["status"] == "draft" and commentary["draft"]["teaching_flow"]
        similarity = expect(teacher.get(f"{BASE_URL}/api/teacher/assignments/{assignment_id}/similarity-hints"))
        assert similarity["advisory_only"] is True

        report = expect(teacher.post(f"{BASE_URL}/api/teacher/intelligence/artifacts", json={"kind": "weekly_report", "class_id": class_id, "note": "验收"}), 201)
        assert report["status"] == "draft"
        remediation = expect(teacher.post(f"{BASE_URL}/api/teacher/intelligence/artifacts", json={"kind": "remediation", "student_id": student_ids[0], "note": "验收"}), 201)
        assert remediation["status"] == "draft" and "remediation_questions" in remediation["content"]
        with SessionLocal() as db:
            before_confirm = int(db.execute(text("SELECT COUNT(*) FROM user_notifications WHERE user_id=:student AND type='remediation'"), {"student": student_ids[0]}).scalar() or 0)
        expect(teacher.post(f"{BASE_URL}/api/teacher/intelligence/artifacts/{remediation['id']}/confirm", json={}))
        with SessionLocal() as db:
            after_confirm = int(db.execute(text("SELECT COUNT(*) FROM user_notifications WHERE user_id=:student AND type='remediation'"), {"student": student_ids[0]}).scalar() or 0)
        assert after_confirm == before_confirm + 1

        risk_scan = expect(teacher.post(f"{BASE_URL}/api/teacher/intelligence/risks/scan", json={}))
        assert any(item["risk_type"] == "question_health" for item in risk_scan["items"])
        assert expect(teacher.get(f"{BASE_URL}/api/teacher/intelligence/help-signals"))["total"] >= 1

        pregrade = expect(teacher.post(f"{BASE_URL}/api/teacher/review/{record_ids[0]}/ai-pregrade", json={}), 201)
        assert pregrade["score_applied"] is False
        rejected = expect(teacher.post(f"{BASE_URL}/api/teacher/review/ai-pregrades/{pregrade['id']}/decision", json={"action": "rejected", "correction_required": False}))
        assert rejected["score_applied"] is False

        print(f"TEACHING_INTELLIGENCE_API_OK: teacher={teacher_id} class={class_id} records={len(record_ids)} assignment={assignment_id}")
    finally:
        if teacher_id is None:
            return
        with SessionLocal.begin() as db:
            id_params = {"teacher": teacher_id, **{f"s{i}": value for i, value in enumerate(student_ids)}}
            student_clause = ",".join(f":s{i}" for i in range(len(student_ids))) or "NULL"
            db.execute(text("DELETE FROM ai_pregrades WHERE teacher_id=:teacher"), id_params)
            db.execute(text("DELETE FROM teaching_artifacts WHERE teacher_id=:teacher"), id_params)
            db.execute(text("DELETE FROM teaching_risks WHERE teacher_id=:teacher"), id_params)
            db.execute(text("DELETE FROM student_help_signals WHERE teacher_id=:teacher"), id_params)
            db.execute(text("DELETE FROM teacher_experiences WHERE teacher_id=:teacher"), id_params)
            db.execute(text("DELETE FROM teacher_ai_preferences WHERE teacher_id=:teacher"), id_params)
            db.execute(text(f"DELETE FROM user_notifications WHERE user_id=:teacher OR user_id IN ({student_clause})"), id_params)
            db.execute(text(f"DELETE FROM auth_sessions WHERE user_id=:teacher OR user_id IN ({student_clause})"), id_params)
            for assignment_id in assignment_ids:
                db.execute(text("DELETE FROM assignments WHERE id=:id AND teacher_id=:teacher"), {"id": assignment_id, "teacher": teacher_id})
            for record_id in record_ids:
                db.execute(text("DELETE FROM practice_records WHERE id=:id"), {"id": record_id})
            if class_id:
                db.execute(text("DELETE FROM class_members WHERE class_id=:id"), {"id": class_id})
                db.execute(text("DELETE FROM classes WHERE id=:id AND teacher_id=:teacher"), {"id": class_id, "teacher": teacher_id})
            for question_id in question_ids:
                db.execute(text("DELETE FROM questions WHERE id=:id AND created_by=:teacher"), {"id": question_id, "teacher": teacher_id})
            db.execute(text("DELETE FROM teacher_profiles WHERE user_id=:teacher"), {"teacher": teacher_id})
            db.execute(text(f"DELETE FROM users WHERE id=:teacher OR id IN ({student_clause})"), id_params)


if __name__ == "__main__":
    main()
