"""Exercise AI feature contracts with temporary managed teacher/student accounts."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import text


ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "backend"))

from app.agents.schemas import LLMUsage  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.utils.password import hash_password  # noqa: E402


def expect(response, status_code: int = 200):
    assert response.status_code == status_code, f"{response.request.method} {response.request.url}: {response.status_code} {response.text}"
    return response.json() if "application/json" in response.headers.get("content-type", "") else response.text


def structured_fallback(_messages, schema, *, fallback, **_kwargs):
    value = fallback if isinstance(fallback, schema) else schema.model_validate(fallback)
    return value, LLMUsage(model="qa-fallback", status="success")


def main() -> None:
    marker = f"{int(time.time())}"
    teacher_username = os.environ.get("E2E_TEACHER_USERNAME", f"qa_ai_teacher_{marker}")
    teacher_password = os.environ.get("E2E_TEACHER_PASSWORD", f"QaAiTeacher-{marker}-Aa9!")
    student_username = os.environ.get("E2E_STUDENT_USERNAME", f"qa_ai_student_{marker}")
    student_password = os.environ.get("E2E_STUDENT_PASSWORD", f"QaAiStudent-{marker}-Aa9!")
    created_primary_accounts = not all(
        os.environ.get(key)
        for key in ("E2E_TEACHER_USERNAME", "E2E_TEACHER_PASSWORD", "E2E_STUDENT_USERNAME", "E2E_STUDENT_PASSWORD")
    )
    class_id = assignment_id = record_id = peer_teacher_id = teacher_id = student_id = None
    previous_preference = None
    created_notification_ids: list[int] = []
    teacher = TestClient(app)
    student = TestClient(app)
    peer = TestClient(app)
    try:
        if created_primary_accounts:
            with SessionLocal() as db:
                teacher_result = db.execute(
                    text("INSERT INTO users (username,password_hash,nickname,role,current_stage,status) VALUES (:username,:password_hash,:username,'teacher','大一',1)"),
                    {"username": teacher_username, "password_hash": hash_password(teacher_password)},
                )
                primary_teacher_id = int(teacher_result.lastrowid)
                db.execute(text("INSERT INTO teacher_profiles (user_id,display_name) VALUES (:id,:name)"), {"id": primary_teacher_id, "name": teacher_username})
                db.execute(
                    text("INSERT INTO users (username,password_hash,nickname,role,current_stage,status) VALUES (:username,:password_hash,:username,'student','大一',1)"),
                    {"username": student_username, "password_hash": hash_password(student_password)},
                )
                db.commit()
        teacher_user = expect(teacher.post("/api/login", json={"username": teacher_username, "password": teacher_password, "role": "teacher"}))
        student_user = expect(student.post("/api/login", json={"username": student_username, "password": student_password, "role": "student"}))
        teacher_id = int(teacher_user["user_id"])
        student_id = int(student_user["user_id"])
        with SessionLocal() as db:
            previous_preference = db.execute(
                text("SELECT value FROM user_preferences WHERE user_id=:user_id AND `key`='notify_xiaoluo'"),
                {"user_id": student_id},
            ).scalar()
        peer_username = f"qa_ai_peer_{marker}"
        peer_password = f"QaAiPeer-{marker}-Aa9!"
        with SessionLocal() as db:
            question = db.execute(
                text("SELECT id, stage, course FROM questions WHERE publish_status='published' ORDER BY id LIMIT 1")
            ).mappings().one()
            result = db.execute(
                text("INSERT INTO classes (teacher_id,name,stage,course,invite_code) VALUES (:teacher,:name,:stage,:course,:code)"),
                {"teacher": teacher_id, "name": f"AI验收班-{marker}", "stage": question["stage"], "course": question["course"], "code": f"AI{marker[-6:]}"},
            )
            class_id = int(result.lastrowid)
            db.execute(text("INSERT INTO class_members (class_id,student_id) VALUES (:class_id,:student_id)"), {"class_id": class_id, "student_id": student_id})
            assignment = db.execute(
                text("INSERT INTO assignments (teacher_id,class_id,title,status,total_score,published_at) VALUES (:teacher,:class_id,:title,'published',10,NOW())"),
                {"teacher": teacher_id, "class_id": class_id, "title": f"AI报告验收作业-{marker}"},
            )
            assignment_id = int(assignment.lastrowid)
            assignment_question = db.execute(
                text("INSERT INTO assignment_questions (assignment_id,question_id,sort_order,points) VALUES (:assignment,:question,1,10)"),
                {"assignment": assignment_id, "question": question["id"]},
            )
            attempt = db.execute(
                text("INSERT INTO assignment_attempts (assignment_id,user_id,status,submitted_at,total_score,max_score,graded_at) VALUES (:assignment,:student,'graded',NOW(),0,10,NOW())"),
                {"assignment": assignment_id, "student": student_id},
            )
            db.execute(
                text("INSERT INTO assignment_answers (attempt_id,assignment_question_id,answer_text,is_correct,score,review_status,answered_at) VALUES (:attempt,:question,'验收错误答案',0,0,'auto_graded',NOW())"),
                {"attempt": int(attempt.lastrowid), "question": int(assignment_question.lastrowid)},
            )
            result = db.execute(
                text(
                    "INSERT INTO practice_records (task_id,user_id,question_id,answer_text,is_correct,score,mistake_tags,time_spent_seconds,practice_mode,review_status) "
                    "VALUES (:task,:user_id,:question_id,'',0,0,:mistakes,90,'daily','pending')"
                ),
                {"task": f"ai-feature-{marker}", "user_id": student_id, "question_id": question["id"], "mistakes": json.dumps(["概念混淆"], ensure_ascii=False)},
            )
            record_id = int(result.lastrowid)
            result = db.execute(
                text("INSERT INTO users (username,password_hash,nickname,role,current_stage,status) VALUES (:username,:password_hash,:username,'teacher','大一',1)"),
                {"username": peer_username, "password_hash": hash_password(peer_password)},
            )
            peer_teacher_id = int(result.lastrowid)
            db.execute(text("INSERT INTO teacher_profiles (user_id,display_name) VALUES (:id,:name)"), {"id": peer_teacher_id, "name": peer_username})
            db.commit()
        expect(peer.post("/api/login", json={"username": peer_username, "password": peer_password, "role": "teacher"}))

        report = expect(student.get("/api/review/analysis"))
        assert report["wrong_count"] >= 1 and report["reason_distribution"][0]["label"] == "概念混淆"
        insights = expect(student.get("/api/learning-insights"))
        assert len(insights["calendar"]) == 84
        recent = expect(student.get("/api/negotiation/recent"))
        assert "available" in recent
        ability = expect(student.get("/api/profile/ability-map"))
        assert ability["record_count"] >= 1 and ability["dominant_reason"] == "概念混淆"
        preferences = expect(student.get("/api/preferences"))
        expect(student.put("/api/preferences", json={"notify_xiaoluo": False}))
        summary = expect(student.get("/api/notifications/summary"))
        assert summary["preference"]["notify_xiaoluo"] is False and summary["should_nudge"] is False
        expect(student.put("/api/preferences", json={"notify_xiaoluo": True}))

        with patch("app.services.student_ai_service.call_llm_json", side_effect=structured_fallback):
            similar = expect(student.post("/api/practice/ai-similar", json={"question_id": int(question["id"]), "count": 2}))
            digest = expect(student.post("/api/review/weekly-digest"))
        assert len(similar["questions"]) == 2 and similar["persisted"] is False
        assert digest["digest"]["next_week"] and digest["digest"]["stats"]["attempts"] >= 1

        with patch("app.services.chat_service.call_llm", return_value="先核对概念定义，再按解析逐步订正。"):
            chat = student.post(
                "/api/chat",
                json={"message": "这题为什么错？", "context": {"type": "question", "question_id": int(question["id"]), "record_id": record_id}},
            )
        assert chat.status_code == 200 and '"type": "thinking"' in chat.text and '"type": "card"' in chat.text and '"delta"' in chat.text

        with patch("app.services.teacher_ai_service.call_llm_json", side_effect=structured_fallback):
            comment = expect(teacher.post("/api/teacher/ai/grade-comment", json={"record_id": record_id, "draft_score": 70}))
            batch = expect(teacher.post("/api/teacher/ai/grade-comment", json={"record_ids": [record_id]}))
            assert comment["comment"]["draft"]
            class_insight = expect(teacher.post("/api/teacher/ai/class-insight", json={"scope": "class", "class_id": class_id}))
            student_insight = expect(teacher.post("/api/teacher/ai/class-insight", json={"scope": "student", "student_id": student_id}))
            suggestion = expect(teacher.post("/api/teacher/ai/assignment-suggestion", json={"class_id": class_id, "question_count": 5}))
        assert class_insight["insight"]["suggestions"] and student_insight["insight"]["suggestions"]
        assert [item["label"] for item in class_insight["card"]["details"]] == ["亮点", "风险点", "建议"]
        assert [item["label"] for item in student_insight["card"]["details"]] == ["亮点", "风险点", "建议"]
        assert batch["count"] == 1 and batch["items"][0]["record_id"] == record_id
        assert sum(item["count"] for item in suggestion["suggestion"]["knowledge_tags"]) == 5
        assignment_analytics = expect(teacher.get(f"/api/teacher/assignments/{assignment_id}/analytics"))
        class_analytics = expect(teacher.get(f"/api/teacher/classes/{class_id}/analytics"))
        assert assignment_analytics["students"][0]["student_id"] == student_id
        assert class_analytics["students"][0]["student_id"] == student_id
        with patch("app.services.assignment_report_service.call_llm_json", side_effect=structured_fallback):
            assignment_report = expect(teacher.post("/api/teacher/ai/assignment-report", json={"assignment_id": assignment_id}))
        assert assignment_report["card"]["details"] and assignment_report["student_summaries"][0]["student_id"] == student_id

        conversation = expect(teacher.post("/api/messages/conversations/start", json={"target_user_id": student_id, "relation": "teacher_student"}))
        conversation_id = int(conversation["conversation_id"])
        conversations = expect(teacher.get("/api/messages/conversations"))["items"]
        assert any(item["id"] == conversation_id and item["other"]["id"] == student_id for item in conversations)
        teacher_message = expect(teacher.post(f"/api/messages/conversations/{conversation_id}", json={"content": f"验收消息 {marker}"}))
        assert teacher_message["sender_id"] == teacher_id
        assert expect(student.get("/api/messages/unread-count"))["unread_count"] >= 1
        student_thread = expect(student.get(f"/api/messages/conversations/{conversation_id}"))
        assert any(marker in item["content"] for item in student_thread["items"])
        expect(student.post(f"/api/messages/conversations/{conversation_id}/read"))
        assert expect(student.get("/api/messages/unread-count"))["unread_count"] == 0
        assert expect(student.get("/api/notifications/summary"))["message_unread_count"] == 0
        student_reply = expect(student.post(f"/api/messages/conversations/{conversation_id}", json={"content": f"验收回复 {marker}"}))
        assert student_reply["sender_id"] == student_id
        assert expect(teacher.get("/api/messages/unread-count"))["unread_count"] >= 1
        expect(teacher.get(f"/api/messages/conversations/{conversation_id}"))
        expect(teacher.post(f"/api/messages/conversations/{conversation_id}/read"))
        assert expect(teacher.get("/api/messages/unread-count"))["unread_count"] == 0
        expect(peer.get(f"/api/messages/conversations/{conversation_id}"), 404)

        with patch("app.services.advice_service.call_llm_json", side_effect=structured_fallback):
            generated = expect(teacher.post("/api/teacher/advice/generate", json={"class_id": class_id}))
        assert generated["generated_count"] == 1
        drafts = expect(teacher.get(f"/api/teacher/advice/drafts?class_id={class_id}"))["items"]
        assert len(drafts) == 1 and drafts[0]["student_id"] == student_id
        updated_content = f"编辑后的学习建议 {marker}"
        expect(teacher.put(f"/api/teacher/advice/drafts/{drafts[0]['id']}", json={"content": updated_content}))
        sent_advice = expect(teacher.post(f"/api/teacher/advice/drafts/{drafts[0]['id']}/send"))
        assert sent_advice["student_id"] == student_id
        advice_thread = expect(student.get(f"/api/messages/conversations/{conversation_id}"))["items"]
        assert any(item["message_type"] == "advice" and item["content"] == updated_content for item in advice_thread)
        flags = expect(teacher.get("/api/teacher/review/flag"))
        record_flag = next(item for item in flags["items"] if item["record_id"] == record_id)
        assert record_flag["needs_attention"] and "答案为空" in record_flag["reasons"]

        ticket_message = f"老师，我想申请作业延期，验收标记 {marker}"
        with (
            patch("app.services.chat_service.call_llm", return_value="我先记录你的情况，并请教师确认截止安排。"),
            patch("app.services.student_ai_service.call_llm_json", side_effect=structured_fallback),
        ):
            ticket_chat = student.post("/api/chat", json={"message": ticket_message, "context": {"type": "diagnosis"}})
        assert ticket_chat.status_code == 200, ticket_chat.text
        tickets = expect(teacher.get("/api/teacher/tickets"))["items"]
        ticket = next(item for item in tickets if marker in str(item.get("metadata", {}).get("message", "")))
        created_notification_ids.append(int(ticket["id"]))
        expect(teacher.post(f"/api/teacher/tickets/{ticket['id']}/reply", json={"content": f"已收到，稍后确认具体安排。{marker}"}))
        with SessionLocal() as db:
            reply_id = db.execute(
                text("SELECT id FROM user_notifications WHERE user_id=:student_id AND type='ticket_reply' AND content LIKE :marker ORDER BY id DESC LIMIT 1"),
                {"student_id": student_id, "marker": f"%{marker}%"},
            ).scalar()
        assert reply_id
        created_notification_ids.append(int(reply_id))
        expect(peer.post("/api/teacher/ai/grade-comment", json={"record_id": record_id}), 403)
        expect(student.post("/api/teacher/ai/class-insight", json={"scope": "class", "class_id": class_id}), 403)
        print("AI_FEATURES_API_OK")
    finally:
        with SessionLocal() as db:
            if teacher_id and student_id:
                db.execute(text("DELETE FROM teacher_student_messages WHERE teacher_id=:teacher AND student_id=:student"), {"teacher": teacher_id, "student": student_id})
                db.execute(text("DELETE FROM conversations WHERE participant_a IN (:teacher,:student) AND participant_b IN (:teacher,:student)"), {"teacher": teacher_id, "student": student_id})
                db.execute(text("DELETE FROM advice_drafts WHERE teacher_id=:teacher AND student_id=:student"), {"teacher": teacher_id, "student": student_id})
                db.execute(text("DELETE FROM user_notifications WHERE user_id IN (:teacher,:student) AND type IN ('teacher_message','student_message','teacher_advice')"), {"teacher": teacher_id, "student": student_id})
            for notification_id in created_notification_ids:
                db.execute(text("DELETE FROM user_notifications WHERE id=:id"), {"id": notification_id})
            if student_id:
                if previous_preference is None:
                    db.execute(text("DELETE FROM user_preferences WHERE user_id=:user_id AND `key`='notify_xiaoluo'"), {"user_id": student_id})
                else:
                    db.execute(
                        text(
                            "INSERT INTO user_preferences (user_id,`key`,value) VALUES (:user_id,'notify_xiaoluo',:value) "
                            "ON DUPLICATE KEY UPDATE value=VALUES(value)"
                        ),
                        {"user_id": student_id, "value": previous_preference},
                    )
            if record_id:
                db.execute(text("DELETE FROM practice_records WHERE id=:id"), {"id": record_id})
            if class_id:
                db.execute(text("DELETE FROM class_members WHERE class_id=:id"), {"id": class_id})
                db.execute(text("DELETE FROM classes WHERE id=:id"), {"id": class_id})
            if teacher_id and student_id:
                db.execute(text("DELETE FROM chat_messages WHERE user_id IN (:teacher,:student)"), {"teacher": teacher_id, "student": student_id})
            if peer_teacher_id:
                db.execute(text("DELETE FROM auth_sessions WHERE user_id=:id"), {"id": peer_teacher_id})
                db.execute(text("DELETE FROM teacher_profiles WHERE user_id=:id"), {"id": peer_teacher_id})
                db.execute(text("DELETE FROM users WHERE id=:id"), {"id": peer_teacher_id})
            if created_primary_accounts and teacher_id and student_id:
                db.execute(text("DELETE FROM auth_sessions WHERE user_id IN (:teacher,:student)"), {"teacher": teacher_id, "student": student_id})
                db.execute(text("DELETE FROM teacher_profiles WHERE user_id=:id"), {"id": teacher_id})
                db.execute(text("DELETE FROM users WHERE id IN (:teacher,:student)"), {"teacher": teacher_id, "student": student_id})
            db.commit()


if __name__ == "__main__":
    main()
