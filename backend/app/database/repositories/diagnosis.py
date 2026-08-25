import json
import math
from collections import Counter
from datetime import date, timedelta
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


def _practice_review_brief_sync(
    user_id: int,
    task_id: str,
    *,
    title: str = "本次练习复盘",
    assignment_id: int | None = None,
) -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT pr.id, pr.question_id, pr.is_correct, pr.score, pr.review_status,
                       pr.mistake_tags, q.stage, q.course, q.knowledge_tag, q.fine_tag
                FROM practice_records AS pr
                JOIN questions AS q ON q.id = pr.question_id
                WHERE pr.user_id = :user_id AND pr.task_id = :task_id
                ORDER BY pr.answered_at, pr.id
                """
            ),
            {"user_id": user_id, "task_id": task_id},
        ).mappings().all()

    graded = [row for row in rows if row["is_correct"] is not None]
    correct = sum(1 for row in graded if bool(row["is_correct"]))
    pending = sum(1 for row in rows if row["is_correct"] is None)
    accuracy = round(correct / len(graded) * 100, 1) if graded else 0.0
    mistake_counter: Counter[str] = Counter()
    weak_counter: Counter[tuple[str, str, str, str]] = Counter()
    for row in rows:
        if row["is_correct"] is False or row["is_correct"] == 0:
            tags = _parse_json_list(row["mistake_tags"]) or ["知识点需巩固"]
            mistake_counter.update(str(tag) for tag in tags)
            weak_counter.update(
                [
                    (
                        str(row["stage"]),
                        str(row["course"]),
                        str(row["knowledge_tag"]),
                        str(row["fine_tag"] or row["knowledge_tag"]),
                    )
                ]
            )
    top_mistakes = [{"label": label, "count": count} for label, count in mistake_counter.most_common(3)]
    weakest = weak_counter.most_common(1)
    if pending and not graded:
        suggestion = "本次作答已进入教师复核，结果确认前先整理关键步骤与所用定理。"
    elif weakest:
        suggestion = f"下一步优先回炉“{weakest[0][0][3]}”，先复习概念，再完成一组同类题。"
    elif rows:
        suggestion = "本次已掌握当前知识点，建议用一道变式题检查迁移能力。"
    else:
        suggestion = "完成题目后，小逻会根据真实作答生成复盘建议。"
    actions: list[dict[str, Any]] = [{"label": "查看完整报告", "type": "navigate", "target": "/review"}]
    if weakest:
        stage, course, knowledge_tag, _ = weakest[0][0]
        actions.insert(
            0,
            {
                "label": "开始回炉练习",
                "type": "navigate",
                "target": "/practice",
                "query": {"stage": stage, "course": course, "knowledge_tag": knowledge_tag, "mode": "wrong_book", "limit": 8},
            },
        )
    context: dict[str, Any] = {"type": "assignment", "assignment_id": assignment_id} if assignment_id else {"type": "question"}
    if rows:
        context.update({"question_id": int(rows[-1]["question_id"]), "record_id": int(rows[-1]["id"])})
    return {
        "type": "review",
        "title": title,
        "summary": suggestion,
        "metrics": [
            {"label": "本次正确率", "value": f"{accuracy:g}%" if graded else "待复核"},
            {"label": "已完成", "value": f"{len(rows)} 题"},
            {"label": "待复核", "value": f"{pending} 题"},
        ],
        "accuracy": accuracy,
        "total": len(rows),
        "graded": len(graded),
        "correct": correct,
        "pending": pending,
        "mistakes": top_mistakes,
        "suggestion": suggestion,
        "actions": actions,
        "context": context,
    }


def _review_analysis_sync(user_id: int) -> dict[str, Any]:
    records = _recent_records_sync(user_id, 500)
    wrong = [record for record in records if record.get("is_correct") is False or record.get("is_correct") == 0]
    reason_counter: Counter[str] = Counter()
    knowledge_counter: Counter[tuple[str, str, str, str]] = Counter()
    for record in wrong:
        reason_counter.update(str(tag) for tag in (record.get("mistake_tags") or ["知识点需巩固"]))
        knowledge_counter.update(
            [
                (
                    str(record.get("stage") or ""),
                    str(record.get("course") or ""),
                    str(record.get("knowledge_tag") or ""),
                    str(record.get("fine_tag") or record.get("knowledge_tag") or ""),
                )
            ]
        )
    reasons = [{"label": label, "count": count} for label, count in reason_counter.most_common(8)]
    knowledge = [
        {"stage": key[0], "course": key[1], "knowledge_tag": key[2], "fine_tag": key[3], "wrong_count": count}
        for key, count in knowledge_counter.most_common(5)
    ]
    if knowledge:
        suggestion = f"先处理“{knowledge[0]['fine_tag']}”的高频错误：复习定义后完成 5—8 道同类题，并逐题标注错因。"
    else:
        suggestion = "当前没有已评分错题。完成练习后，这里会生成错因分布与薄弱知识点报告。"
    return {
        "user_id": user_id,
        "total_records": len(records),
        "wrong_count": len(wrong),
        "reason_distribution": reasons,
        "weak_knowledge": knowledge,
        "suggestion": suggestion,
    }


def _learning_insights_sync(user_id: int, days: int = 84) -> dict[str, Any]:
    start_day = date.today() - timedelta(days=max(1, days) - 1)
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT DATE(answered_at) AS day, COUNT(*) AS attempts,
                       ROUND(AVG(CASE WHEN is_correct IS NOT NULL THEN is_correct END) * 100, 1) AS mastery,
                       COALESCE(SUM(time_spent_seconds), 0) AS study_seconds
                FROM practice_records
                WHERE user_id = :user_id AND answered_at >= :start_day
                GROUP BY DATE(answered_at)
                ORDER BY day
                """
            ),
            {"user_id": user_id, "start_day": start_day},
        ).mappings().all()
    by_day = {str(row["day"]): row for row in rows}
    calendar = []
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        row = by_day.get(day.isoformat(), {})
        calendar.append(
            {
                "date": day.isoformat(),
                "attempts": int(row.get("attempts") or 0),
                "study_minutes": round(int(row.get("study_seconds") or 0) / 60),
            }
        )
    trend = [
        {
            "date": item["date"],
            "mastery": float(by_day[item["date"]]["mastery"] or 0),
            "attempts": item["attempts"],
        }
        for item in calendar[-30:]
        if item["date"] in by_day and by_day[item["date"]]["mastery"] is not None
    ]
    return {"user_id": user_id, "days": days, "calendar": calendar, "mastery_trend": trend}


def _recent_negotiation_sync(user_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        conversation_id = db.execute(
            text(
                """
                SELECT conversation_id FROM negotiation_log
                WHERE user_id = :user_id
                ORDER BY created_at DESC, id DESC LIMIT 1
                """
            ),
            {"user_id": user_id},
        ).scalar()
        if not conversation_id:
            return {"available": False, "items": [], "message": "完成首测后即可查看多智能体分析过程。"}
        rows = db.execute(
            text(
                """
                SELECT round_no, speaker, message_type, content, needs_rediagnosis, created_at
                FROM negotiation_log
                WHERE user_id = :user_id AND conversation_id = :conversation_id
                ORDER BY round_no, created_at, id
                """
            ),
            {"user_id": user_id, "conversation_id": conversation_id},
        ).mappings().all()
    items = []
    confidence = None
    for row in rows:
        raw_content = str(row["content"] or "")
        try:
            content: Any = json.loads(raw_content)
        except (TypeError, json.JSONDecodeError):
            content = {"summary": raw_content[:500]}
        if row["message_type"] in {"diagnosis", "rediagnosis"} and isinstance(content, dict):
            confidence = content.get("confidence", confidence)
        items.append(
            {
                "round": int(row["round_no"]),
                "speaker": str(row["speaker"]),
                "message_type": str(row["message_type"]),
                "content": content,
                "needs_rediagnosis": bool(row["needs_rediagnosis"]),
                "created_at": _json_safe(row["created_at"]),
            }
        )
    started = rows[0]["created_at"] if rows else None
    ended = rows[-1]["created_at"] if rows else None
    duration_ms = max(0, round((ended - started).total_seconds() * 1000)) if started and ended else 0
    return {
        "available": True,
        "conversation_id": str(conversation_id),
        "rounds": max((item["round"] for item in items), default=0),
        "rediagnosed": any(item["message_type"] == "rediagnosis" for item in items),
        "confidence": float(confidence) if confidence is not None else None,
        "duration_ms": duration_ms,
        "items": items,
    }

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
