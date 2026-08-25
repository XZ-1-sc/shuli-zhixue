import json
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text

from ..api.schemas import ChatContext
from ..api.utils import _json_safe, _parse_json_list
from ..database.repositories.diagnosis import _diagnose_sync, _study_roadmap_sync
from ..database.session import SessionLocal


def _student_behavior_backtrace(user_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        last_chat = db.execute(
            text(
                """
                SELECT session_id,content,created_at FROM chat_messages
                WHERE user_id=:user_id AND role='user'
                ORDER BY created_at DESC,id DESC LIMIT 1
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
        last_plan = db.execute(
            text(
                """
                SELECT plan_name,plan_json,updated_at FROM learning_plans
                WHERE user_id=:user_id ORDER BY updated_at DESC,id DESC LIMIT 1
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
        activity = db.execute(
            text(
                """
                SELECT COUNT(*) AS total,MAX(answered_at) AS last_activity,
                       ROUND(AVG(CASE WHEN answered_at>=DATE_SUB(NOW(),INTERVAL 7 DAY) AND is_correct IS NOT NULL THEN is_correct END)*100,1) AS recent_accuracy,
                       ROUND(AVG(CASE WHEN answered_at>=DATE_SUB(NOW(),INTERVAL 14 DAY) AND answered_at<DATE_SUB(NOW(),INTERVAL 7 DAY) AND is_correct IS NOT NULL THEN is_correct END)*100,1) AS previous_accuracy,
                       SUM(CASE WHEN :last_chat_at IS NOT NULL AND answered_at>:last_chat_at THEN 1 ELSE 0 END) AS since_last_chat
                FROM practice_records WHERE user_id=:user_id
                """
            ),
            {"user_id": user_id, "last_chat_at": last_chat["created_at"] if last_chat else None},
        ).mappings().first()
        recent_results = db.execute(
            text(
                """
                SELECT is_correct FROM practice_records
                WHERE user_id=:user_id AND is_correct IS NOT NULL
                ORDER BY answered_at DESC,id DESC LIMIT 8
                """
            ),
            {"user_id": user_id},
        ).scalars().all()
    consecutive_wrong = 0
    for value in recent_results:
        if bool(value):
            break
        consecutive_wrong += 1
    recent_accuracy = float(activity["recent_accuracy"] or 0) if activity else 0
    previous_accuracy = float(activity["previous_accuracy"]) if activity and activity["previous_accuracy"] is not None else None
    if consecutive_wrong >= 3:
        emotional_state = "frustrated"
    elif previous_accuracy is not None and recent_accuracy <= previous_accuracy - 10:
        emotional_state = "regressing"
    elif previous_accuracy is not None and recent_accuracy >= previous_accuracy + 10:
        emotional_state = "improving"
    elif not activity or not activity["last_activity"]:
        emotional_state = "new"
    else:
        emotional_state = "steady"
    plan_payload: Any = last_plan["plan_json"] if last_plan else None
    if isinstance(plan_payload, str):
        try:
            plan_payload = json.loads(plan_payload)
        except json.JSONDecodeError:
            plan_payload = None
    return {
        "last_conversation": {
            "session_id": str(last_chat["session_id"]) if last_chat else None,
            "topic": str(last_chat["content"] or "")[:160] if last_chat else None,
            "at": _json_safe(last_chat["created_at"]) if last_chat else None,
        },
        "latest_plan": {
            "name": str(last_plan["plan_name"]) if last_plan else None,
            "updated_at": _json_safe(last_plan["updated_at"]) if last_plan else None,
            "plan": plan_payload,
        },
        "activity": {
            "total": int(activity["total"] or 0) if activity else 0,
            "new_attempts_since_last_chat": int(activity["since_last_chat"] or 0) if activity else 0,
            "last_activity": _json_safe(activity["last_activity"]) if activity else None,
            "recent_accuracy": recent_accuracy,
            "previous_accuracy": previous_accuracy,
            "consecutive_wrong": consecutive_wrong,
        },
        "emotional_state": emotional_state,
    }


def _student_record_context(user_id: int, context: ChatContext) -> dict[str, Any]:
    clauses = ["pr.user_id = :user_id"]
    params: dict[str, Any] = {"user_id": user_id}
    if context.record_id:
        clauses.append("pr.id = :record_id")
        params["record_id"] = context.record_id
    elif context.question_id:
        clauses.append("pr.question_id = :question_id")
        params["question_id"] = context.question_id
    else:
        raise HTTPException(status_code=422, detail="题目上下文缺少 question_id 或 record_id。")
    with SessionLocal() as db:
        row = db.execute(
            text(
                f"""
                SELECT pr.id AS record_id, pr.question_id, pr.selected_answer, pr.answer_text,
                       pr.score, pr.is_correct, pr.review_status, pr.mistake_tags, pr.answered_at,
                       q.question_text, q.question_type, q.stage, q.course, q.knowledge_tag,
                       q.fine_tag, q.standard_answer, q.analysis_text, q.key_steps, q.common_errors
                FROM practice_records AS pr
                JOIN questions AS q ON q.id = pr.question_id
                WHERE {' AND '.join(clauses)}
                ORDER BY pr.answered_at DESC, pr.id DESC LIMIT 1
                """
            ),
            params,
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该题目记录不属于当前账号。")
        related = []
        if context.type == "wrong":
            related_rows = db.execute(
                text(
                    """
                    SELECT pr.id AS record_id, q.question_text, q.fine_tag, pr.mistake_tags
                    FROM practice_records AS pr
                    JOIN questions AS q ON q.id = pr.question_id
                    WHERE pr.user_id = :user_id AND pr.is_correct = 0
                      AND q.knowledge_tag = :knowledge_tag AND pr.id <> :record_id
                    ORDER BY pr.answered_at DESC LIMIT 3
                    """
                ),
                {"user_id": user_id, "knowledge_tag": row["knowledge_tag"], "record_id": row["record_id"]},
            ).mappings().all()
            related = [
                {
                    "record_id": int(item["record_id"]),
                    "question_text": str(item["question_text"]),
                    "fine_tag": str(item["fine_tag"]),
                    "mistake_tags": _parse_json_list(item["mistake_tags"]),
                }
                for item in related_rows
            ]
    return {
        "type": context.type,
        "record_id": int(row["record_id"]),
        "question_id": int(row["question_id"]),
        "question_text": str(row["question_text"]),
        "question_type": str(row["question_type"]),
        "stage": str(row["stage"]),
        "course": str(row["course"]),
        "knowledge_tag": str(row["knowledge_tag"]),
        "fine_tag": str(row["fine_tag"]),
        "student_answer": row["selected_answer"] or row["answer_text"] or "仅提交图片作答",
        "score": float(row["score"]) if row["score"] is not None else None,
        "is_correct": bool(row["is_correct"]) if row["is_correct"] is not None else None,
        "review_status": str(row["review_status"]),
        "mistake_tags": _parse_json_list(row["mistake_tags"]),
        "standard_answer": str(row["standard_answer"] or ""),
        "analysis_text": str(row["analysis_text"] or ""),
        "key_steps": _parse_json_list(row["key_steps"]),
        "common_errors": _parse_json_list(row["common_errors"]),
        "answered_at": _json_safe(row["answered_at"]),
        "recent_similar_wrong": related,
    }


def _student_assignment_context(user_id: int, context: ChatContext) -> dict[str, Any]:
    if not context.assignment_id:
        raise HTTPException(status_code=422, detail="作业上下文缺少 assignment_id。")
    with SessionLocal() as db:
        assignment = db.execute(
            text(
                """
                SELECT a.id, a.title, a.description, a.status, a.due_at, c.name AS class_name,
                       c.stage, c.course, aa.id AS attempt_id, aa.status AS attempt_status,
                       aa.total_score, aa.max_score, aa.submitted_at
                FROM assignments AS a
                JOIN classes AS c ON c.id = a.class_id
                JOIN class_members AS cm ON cm.class_id = c.id AND cm.student_id = :user_id AND cm.status = 'active'
                LEFT JOIN assignment_attempts AS aa ON aa.id = (
                  SELECT latest.id FROM assignment_attempts AS latest
                  WHERE latest.assignment_id = a.id AND latest.user_id = :user_id
                  ORDER BY latest.attempt_no DESC LIMIT 1
                )
                WHERE a.id = :assignment_id AND a.status IN ('published', 'closed') LIMIT 1
                """
            ),
            {"user_id": user_id, "assignment_id": context.assignment_id},
        ).mappings().first()
        if not assignment:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该作业不属于当前账号所在班级。")
        answers = []
        if assignment["attempt_id"]:
            rows = db.execute(
                text(
                    """
                    SELECT q.question_text, q.knowledge_tag, ans.selected_answer, ans.answer_text,
                           ans.score, ans.review_status, ans.teacher_feedback
                    FROM assignment_answers AS ans
                    JOIN assignment_questions AS aq ON aq.id = ans.assignment_question_id
                    JOIN questions AS q ON q.id = aq.question_id
                    WHERE ans.attempt_id = :attempt_id ORDER BY aq.sort_order
                    """
                ),
                {"attempt_id": assignment["attempt_id"]},
            ).mappings().all()
            answers = [
                {
                    "question_text": str(row["question_text"]),
                    "knowledge_tag": str(row["knowledge_tag"]),
                    "student_answer": row["selected_answer"] or row["answer_text"] or "图片作答",
                    "score": float(row["score"]) if row["score"] is not None else None,
                    "review_status": str(row["review_status"]),
                    "teacher_feedback": row["teacher_feedback"],
                }
                for row in rows[:20]
            ]
    return {
        "type": "assignment",
        "assignment_id": int(assignment["id"]),
        "title": str(assignment["title"]),
        "description": str(assignment["description"] or ""),
        "class_name": str(assignment["class_name"]),
        "stage": str(assignment["stage"]),
        "course": str(assignment["course"]),
        "due_at": _json_safe(assignment["due_at"]),
        "attempt_status": assignment["attempt_status"],
        "score": float(assignment["total_score"] or 0) if assignment["total_score"] is not None else None,
        "max_score": float(assignment["max_score"] or 0) if assignment["max_score"] is not None else None,
        "answers": answers,
    }


def _teacher_context(teacher_id: int, context: ChatContext | None) -> dict[str, Any]:
    with SessionLocal() as db:
        if context and context.type == "class":
            if not context.class_id:
                raise HTTPException(status_code=422, detail="班级上下文缺少 class_id。")
            row = db.execute(
                text(
                    """
                    SELECT c.id, c.name, c.stage, c.course,
                           COUNT(DISTINCT cm.student_id) AS student_count,
                           COUNT(pr.id) AS attempts,
                           ROUND(AVG(CASE WHEN pr.is_correct IS NOT NULL THEN pr.is_correct END) * 100, 1) AS accuracy,
                           SUM(CASE WHEN pr.review_status = 'pending' THEN 1 ELSE 0 END) AS pending_review
                    FROM classes AS c
                    LEFT JOIN class_members AS cm ON cm.class_id = c.id AND cm.status = 'active'
                    LEFT JOIN practice_records AS pr ON pr.user_id = cm.student_id
                    WHERE c.id = :class_id AND c.teacher_id = :teacher_id AND c.status = 'active'
                    GROUP BY c.id, c.name, c.stage, c.course
                    """
                ),
                {"class_id": context.class_id, "teacher_id": teacher_id},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该班级不属于当前教师。")
            return {"type": "class", **dict(row)}
        if context and context.type == "student":
            if not context.student_id:
                raise HTTPException(status_code=422, detail="学生上下文缺少 student_id。")
            row = db.execute(
                text(
                    """
                    SELECT u.id, u.username, u.nickname, u.current_stage, COUNT(pr.id) AS attempts,
                           ROUND(AVG(CASE WHEN pr.is_correct IS NOT NULL THEN pr.is_correct END) * 100, 1) AS accuracy,
                           SUM(CASE WHEN pr.review_status = 'pending' THEN 1 ELSE 0 END) AS pending_review
                    FROM users AS u
                    JOIN class_members AS cm ON cm.student_id = u.id AND cm.status = 'active'
                    JOIN classes AS c ON c.id = cm.class_id AND c.teacher_id = :teacher_id AND c.status = 'active'
                    LEFT JOIN practice_records AS pr ON pr.user_id = u.id
                    WHERE u.id = :student_id
                    GROUP BY u.id, u.username, u.nickname, u.current_stage
                    """
                ),
                {"teacher_id": teacher_id, "student_id": context.student_id},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该学生不属于当前教师管理范围。")
            return {"type": "student", **dict(row)}
        rows = db.execute(
            text(
                """
                SELECT c.id, c.name, c.stage, c.course, COUNT(DISTINCT cm.student_id) AS student_count
                FROM classes AS c
                LEFT JOIN class_members AS cm ON cm.class_id = c.id AND cm.status = 'active'
                WHERE c.teacher_id = :teacher_id AND c.status = 'active'
                GROUP BY c.id, c.name, c.stage, c.course ORDER BY c.created_at DESC LIMIT 12
                """
            ),
            {"teacher_id": teacher_id},
        ).mappings().all()
    return {"type": "teacher_overview", "classes": [dict(row) for row in rows]}


def build_chat_context_sync(user_id: int, role: str, context: ChatContext | None) -> dict[str, Any]:
    if role in {"teacher", "admin"}:
        return _teacher_context(user_id, context)
    if context and context.type in {"question", "wrong"}:
        result = _student_record_context(user_id, context)
    elif context and context.type == "assignment":
        result = _student_assignment_context(user_id, context)
    elif context and context.type == "plan":
        result = {"type": "plan", **_study_roadmap_sync(user_id)}
    else:
        result = {"type": "diagnosis", **_diagnose_sync(user_id)}
    result["behavior_backtrace"] = _student_behavior_backtrace(user_id)
    return result


def serialize_authorized_context(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=False, default=str)[:24000]
