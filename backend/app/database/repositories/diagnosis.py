import math
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..session import SessionLocal
from ...api.schemas import GoalRequest
from ...api.utils import _json_safe, _parse_json_list, _parse_json_object
from .common import _get_user_exists
from .questions import _question_select_sql, _random_questions_sync, _row_to_question
from .stages import _stages_sync


def _recent_records_sync(user_id: int, limit: int = 50) -> list[dict[str, Any]]:
    query = text(
        """
        SELECT
          pr.id,
          pr.task_id,
          pr.question_id,
          pr.selected_answer,
          pr.answer_text,
          pr.is_correct,
          pr.score,
          pr.mistake_tags AS record_mistake_tags,
          pr.time_spent_seconds,
          pr.practice_mode,
          pr.answered_at,
          q.stage,
          q.course,
          q.knowledge_tag,
          q.fine_tag,
          q.question_type,
          q.difficulty
        FROM practice_records AS pr
        JOIN questions AS q ON q.id = pr.question_id
        WHERE pr.user_id = :user_id
        ORDER BY pr.answered_at DESC, pr.id DESC
        LIMIT :limit
        """
    )
    try:
        with SessionLocal() as db:
            rows = db.execute(query, {"user_id": user_id, "limit": limit}).mappings().all()
    except SQLAlchemyError:
        return []

    records = []
    for row in rows:
        item = dict(row)
        item["answered_at"] = _json_safe(item.get("answered_at"))
        item["mistake_tags"] = _parse_json_list(item.pop("record_mistake_tags", None))
        records.append(item)
    return records

def _diagnose_sync(user_id: int) -> dict[str, Any]:
    all_records = _recent_records_sync(user_id, 200)
    records = [record for record in all_records if record.get("is_correct") is not None]
    if not all_records:
        return {
            "user_id": user_id,
            "recent_record_count": 0,
            "summary": "暂无做题记录。建议先完成一次首测，系统会根据课程和知识点正确率生成个性化规划。",
            "course_scores": [],
            "weak_points": [],
            "radar": [],
        }
    if not records:
        return {
            "user_id": user_id,
            "recent_record_count": len(all_records),
            "graded_record_count": 0,
            "pending_review_count": len(all_records),
            "summary": "作答图片已提交，正在等待教师复核。复核完成后系统会生成薄弱点和学习计划。",
            "course_scores": [],
            "weak_points": [],
            "radar": [],
        }

    stats: dict[str, dict[str, Any]] = {}
    knowledge_stats: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in records:
        course = str(record["course"])
        stats.setdefault(course, {"course": course, "stage": record["stage"], "total": 0, "correct": 0})
        stats[course]["total"] += 1
        stats[course]["correct"] += int(bool(record["is_correct"]))

        key = (str(record["stage"]), course, str(record["knowledge_tag"]))
        knowledge_stats.setdefault(
            key,
            {
                "stage": str(record["stage"]),
                "course": course,
                "knowledge_tag": str(record["knowledge_tag"]),
                "fine_tag": str(record["fine_tag"]),
                "total": 0,
                "correct": 0,
                "time_spent_seconds": 0,
            },
        )
        knowledge_stats[key]["total"] += 1
        knowledge_stats[key]["correct"] += int(bool(record["is_correct"]))
        knowledge_stats[key]["time_spent_seconds"] += int(record.get("time_spent_seconds") or 0)

    course_scores = []
    for item in stats.values():
        score = round(item["correct"] / item["total"] * 100)
        course_scores.append({**item, "score": score, "accuracy": score, "weak": score < 65})
    course_scores.sort(key=lambda item: (item["score"], -item["total"]))

    weak_points = []
    for item in knowledge_stats.values():
        score = round(item["correct"] / item["total"] * 100)
        weak_points.append(
            {
                "stage": item["stage"],
                "course": item["course"],
                "knowledge_tag": item["knowledge_tag"],
                "fine_tag": item["fine_tag"],
                "score": score,
                "total": item["total"],
                "avg_time_seconds": round(item["time_spent_seconds"] / max(item["total"], 1)),
                "reason": "正确率偏低" if score < 60 else "耗时较长或需要继续巩固",
            }
        )
    weak_points.sort(key=lambda item: (item["score"], -item["total"]))
    weakest = weak_points[:3]

    radar_groups = {
        "高等数学": ["高等数学上", "高等数学下", "数学分析选讲"],
        "线性代数": ["线性代数上", "线性代数下", "高等代数"],
        "概率统计": ["概率论与数理统计"],
        "方程与分析": ["级数与常微分方程", "实变函数", "复变函数"],
        "综合建模": ["数学建模与综合专题", "证明方法入门"],
    }
    radar = []
    for label, courses in radar_groups.items():
        matched = [item for item in course_scores if item["course"] in courses]
        if matched:
            score = round(sum(item["score"] for item in matched) / len(matched))
            radar.append({"name": label, "score": score})

    return {
        "user_id": user_id,
        "recent_record_count": len(records),
        "graded_record_count": len(records),
        "pending_review_count": len(all_records) - len(records),
        "summary": (
            f"已分析最近 {len(records)} 条记录，当前最需要补强：{weakest[0]['course']} - {weakest[0]['knowledge_tag']}。"
            if weakest
            else f"已分析最近 {len(records)} 条记录，暂未发现明显薄弱点。"
        ),
        "course_scores": course_scores,
        "weak_points": weakest,
        "radar": radar,
    }

def _recommend_sync(user_id: int, limit: int, stage: str | None, course: str | None) -> list[dict[str, Any]]:
    diagnosis = _diagnose_sync(user_id)
    if int(diagnosis.get("recent_record_count") or 0) == 0:
        return []
    weak_points = diagnosis.get("weak_points") or []
    tasks = []
    for weak in weak_points[:5]:
        task_stage = stage or weak.get("stage")
        task_course = course or weak.get("course")
        tag = weak.get("knowledge_tag")
        questions = _random_questions_sync(
            stage=task_stage,
            course=task_course,
            knowledge_tag=tag,
            question_type=None,
            limit=min(10, max(3, math.ceil(limit / 2))),
        )
        if not questions:
            continue
        tasks.append(
            {
                "title": f"{weak.get('fine_tag') or tag} 巩固训练",
                "stage": task_stage,
                "course": task_course,
                "knowledge_tag": tag,
                "difficulty": round(sum(int(q["difficulty"]) for q in questions) / len(questions), 1),
                "question_count": len(questions),
                "reason": weak.get("reason", "根据薄弱点推荐"),
                "questions": questions,
            }
        )
    return tasks[:limit]

def _study_roadmap_sync(user_id: int) -> dict[str, Any]:
    stages = _stages_sync()
    diagnosis = _diagnose_sync(user_id)
    weak_points = diagnosis.get("weak_points") or []
    try:
        with SessionLocal() as db:
            saved_plan = db.execute(
                text(
                    """
                    SELECT plan_name, plan_json, updated_at
                    FROM learning_plans
                    WHERE user_id = :user_id
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """
                ),
                {"user_id": user_id},
            ).mappings().first()
    except SQLAlchemyError:
        saved_plan = None
    if saved_plan:
        plan_data = _parse_json_object(saved_plan["plan_json"])
        if plan_data.get("weekly_plan"):
            return {
                "user_id": user_id,
                "stages": stages,
                "priority": weak_points[:3],
                "weekly_plan": plan_data["weekly_plan"],
                "summary": plan_data.get("headline") or str(saved_plan["plan_name"]),
                "source": "assessment",
                "updated_at": _json_safe(saved_plan.get("updated_at")),
            }
    if int(diagnosis.get("recent_record_count") or 0) == 0 or not weak_points:
        return {
            "user_id": user_id,
            "stages": stages,
            "priority": [],
            "weekly_plan": [],
            "summary": "暂无做题记录。完成首测后，系统会按薄弱课程生成一周学习计划。",
        }
    focus = weak_points[0]
    weekly_plan = [
        {"day": "周一", "course": focus["course"], "task": f"{focus['knowledge_tag']} 概念回顾", "minutes": 90},
        {"day": "周二", "course": focus["course"], "task": "基础题组 + 错因标注", "minutes": 90},
        {"day": "周三", "course": focus["course"], "task": "计算题/证明题拆解", "minutes": 90},
        {"day": "周四", "course": "线性代数上", "task": "矩阵与向量空间复习", "minutes": 75},
        {"day": "周五", "course": "高等数学上", "task": "混合小测", "minutes": 90},
        {"day": "周六", "course": "综合", "task": "错题回炉与笔记整理", "minutes": 60},
        {"day": "周日", "course": "综合", "task": "休整或轻量复盘", "minutes": 30},
    ]
    return {
        "user_id": user_id,
        "stages": stages,
        "priority": weak_points[:3],
        "weekly_plan": weekly_plan,
        "summary": "学习路线按先修关系推进：基础概念先打牢，再进入计算技巧、证明方法和综合应用。",
    }

def _wrong_questions_sync(user_id: int, limit: int, offset: int) -> dict[str, Any]:
    query = text(
        f"""
        SELECT
          pr.id AS record_id,
          pr.task_id,
          pr.selected_answer,
          pr.answer_text,
          pr.score,
          pr.mistake_tags AS record_mistake_tags,
          pr.time_spent_seconds,
          pr.practice_mode,
          pr.answered_at,
          {_question_select_sql()}
        FROM practice_records AS pr
        JOIN questions AS q ON q.id = pr.question_id
        JOIN source_attributions AS s ON s.id = q.source_id
        WHERE pr.user_id = :user_id AND pr.is_correct = 0
        ORDER BY pr.answered_at DESC, pr.id DESC
        LIMIT :limit OFFSET :offset
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query, {"user_id": user_id, "limit": limit, "offset": offset}).mappings().all()
    items = []
    for row in rows:
        question = _row_to_question(row, include_answer=True)
        question.update(
            {
                "record_id": int(row["record_id"]),
                "task_id": str(row["task_id"]),
                "score": float(row["score"] or 0),
                "answered_at": _json_safe(row["answered_at"]),
                "record_mistake_tags": _parse_json_list(row["record_mistake_tags"]),
            }
        )
        items.append(question)
    return {"user_id": user_id, "items": items, "limit": limit, "offset": offset}

def _get_goal_sync(user_id: int) -> dict[str, Any]:
    query = text(
        """
        SELECT user_id, target_course, target_stage, weekly_hours, exam_date
        FROM user_goal_settings
        WHERE user_id = :user_id
        LIMIT 1
        """
    )
    with SessionLocal() as db:
        row = db.execute(query, {"user_id": user_id}).mappings().first()
    if not row:
        return {
            "user_id": user_id,
            "target_course": "高等数学上",
            "target_stage": "大一",
            "weekly_hours": 8.0,
            "exam_date": None,
            "remaining_days": None,
        }
    exam_date = row["exam_date"]
    remaining_days = max((exam_date - date.today()).days, 0) if exam_date else None
    return {
        "user_id": int(row["user_id"]),
        "target_course": str(row["target_course"]),
        "target_stage": str(row["target_stage"]),
        "weekly_hours": float(row["weekly_hours"]),
        "exam_date": exam_date.isoformat() if exam_date else None,
        "remaining_days": remaining_days,
    }

def _save_goal_sync(user_id: int, payload: GoalRequest) -> dict[str, Any]:
    query = text(
        """
        INSERT INTO user_goal_settings (user_id, target_course, target_stage, weekly_hours, exam_date)
        VALUES (:user_id, :target_course, :target_stage, :weekly_hours, :exam_date)
        ON DUPLICATE KEY UPDATE
          target_course = VALUES(target_course),
          target_stage = VALUES(target_stage),
          weekly_hours = VALUES(weekly_hours),
          exam_date = VALUES(exam_date),
          updated_at = CURRENT_TIMESTAMP
        """
    )
    try:
        with SessionLocal() as db:
            if not _get_user_exists(db, user_id):
                raise HTTPException(status_code=404, detail="请先注册或登录后再设置学习目标。")
            db.execute(query, {"user_id": user_id, **payload.model_dump()})
            db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="学习目标保存失败，请检查数据库连接。") from exc
    return _get_goal_sync(user_id)
