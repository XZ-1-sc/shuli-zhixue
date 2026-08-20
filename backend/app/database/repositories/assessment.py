import json
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text

from ..session import SessionLocal
from ...api.schemas import AnswerSubmissionRequest, AssessmentStartRequest
from ...api.utils import _json_safe, _parse_json_list, _parse_json_object, _row_to_question
from .common import _get_user_exists
from .questions import _question_select_sql


def _assessment_question_rows(db: Any, assessment_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            f"""
            SELECT {_question_select_sql()}, aq.sort_order, aq.practice_record_id,
                   pr.selected_answer AS attempt_selected_answer,
                   pr.answer_text AS attempt_answer_text,
                   pr.is_correct AS attempt_is_correct,
                   pr.score AS attempt_score,
                   pr.review_status AS attempt_review_status
            FROM assessment_session_questions AS aq
            JOIN questions AS q ON q.id = aq.question_id
            JOIN source_attributions AS s ON s.id = q.source_id
            LEFT JOIN practice_records AS pr ON pr.id = aq.practice_record_id
            WHERE aq.assessment_id = :assessment_id
            ORDER BY aq.sort_order
            """
        ),
        {"assessment_id": assessment_id},
    ).mappings().all()
    return [dict(row) for row in rows]

def _assessment_payload(db: Any, session: Any) -> dict[str, Any]:
    session_data = dict(session)
    rows = _assessment_question_rows(db, int(session_data["id"]))
    answered = sum(1 for row in rows if row.get("practice_record_id") is not None)
    questions = []
    for row in rows:
        sort_order = int(row.pop("sort_order"))
        practice_record_id = row.pop("practice_record_id", None)
        attempt = None
        if practice_record_id is not None:
            attempt_score = row.pop("attempt_score", None)
            attempt = {
                "selected_answer": row.pop("attempt_selected_answer", None),
                "answer_text": row.pop("attempt_answer_text", None),
                "is_correct": row.pop("attempt_is_correct", None),
                "score": float(attempt_score) if attempt_score is not None else None,
                "review_status": row.pop("attempt_review_status", None),
                "correct_answer": row.get("correct_answer"),
                "standard_answer": row.get("standard_answer"),
                "analysis_text": row.get("analysis_text"),
                "key_steps": _parse_json_list(row.get("key_steps")),
                "common_errors": _parse_json_list(row.get("common_errors")),
            }
        else:
            for key in (
                "attempt_selected_answer",
                "attempt_answer_text",
                "attempt_is_correct",
                "attempt_score",
                "attempt_review_status",
            ):
                row.pop(key, None)
        question = _row_to_question(row)
        question["sort_order"] = sort_order
        question["answered"] = practice_record_id is not None
        question["attempt"] = attempt
        questions.append(question)
    return {
        "task_id": str(session_data["task_id"]),
        "mode": "assessment",
        "title": "数学基础首测",
        "stage": str(session_data["stage"]),
        "status": str(session_data["status"]),
        "question_count": int(session_data["question_count"]),
        "answered_count": answered,
        "started_at": _json_safe(session_data.get("started_at")),
        "completed_at": _json_safe(session_data.get("completed_at")),
        "questions": questions,
        "report": {
            **_parse_json_object(session_data.get("summary_json")),
            "plan": _parse_json_object(session_data.get("plan_json")),
        }
        if session_data.get("summary_json")
        else None,
    }

def _pick_balanced_assessment_questions(db: Any, stage: str, limit: int) -> list[int]:
    type_cycle = ["choice", "blank", "calculation", "proof", "comprehensive"]
    type_weights: list[str] = []
    while len(type_weights) < limit:
        type_weights.extend(type_cycle)
    if limit >= 10:
        # A second choice/calculation pass keeps larger tests practical without dropping proof coverage.
        type_weights = [
            "choice", "blank", "calculation", "proof", "comprehensive",
            "choice", "calculation", "blank", "proof", "comprehensive",
        ] + type_weights
    selected: list[int] = []

    for question_type in type_weights[:limit]:
        row = db.execute(
            text(
                """
                SELECT q.id
                FROM questions AS q
                WHERE q.stage = :stage
                  AND q.question_type = :question_type
                  AND (q.source_question_no LIKE 'CURATED-%' OR q.source_question_no LIKE 'BACHELOR-CN-%')
                  AND q.question_text NOT LIKE :placeholder
                  AND q.id NOT IN (
                    SELECT aq.question_id
                    FROM assessment_session_questions AS aq
                    JOIN assessment_sessions AS a ON a.id = aq.assessment_id
                    WHERE a.stage = :stage
                  )
                ORDER BY RAND()
                LIMIT 1
                """
            ),
            {"stage": stage, "question_type": question_type, "placeholder": "%□%"},
        ).first()
        if not row:
            row = db.execute(
                text(
                    """
                    SELECT q.id
                    FROM questions AS q
                    WHERE q.stage = :stage
                      AND q.question_type = :question_type
                      AND (q.source_question_no LIKE 'CURATED-%' OR q.source_question_no LIKE 'BACHELOR-CN-%')
                      AND q.question_text NOT LIKE :placeholder
                    ORDER BY RAND()
                    LIMIT 1
                    """
                ),
                {"stage": stage, "question_type": question_type, "placeholder": "%□%"},
            ).first()
        if row and int(row[0]) not in selected:
            selected.append(int(row[0]))

    if len(selected) < limit:
        params: dict[str, Any] = {"stage": stage, "limit": limit - len(selected), "placeholder": "%□%"}
        exclusion = ""
        if selected:
            keys = []
            for index, question_id in enumerate(selected):
                key = f"selected_{index}"
                params[key] = question_id
                keys.append(f":{key}")
            exclusion = f"AND q.id NOT IN ({', '.join(keys)})"
        rows = db.execute(
            text(
                f"""
                SELECT q.id
                FROM questions AS q
                WHERE q.stage = :stage
                  AND (q.source_question_no LIKE 'CURATED-%' OR q.source_question_no LIKE 'BACHELOR-CN-%')
                  AND q.question_text NOT LIKE :placeholder
                  {exclusion}
                ORDER BY RAND()
                LIMIT :limit
                """
            ),
            params,
        ).all()
        selected.extend(int(row[0]) for row in rows)
    return selected[:limit]

def _start_assessment_sync(user_id: int, payload: AssessmentStartRequest) -> dict[str, Any]:
    with SessionLocal() as db:
        if not _get_user_exists(db, user_id):
            raise HTTPException(status_code=404, detail="请先注册或登录后再开始首测。")
        if payload.restart:
            db.execute(
                text("UPDATE assessment_sessions SET status = 'abandoned' WHERE user_id = :user_id AND status = 'in_progress'"),
                {"user_id": user_id},
            )
        else:
            existing = db.execute(
                text(
                    """
                    SELECT * FROM assessment_sessions
                    WHERE user_id = :user_id AND status = 'in_progress'
                    ORDER BY started_at DESC LIMIT 1
                    """
                ),
                {"user_id": user_id},
            ).mappings().first()
            if existing:
                return _assessment_payload(db, existing)

        stage = payload.stage or db.execute(
            text("SELECT current_stage FROM users WHERE id = :user_id"), {"user_id": user_id}
        ).scalar() or "大一"
        question_ids = _pick_balanced_assessment_questions(db, str(stage), payload.limit)
        if len(question_ids) < payload.limit:
            raise HTTPException(status_code=409, detail=f"{stage}中文首测题暂时不足，请先补充题库。")

        task_id = str(uuid.uuid4())
        result = db.execute(
            text(
                """
                INSERT INTO assessment_sessions (task_id, user_id, stage, question_count)
                VALUES (:task_id, :user_id, :stage, :question_count)
                """
            ),
            {"task_id": task_id, "user_id": user_id, "stage": stage, "question_count": len(question_ids)},
        )
        assessment_id = int(result.lastrowid)
        for sort_order, question_id in enumerate(question_ids, start=1):
            db.execute(
                text(
                    """
                    INSERT INTO assessment_session_questions (assessment_id, question_id, sort_order)
                    VALUES (:assessment_id, :question_id, :sort_order)
                    """
                ),
                {"assessment_id": assessment_id, "question_id": question_id, "sort_order": sort_order},
            )
        db.commit()
        session = db.execute(
            text("SELECT * FROM assessment_sessions WHERE id = :assessment_id"), {"assessment_id": assessment_id}
        ).mappings().one()
        return _assessment_payload(db, session)

def _validate_assessment_question(db: Any, user_id: int, payload: AnswerSubmissionRequest) -> int | None:
    if payload.practice_mode != "assessment":
        return None
    row = db.execute(
        text(
            """
            SELECT aq.id
            FROM assessment_sessions AS a
            JOIN assessment_session_questions AS aq ON aq.assessment_id = a.id
            WHERE a.task_id = :task_id
              AND a.user_id = :user_id
              AND a.status = 'in_progress'
              AND aq.question_id = :question_id
              AND aq.practice_record_id IS NULL
            LIMIT 1
            """
        ),
        {"task_id": payload.task_id, "user_id": user_id, "question_id": payload.question_id},
    ).first()
    if not row:
        raise HTTPException(status_code=409, detail="该首测题目已提交，或首测任务已经结束。")
    return int(row[0])

def _build_assessment_report_sync(user_id: int, task_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        session = db.execute(
            text(
                """
                SELECT id, stage, question_count
                FROM assessment_sessions
                WHERE task_id = :task_id AND user_id = :user_id
                LIMIT 1
                """
            ),
            {"task_id": task_id, "user_id": user_id},
        ).mappings().first()
        if not session:
            raise HTTPException(status_code=404, detail="首测任务不存在。")
        rows = db.execute(
            text(
                """
                SELECT
                  q.course, q.knowledge_tag, q.fine_tag, q.question_type,
                  pr.is_correct, pr.score, pr.review_status, pr.time_spent_seconds
                FROM assessment_session_questions AS aq
                JOIN questions AS q ON q.id = aq.question_id
                LEFT JOIN practice_records AS pr ON pr.id = aq.practice_record_id
                WHERE aq.assessment_id = :assessment_id
                ORDER BY aq.sort_order
                """
            ),
            {"assessment_id": int(session["id"])},
        ).mappings().all()

    graded = [row for row in rows if row["is_correct"] is not None]
    correct_count = sum(1 for row in graded if bool(row["is_correct"]))
    pending_count = sum(1 for row in rows if str(row.get("review_status") or "") == "pending")
    accuracy = round(correct_count / len(graded) * 100) if graded else 0
    total_seconds = sum(int(row.get("time_spent_seconds") or 0) for row in rows)

    knowledge: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in graded:
        key = (str(row["course"]), str(row["knowledge_tag"]), str(row["fine_tag"]))
        item = knowledge.setdefault(
            key,
            {
                "course": key[0],
                "knowledge_tag": key[1],
                "fine_tag": key[2],
                "total": 0,
                "correct": 0,
                "time_spent_seconds": 0,
            },
        )
        item["total"] += 1
        item["correct"] += int(bool(row["is_correct"]))
        item["time_spent_seconds"] += int(row.get("time_spent_seconds") or 0)

    scored_points = []
    for item in knowledge.values():
        point_score = round(item["correct"] / max(item["total"], 1) * 100)
        scored_points.append(
            {
                **item,
                "score": point_score,
                "avg_time_seconds": round(item["time_spent_seconds"] / max(item["total"], 1)),
            }
        )
    weak_points = sorted(scored_points, key=lambda item: (item["score"], -item["total"]))[:3]
    strengths = sorted(scored_points, key=lambda item: (-item["score"], -item["total"]))[:2]
    focus = weak_points[0] if weak_points else {
        "course": "高等数学上",
        "knowledge_tag": "基础概念",
        "fine_tag": "基础概念",
        "score": accuracy,
    }

    second_focus = weak_points[1] if len(weak_points) > 1 else focus
    weekly_plan = [
        {"day": "第 1 天", "task": f"回顾「{focus['fine_tag']}」定义与例题", "minutes": 45},
        {"day": "第 2 天", "task": f"完成「{focus['fine_tag']}」基础题 8 题", "minutes": 50},
        {"day": "第 3 天", "task": f"整理「{focus['knowledge_tag']}」错因笔记", "minutes": 35},
        {"day": "第 4 天", "task": f"学习「{second_focus['fine_tag']}」关键方法", "minutes": 45},
        {"day": "第 5 天", "task": "完成一组计算与证明混合练习", "minutes": 60},
        {"day": "第 6 天", "task": "回炉本次首测错题", "minutes": 40},
        {"day": "第 7 天", "task": "完成 10 题阶段复测并复盘", "minutes": 50},
    ]

    pending_note = f"，另有 {pending_count} 道图片作答待教师复核" if pending_count else ""
    summary = (
        f"本次首测完成 {len(rows)} 题，已自动评分 {len(graded)} 题，正确 {correct_count} 题，"
        f"自动评分正确率 {accuracy}%{pending_note}。"
    )
    xiaoluo_message = (
        f"首测完成，我已经看过你的作答。{summary}\n\n"
        f"当前优先补强：{focus['course']} · {focus['fine_tag']}（掌握度约 {focus['score']}%）。\n"
        f"接下来 7 天先走“概念回顾 → 基础题 → 错因整理 → 混合复测”这条路线。"
        + (" 图片题我先标成待复核，教师评分后再更新你的诊断。" if pending_count else "")
    )
    return {
        "task_id": task_id,
        "title": "基础首测分析",
        "stage": str(session["stage"]),
        "question_count": int(session["question_count"]),
        "graded_count": len(graded),
        "correct_count": correct_count,
        "pending_review_count": pending_count,
        "accuracy": accuracy,
        "duration_seconds": total_seconds,
        "summary": summary,
        "weak_points": weak_points,
        "strengths": strengths,
        "plan": {
            "headline": f"先补强 {focus['fine_tag']}，再进行阶段复测",
            "focus_course": focus["course"],
            "focus_knowledge": focus["knowledge_tag"],
            "weekly_plan": weekly_plan,
            "next_action": {
                "label": f"练习 {focus['fine_tag']}",
                "path": "/practice",
                "query": {
                    "mode": "daily",
                    "course": focus["course"],
                    "knowledge_tag": focus["knowledge_tag"],
                    "limit": 8,
                },
            },
        },
        "xiaoluo_message": xiaoluo_message,
    }

def _assessment_after_submit_sync(user_id: int, task_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        state = db.execute(
            text(
                """
                SELECT
                  a.id, a.status, a.question_count, a.summary_json, a.plan_json,
                  SUM(CASE WHEN aq.practice_record_id IS NOT NULL THEN 1 ELSE 0 END) AS answered_count
                FROM assessment_sessions AS a
                JOIN assessment_session_questions AS aq ON aq.assessment_id = a.id
                WHERE a.task_id = :task_id AND a.user_id = :user_id
                GROUP BY a.id, a.status, a.question_count, a.summary_json, a.plan_json
                LIMIT 1
                """
            ),
            {"task_id": task_id, "user_id": user_id},
        ).mappings().first()
    if not state:
        raise HTTPException(status_code=404, detail="首测任务不存在。")

    answered_count = int(state["answered_count"] or 0)
    question_count = int(state["question_count"])
    if answered_count < question_count:
        return {
            "assessment_complete": False,
            "assessment_progress": {"answered": answered_count, "total": question_count},
        }

    if str(state["status"]) == "completed" and state.get("summary_json"):
        report = _parse_json_object(state["summary_json"])
        report["plan"] = _parse_json_object(state["plan_json"])
        return {
            "assessment_complete": True,
            "assessment_progress": {"answered": answered_count, "total": question_count},
            "assessment_report": report,
        }

    report = _build_assessment_report_sync(user_id, task_id)
    session_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.execute(
            text(
                """
                UPDATE assessment_sessions
                SET status = 'completed', summary_json = :summary_json, plan_json = :plan_json,
                    completed_at = CURRENT_TIMESTAMP
                WHERE task_id = :task_id AND user_id = :user_id
                """
            ),
            {
                "summary_json": json.dumps({key: value for key, value in report.items() if key != "plan"}, ensure_ascii=False),
                "plan_json": json.dumps(report["plan"], ensure_ascii=False),
                "task_id": task_id,
                "user_id": user_id,
            },
        )
        db.execute(
            text(
                """
                INSERT INTO learning_plans (user_id, stage, course, plan_name, plan_json)
                VALUES (:user_id, :stage, :course, :plan_name, :plan_json)
                """
            ),
            {
                "user_id": user_id,
                "stage": report["stage"],
                "course": report["plan"]["focus_course"],
                "plan_name": "首测后 7 天学习计划",
                "plan_json": json.dumps(report["plan"], ensure_ascii=False),
            },
        )
        db.execute(
            text(
                """
                INSERT INTO chat_messages (session_id, user_id, role, content)
                VALUES (:session_id, :user_id, 'assistant', :content)
                """
            ),
            {"session_id": session_id, "user_id": user_id, "content": report["xiaoluo_message"]},
        )
        db.commit()
    report["chat_session_id"] = session_id
    return {
        "assessment_complete": True,
        "assessment_progress": {"answered": answered_count, "total": question_count},
        "assessment_report": report,
    }

