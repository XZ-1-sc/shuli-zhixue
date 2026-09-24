import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text

from ..api.routes.teacher import _owned_class
from ..database.repositories.teacher_assignments import _owned_assignment
from ..database.session import SessionLocal


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [str(value)]
    return [str(item) for item in parsed] if isinstance(parsed, list) else [str(parsed)]


def _accuracy(correct: int, total: int) -> float:
    return round(correct / total * 100, 1) if total else 0.0


def class_dashboard_sync(teacher_id: int, class_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        class_row = _owned_class(db, teacher_id, class_id)
        members = db.execute(
            text("SELECT u.id,u.username,COALESCE(u.nickname,u.username) nickname FROM class_members cm JOIN users u ON u.id=cm.student_id WHERE cm.class_id=:class_id AND cm.status='active' ORDER BY u.username"),
            {"class_id": class_id},
        ).mappings().all()
        rows = db.execute(
            text(
                """
                SELECT pr.user_id,pr.is_correct,pr.mistake_tags,pr.time_spent_seconds,pr.answered_at,
                       q.knowledge_tag,q.fine_tag,q.question_type
                FROM class_members cm
                JOIN practice_records pr ON pr.user_id=cm.student_id
                JOIN questions q ON q.id=pr.question_id
                WHERE cm.class_id=:class_id AND cm.status='active'
                  AND pr.answered_at>=DATE_SUB(CURDATE(),INTERVAL 89 DAY)
                  AND pr.mastery_evidence='formal'
                ORDER BY pr.answered_at
                """
            ),
            {"class_id": class_id},
        ).mappings().all()

    today = date.today()
    daily = {today - timedelta(days=offset): {"attempts": 0, "correct": 0, "graded": 0} for offset in range(6, -1, -1)}
    knowledge: dict[str, dict[str, int]] = defaultdict(lambda: {"attempts": 0, "correct": 0})
    matrix: dict[int, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"attempts": 0, "wrong": 0}))
    reasons: Counter[str] = Counter()
    activity: dict[int, dict[str, Any]] = defaultdict(lambda: {"attempts_7d": 0, "last_active": None, "seconds_7d": 0})
    for row in rows:
        answered = row["answered_at"]
        answered_date = answered.date() if answered else None
        tag = str(row["fine_tag"] or row["knowledge_tag"] or "未分类")
        if answered_date in daily:
            daily[answered_date]["attempts"] += 1
            activity[int(row["user_id"])]["attempts_7d"] += 1
            activity[int(row["user_id"])]["seconds_7d"] += int(row["time_spent_seconds"] or 0)
            if row["is_correct"] is not None:
                daily[answered_date]["graded"] += 1
                daily[answered_date]["correct"] += int(row["is_correct"])
        current_last = activity[int(row["user_id"])]["last_active"]
        if answered and (not current_last or answered > current_last):
            activity[int(row["user_id"])]["last_active"] = answered
        if row["is_correct"] is not None:
            knowledge[tag]["attempts"] += 1
            knowledge[tag]["correct"] += int(row["is_correct"])
            matrix[int(row["user_id"])][tag]["attempts"] += 1
            matrix[int(row["user_id"])][tag]["wrong"] += 0 if bool(row["is_correct"]) else 1
            if not bool(row["is_correct"]):
                reasons.update(_json_list(row["mistake_tags"]) or ["知识点需巩固"])

    mastery = [{"knowledge_tag": tag, **stat, "accuracy": _accuracy(stat["correct"], stat["attempts"])} for tag, stat in knowledge.items()]
    mastery.sort(key=lambda item: (item["accuracy"], -item["attempts"]))
    top_tags = [item["knowledge_tag"] for item in sorted(mastery, key=lambda item: (-item["attempts"], item["accuracy"]))[:12]]
    heatmap = []
    student_activity = []
    for member in members:
        student_id = int(member["id"])
        heatmap.append({
            "student_id": student_id,
            "student": str(member["nickname"]),
            "cells": [{"knowledge_tag": tag, "attempts": matrix[student_id][tag]["attempts"], "error_rate": _accuracy(matrix[student_id][tag]["wrong"], matrix[student_id][tag]["attempts"])} for tag in top_tags],
        })
        stat = activity[student_id]
        student_activity.append({
            "student_id": student_id,
            "student": str(member["nickname"]),
            "attempts_7d": stat["attempts_7d"],
            "study_minutes_7d": round(stat["seconds_7d"] / 60, 1),
            "last_active": stat["last_active"].isoformat() if stat["last_active"] else None,
        })
    trend = [{"date": day.isoformat(), **stat, "accuracy": _accuracy(stat["correct"], stat["graded"])} for day, stat in daily.items()]
    return {
        "class": {"id": int(class_row["id"]), "name": str(class_row["name"]), "course": str(class_row["course"])},
        "trend_7d": trend,
        "knowledge_mastery": mastery,
        "knowledge_top": sorted(mastery, key=lambda item: (-item["accuracy"], -item["attempts"]))[:5],
        "knowledge_bottom": mastery[:5],
        "mistake_distribution": [{"reason": key, "count": value} for key, value in reasons.most_common(10)],
        "heatmap": {"columns": top_tags, "rows": heatmap},
        "student_activity": sorted(student_activity, key=lambda item: (item["attempts_7d"], item["student"])),
    }


def assignment_question_stats_sync(teacher_id: int, assignment_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        assignment = _owned_assignment(db, teacher_id, assignment_id)
        rows = db.execute(
            text(
                """
                SELECT aq.question_id,aq.sort_order,q.question_text,q.question_type,q.knowledge_tag,
                       ans.selected_answer,ans.is_correct,ans.time_spent_seconds,pr.mistake_tags
                FROM assignment_questions aq
                JOIN questions q ON q.id=aq.question_id
                LEFT JOIN assignment_answers ans ON ans.assignment_question_id=aq.id AND ans.answered_at IS NOT NULL
                LEFT JOIN practice_records pr ON pr.id=ans.practice_record_id
                WHERE aq.assignment_id=:assignment_id ORDER BY aq.sort_order,ans.id
                """
            ),
            {"assignment_id": assignment_id},
        ).mappings().all()
    grouped: dict[int, list[Any]] = defaultdict(list)
    meta: dict[int, Any] = {}
    for row in rows:
        qid = int(row["question_id"])
        meta[qid] = row
        if row["is_correct"] is not None or row["selected_answer"] is not None:
            grouped[qid].append(row)
    items = []
    for qid, row in sorted(meta.items(), key=lambda item: int(item[1]["sort_order"])):
        answers = grouped[qid]
        graded = [item for item in answers if item["is_correct"] is not None]
        wrong_options = Counter(str(item["selected_answer"]).upper() for item in answers if item["is_correct"] == 0 and item["selected_answer"])
        reasons = Counter(reason for item in answers if item["is_correct"] == 0 for reason in (_json_list(item["mistake_tags"]) or ["知识点需巩固"]))
        items.append({
            "question_id": qid, "sort_order": int(row["sort_order"]), "question_text": str(row["question_text"]),
            "question_type": str(row["question_type"]), "knowledge_tag": str(row["knowledge_tag"]),
            "answered_count": len(answers), "correct_rate": _accuracy(sum(int(item["is_correct"]) for item in graded), len(graded)),
            "error_rate": round(100 - _accuracy(sum(int(item["is_correct"]) for item in graded), len(graded)), 1) if graded else 0.0,
            "average_seconds": round(sum(int(item["time_spent_seconds"] or 0) for item in answers) / len(answers), 1) if answers else 0.0,
            "wrong_options": [{"option": option, "count": count} for option, count in wrong_options.most_common()],
            "mistake_distribution": [{"reason": reason, "count": count} for reason, count in reasons.most_common(6)],
        })
    return {"assignment_id": assignment_id, "title": str(assignment["title"]), "items": items}


def question_insight_sync(teacher_id: int, question_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        question = db.execute(text("SELECT id,question_text,question_type,knowledge_tag FROM questions WHERE id=:id AND deleted_at IS NULL"), {"id": question_id}).mappings().first()
        if not question:
            raise HTTPException(status_code=404, detail="题目不存在。")
        rows = db.execute(
            text(
                """
                SELECT DISTINCT pr.id,pr.selected_answer,pr.is_correct,pr.time_spent_seconds,pr.mistake_tags
                FROM classes c JOIN class_members cm ON cm.class_id=c.id AND cm.status='active'
                JOIN practice_records pr ON pr.user_id=cm.student_id AND pr.question_id=:question_id
                WHERE c.teacher_id=:teacher_id AND c.status='active' AND pr.mastery_evidence='formal'
                """
            ),
            {"teacher_id": teacher_id, "question_id": question_id},
        ).mappings().all()
    graded = [row for row in rows if row["is_correct"] is not None]
    wrong_options = Counter(str(row["selected_answer"]).upper() for row in graded if row["is_correct"] == 0 and row["selected_answer"])
    reasons = Counter(reason for row in graded if row["is_correct"] == 0 for reason in (_json_list(row["mistake_tags"]) or ["知识点需巩固"]))
    rate = _accuracy(sum(int(row["is_correct"]) for row in graded), len(graded))
    dominant = wrong_options.most_common(1)[0] if wrong_options else None
    concept_signal = bool(rate < 60 and dominant and dominant[1] >= max(2, round(len(graded) * 0.35)))
    return {
        "question_id": question_id, "attempts": len(rows), "graded": len(graded), "correct_rate": rate,
        "average_seconds": round(sum(int(row["time_spent_seconds"] or 0) for row in rows) / len(rows), 1) if rows else 0.0,
        "wrong_options": [{"option": option, "count": count} for option, count in wrong_options.most_common()],
        "mistake_distribution": [{"reason": reason, "count": count} for reason, count in reasons.most_common(8)],
        "concept_blind_spot": concept_signal,
        "insight": f"错误主要集中在选项 {dominant[0]}，更像概念边界混淆。" if concept_signal else "当前样本未形成稳定的单一干扰项集中信号。",
    }


def common_issues_sync(teacher_id: int, class_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        _owned_class(db, teacher_id, class_id)
        rows = db.execute(
            text(
                """
                SELECT q.id AS question_id,q.question_text,q.knowledge_tag,q.fine_tag,
                       COUNT(DISTINCT pr.user_id) AS student_count,COUNT(pr.id) AS wrong_count
                FROM class_members cm JOIN practice_records pr ON pr.user_id=cm.student_id AND pr.is_correct=0
                JOIN questions q ON q.id=pr.question_id
                WHERE cm.class_id=:class_id AND cm.status='active' AND pr.mastery_evidence='formal'
                  AND pr.answered_at>=DATE_SUB(NOW(),INTERVAL 90 DAY)
                GROUP BY q.id,q.question_text,q.knowledge_tag,q.fine_tag
                HAVING COUNT(DISTINCT pr.user_id)>=3
                ORDER BY student_count DESC,wrong_count DESC LIMIT 20
                """
            ),
            {"class_id": class_id},
        ).mappings().all()
    return {"class_id": class_id, "items": [{**dict(row), "question_id": int(row["question_id"]), "student_count": int(row["student_count"]), "wrong_count": int(row["wrong_count"])} for row in rows]}


def profile_analytics_sync(user_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT pr.is_correct,pr.mistake_tags,pr.time_spent_seconds,pr.answered_at,
                       q.question_type,q.knowledge_tag,q.fine_tag
                FROM practice_records pr JOIN questions q ON q.id=pr.question_id
                WHERE pr.user_id=:user_id AND pr.mastery_evidence='formal'
                  AND pr.answered_at>=DATE_SUB(CURDATE(),INTERVAL 89 DAY)
                ORDER BY pr.answered_at
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
    by_type: dict[str, list[int]] = defaultdict(list)
    by_knowledge: dict[str, list[int]] = defaultdict(list)
    reasons: Counter[str] = Counter()
    daily: dict[str, list[int]] = defaultdict(list)
    heat: Counter[str] = Counter()
    for row in rows:
        day = row["answered_at"].date().isoformat() if row["answered_at"] else ""
        if day:
            heat[day] += 1
        if row["is_correct"] is None:
            continue
        value = int(row["is_correct"])
        by_type[str(row["question_type"])].append(value)
        by_knowledge[str(row["fine_tag"] or row["knowledge_tag"] or "未分类")].append(value)
        daily[day].append(value)
        if not value:
            reasons.update(_json_list(row["mistake_tags"]) or ["知识点需巩固"])
    return {
        "by_type": [{"name": key, "attempts": len(values), "accuracy": _accuracy(sum(values), len(values))} for key, values in by_type.items()],
        "by_knowledge": sorted([{"name": key, "attempts": len(values), "accuracy": _accuracy(sum(values), len(values))} for key, values in by_knowledge.items()], key=lambda item: (item["accuracy"], -item["attempts"]))[:20],
        "mistake_distribution": [{"reason": key, "count": value} for key, value in reasons.most_common(10)],
        "accuracy_trend": [{"date": key, "accuracy": _accuracy(sum(values), len(values)), "attempts": len(values)} for key, values in sorted(daily.items())[-30:]],
        "practice_heatmap": [{"date": key, "count": value} for key, value in sorted(heat.items())],
        "mastery_evidence": {"formal": len(rows)},
    }
