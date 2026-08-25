import json
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import text

from ..api.routes.teacher import _owned_class
from ..api.utils import _parse_json_list
from ..database.repositories.teacher_assignments import _owned_assignment
from ..database.session import SessionLocal


BUCKETS = ((90, 101, "90-100"), (80, 90, "80-89"), (70, 80, "70-79"), (60, 70, "60-69"), (0, 60, "0-59"))


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _reason_values(value: Any) -> list[str]:
    values = _parse_json_list(value)
    return [str(item).strip() for item in values if str(item).strip()][:5]


def _build_analytics(members: list[Any], answers: list[Any]) -> dict[str, Any]:
    student_answers: dict[int, list[Any]] = defaultdict(list)
    knowledge_answers: dict[str, list[Any]] = defaultdict(list)
    reason_counts: Counter[str] = Counter()
    for row in answers:
        student_id = int(row["student_id"])
        student_answers[student_id].append(row)
        knowledge_answers[str(row["knowledge_tag"] or "未分类")].append(row)
        if row["is_correct"] == 0:
            reasons = _reason_values(row["record_mistakes"]) or _reason_values(row["question_mistakes"]) or ["知识点需巩固"]
            reason_counts.update(reasons)

    students = []
    for member in members:
        student_id = int(member["student_id"])
        rows = student_answers.get(student_id, [])
        graded = [row for row in rows if row["is_correct"] is not None]
        accuracy = round(sum(int(row["is_correct"]) for row in graded) / len(graded) * 100, 1) if graded else 0.0
        by_knowledge: dict[str, list[int]] = defaultdict(list)
        for row in graded:
            by_knowledge[str(row["knowledge_tag"] or "未分类")].append(int(row["is_correct"]))
        weak = sorted(
            ((tag, sum(values) / len(values)) for tag, values in by_knowledge.items()),
            key=lambda item: (item[1], item[0]),
        )
        students.append(
            {
                "student_id": student_id,
                "username": str(member["username"]),
                "nickname": str(member["nickname"]),
                "accuracy": accuracy,
                "attempts": len(rows),
                "weak_knowledge": [tag for tag, _ in weak[:3]],
                "last_active": _iso(max((row["answered_at"] for row in rows if row["answered_at"]), default=None)),
            }
        )

    distribution = []
    active_students = [item for item in students if item["attempts"] > 0]
    for low, high, label in BUCKETS:
        distribution.append({"bucket": label, "count": sum(1 for item in active_students if low <= item["accuracy"] < high)})
    mastery = []
    for tag, rows in knowledge_answers.items():
        graded = [row for row in rows if row["is_correct"] is not None]
        accuracy = round(sum(int(row["is_correct"]) for row in graded) / len(graded) * 100, 1) if graded else 0.0
        mastery.append({"knowledge_tag": tag, "accuracy": accuracy, "attempts": len(rows)})
    mastery.sort(key=lambda item: (item["accuracy"], -item["attempts"], item["knowledge_tag"]))
    return {
        "accuracy_distribution": distribution,
        "knowledge_mastery": mastery,
        "reason_distribution": [{"reason": reason, "count": count} for reason, count in reason_counts.most_common(12)],
        "students": students,
    }


def assignment_analytics_sync(teacher_id: int, assignment_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        assignment = _owned_assignment(db, teacher_id, assignment_id)
        members = db.execute(
            text(
                """
                SELECT u.id AS student_id,u.username,COALESCE(u.nickname,u.username) AS nickname
                FROM class_members cm JOIN users u ON u.id=cm.student_id
                WHERE cm.class_id=:class_id AND cm.status='active' ORDER BY u.username
                """
            ),
            {"class_id": assignment["class_id"]},
        ).mappings().all()
        answers = db.execute(
            text(
                """
                SELECT aa.user_id AS student_id,ans.is_correct,q.knowledge_tag,
                       pr.mistake_tags AS record_mistakes,q.mistake_tags AS question_mistakes,
                       COALESCE(pr.answered_at,ans.answered_at) AS answered_at
                FROM assignment_attempts aa
                JOIN assignment_answers ans ON ans.attempt_id=aa.id
                JOIN assignment_questions aq ON aq.id=ans.assignment_question_id
                JOIN questions q ON q.id=aq.question_id
                LEFT JOIN practice_records pr ON pr.id=ans.practice_record_id
                WHERE aa.assignment_id=:assignment_id AND aa.submitted_at IS NOT NULL
                """
            ),
            {"assignment_id": assignment_id},
        ).mappings().all()
    return {"scope": "assignment", "assignment_id": assignment_id, **_build_analytics(list(members), list(answers))}


def class_analytics_sync(teacher_id: int, class_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        _owned_class(db, teacher_id, class_id)
        members = db.execute(
            text(
                """
                SELECT u.id AS student_id,u.username,COALESCE(u.nickname,u.username) AS nickname
                FROM class_members cm JOIN users u ON u.id=cm.student_id
                WHERE cm.class_id=:class_id AND cm.status='active' ORDER BY u.username
                """
            ),
            {"class_id": class_id},
        ).mappings().all()
        answers = db.execute(
            text(
                """
                SELECT pr.user_id AS student_id,pr.is_correct,q.knowledge_tag,
                       pr.mistake_tags AS record_mistakes,q.mistake_tags AS question_mistakes,pr.answered_at
                FROM class_members cm
                JOIN practice_records pr ON pr.user_id=cm.student_id
                JOIN questions q ON q.id=pr.question_id
                WHERE cm.class_id=:class_id AND cm.status='active'
                  AND pr.answered_at>=DATE_SUB(NOW(),INTERVAL 90 DAY)
                """
            ),
            {"class_id": class_id},
        ).mappings().all()
    return {"scope": "class", "class_id": class_id, **_build_analytics(list(members), list(answers))}
