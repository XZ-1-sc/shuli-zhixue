from typing import Any

from sqlalchemy import text

from ..session import SessionLocal
from ...api.routes.teacher import _owned_class
from ...api.teacher_schemas import TYPE_LABELS
from .teacher_common import _iso, _managed_student


def _student_list_sync(teacher_id: int, class_id: int | None, search: str | None) -> dict[str, Any]:
    clauses = ["c.teacher_id = :teacher_id", "c.status = 'active'", "cm.status = 'active'"]
    params: dict[str, Any] = {"teacher_id": teacher_id}
    if class_id:
        clauses.append("c.id = :class_id")
        params["class_id"] = class_id
    if search:
        clauses.append("(u.username LIKE :search OR COALESCE(u.nickname, '') LIKE :search)")
        params["search"] = f"%{search.strip()}%"
    with SessionLocal() as db:
        if class_id:
            _owned_class(db, teacher_id, class_id)
        rows = db.execute(
            text(
                f"""
                SELECT u.id, u.username, u.nickname, u.current_stage,
                       GROUP_CONCAT(DISTINCT c.name ORDER BY c.name SEPARATOR '、') AS class_names,
                       (SELECT COUNT(*) FROM practice_records pr WHERE pr.user_id=u.id) AS practice_count,
                       (SELECT ROUND(AVG(CASE WHEN pr.is_correct IS NOT NULL THEN pr.is_correct END) * 100, 1)
                          FROM practice_records pr WHERE pr.user_id=u.id) AS accuracy,
                       (SELECT COALESCE(SUM(pr.time_spent_seconds),0) FROM practice_records pr WHERE pr.user_id=u.id) AS study_seconds,
                       (SELECT COUNT(*) FROM practice_records pr WHERE pr.user_id=u.id AND pr.review_status='pending') AS pending_review,
                       (SELECT MAX(pr.answered_at) FROM practice_records pr WHERE pr.user_id=u.id) AS last_active,
                       (SELECT COUNT(*) FROM assignment_attempts aa JOIN assignments a ON a.id=aa.assignment_id
                          WHERE aa.user_id=u.id AND a.teacher_id=:teacher_id
                            AND aa.status IN ('submitted','grading','graded','returned')) AS assignment_count
                FROM class_members AS cm
                JOIN classes AS c ON c.id = cm.class_id
                JOIN users AS u ON u.id = cm.student_id
                WHERE {' AND '.join(clauses)}
                GROUP BY u.id, u.username, u.nickname, u.current_stage
                ORDER BY last_active DESC, u.username
                """
            ),
            params,
        ).mappings().all()
    items = [
        {
            "id": int(row["id"]),
            "username": str(row["username"]),
            "nickname": str(row["nickname"] or row["username"]),
            "current_stage": str(row["current_stage"] or "大一"),
            "class_names": str(row["class_names"] or ""),
            "practice_count": int(row["practice_count"] or 0),
            "accuracy": float(row["accuracy"] or 0),
            "study_hours": round(int(row["study_seconds"] or 0) / 3600, 1),
            "pending_review": int(row["pending_review"] or 0),
            "assignment_count": int(row["assignment_count"] or 0),
            "last_active": _iso(row["last_active"]),
        }
        for row in rows
    ]
    return {"items": items, "total": len(items)}

def _student_detail_sync(teacher_id: int, student_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        _managed_student(db, teacher_id, student_id)
        profile = db.execute(
            text(
                """
                SELECT u.id, u.username, u.nickname, u.current_stage, u.created_at,
                       GROUP_CONCAT(DISTINCT c.name ORDER BY c.name SEPARATOR '、') AS class_names,
                       (SELECT COUNT(*) FROM practice_records pr WHERE pr.user_id=u.id) AS practice_count,
                       (SELECT ROUND(AVG(CASE WHEN pr.is_correct IS NOT NULL THEN pr.is_correct END) * 100, 1)
                          FROM practice_records pr WHERE pr.user_id=u.id) AS accuracy,
                       (SELECT COALESCE(SUM(pr.time_spent_seconds),0) FROM practice_records pr WHERE pr.user_id=u.id) AS study_seconds,
                       (SELECT MAX(pr.answered_at) FROM practice_records pr WHERE pr.user_id=u.id) AS last_active
                FROM users AS u
                JOIN class_members AS cm ON cm.student_id = u.id AND cm.status = 'active'
                JOIN classes AS c ON c.id = cm.class_id AND c.teacher_id = :teacher_id AND c.status = 'active'
                WHERE u.id = :student_id
                GROUP BY u.id, u.username, u.nickname, u.current_stage, u.created_at
                """
            ),
            {"teacher_id": teacher_id, "student_id": student_id},
        ).mappings().one()
        courses = db.execute(
            text(
                """
                SELECT q.course, COUNT(*) AS attempts,
                       ROUND(AVG(CASE WHEN pr.is_correct IS NOT NULL THEN pr.is_correct END) * 100, 1) AS accuracy,
                       SUM(CASE WHEN pr.is_correct = 0 THEN 1 ELSE 0 END) AS wrong_count
                FROM practice_records AS pr
                JOIN questions AS q ON q.id = pr.question_id
                WHERE pr.user_id = :student_id
                GROUP BY q.course
                ORDER BY attempts DESC, accuracy ASC
                """
            ),
            {"student_id": student_id},
        ).mappings().all()
        weak = db.execute(
            text(
                """
                SELECT q.course, q.knowledge_tag, q.fine_tag, COUNT(*) AS attempts,
                       ROUND(AVG(CASE WHEN pr.is_correct IS NOT NULL THEN pr.is_correct END) * 100, 1) AS mastery
                FROM practice_records AS pr
                JOIN questions AS q ON q.id = pr.question_id
                WHERE pr.user_id = :student_id
                GROUP BY q.course, q.knowledge_tag, q.fine_tag
                ORDER BY mastery ASC, attempts DESC
                LIMIT 8
                """
            ),
            {"student_id": student_id},
        ).mappings().all()
        recent = db.execute(
            text(
                """
                SELECT pr.id, q.course, q.knowledge_tag, q.fine_tag, q.question_type,
                       pr.score, pr.is_correct, pr.review_status, pr.practice_mode, pr.answered_at
                FROM practice_records AS pr
                JOIN questions AS q ON q.id = pr.question_id
                WHERE pr.user_id = :student_id
                ORDER BY pr.answered_at DESC LIMIT 20
                """
            ),
            {"student_id": student_id},
        ).mappings().all()
        assignments = db.execute(
            text(
                """
                SELECT a.id, a.title, c.name AS class_name, a.due_at, aa.status,
                       aa.total_score, aa.max_score, aa.submitted_at
                FROM assignments AS a
                JOIN classes AS c ON c.id = a.class_id AND c.teacher_id = :teacher_id
                JOIN class_members AS cm ON cm.class_id = c.id AND cm.student_id = :student_id AND cm.status = 'active'
                LEFT JOIN assignment_attempts AS aa ON aa.assignment_id = a.id AND aa.user_id = :student_id
                WHERE a.status IN ('published','closed')
                ORDER BY a.created_at DESC LIMIT 20
                """
            ),
            {"teacher_id": teacher_id, "student_id": student_id},
        ).mappings().all()
        goal = db.execute(
            text("SELECT target_stage, target_course, weekly_hours, exam_date FROM user_goal_settings WHERE user_id = :student_id"),
            {"student_id": student_id},
        ).mappings().first()
    return {
        "profile": {
            "id": int(profile["id"]),
            "username": str(profile["username"]),
            "nickname": str(profile["nickname"] or profile["username"]),
            "current_stage": str(profile["current_stage"] or "大一"),
            "class_names": str(profile["class_names"] or ""),
            "practice_count": int(profile["practice_count"] or 0),
            "accuracy": float(profile["accuracy"] or 0),
            "study_hours": round(int(profile["study_seconds"] or 0) / 3600, 1),
            "last_active": _iso(profile["last_active"]),
            "created_at": _iso(profile["created_at"]),
        },
        "goal": dict(goal) if goal else None,
        "courses": [
            {"course": str(row["course"]), "attempts": int(row["attempts"]), "accuracy": float(row["accuracy"] or 0), "wrong_count": int(row["wrong_count"] or 0)}
            for row in courses
        ],
        "weak_points": [
            {"course": str(row["course"]), "knowledge_tag": str(row["knowledge_tag"]), "fine_tag": str(row["fine_tag"]), "attempts": int(row["attempts"]), "mastery": float(row["mastery"] or 0)}
            for row in weak
        ],
        "recent_records": [
            {**dict(row), "id": int(row["id"]), "score": float(row["score"] or 0) if row["score"] is not None else None, "is_correct": bool(row["is_correct"]) if row["is_correct"] is not None else None, "answered_at": _iso(row["answered_at"]), "type_label": TYPE_LABELS.get(str(row["question_type"]), str(row["question_type"]))}
            for row in recent
        ],
        "assignments": [
            {**dict(row), "id": int(row["id"]), "total_score": float(row["total_score"] or 0) if row["total_score"] is not None else None, "max_score": float(row["max_score"] or 0), "due_at": _iso(row["due_at"]), "submitted_at": _iso(row["submitted_at"])}
            for row in assignments
        ],
    }
