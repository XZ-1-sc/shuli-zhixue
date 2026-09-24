import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..session import SessionLocal
from ...agents.evaluator import evaluate
from ...api.schemas import AnswerSubmissionRequest
from ...services.scoring import _score_subjective
from ...services.solution_service import ensure_solution_steps_sync, score_answer_steps
from ...services.risk_service import create_help_signals_sync
from .assessment import _assessment_after_submit_sync, _validate_assessment_question
from .common import _get_user_exists
from .diagnosis import _practice_review_brief_sync
from .questions import _get_question_sync, _random_questions_sync, _validate_attachment_ids


def _practice_companion_signal_sync(user_id: int, question: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT pr.id,pr.is_correct
                FROM practice_records pr JOIN questions q ON q.id=pr.question_id
                WHERE pr.user_id=:user_id AND q.knowledge_tag=:knowledge_tag AND pr.is_correct IS NOT NULL
                ORDER BY pr.answered_at DESC,pr.id DESC LIMIT 30
                """
            ),
            {"user_id": user_id, "knowledge_tag": question.get("knowledge_tag")},
        ).mappings().all()
    streak_wrong = 0
    for row in rows:
        if bool(row["is_correct"]):
            break
        streak_wrong += 1
    total = len(rows)
    correct = sum(1 for row in rows if bool(row["is_correct"]))
    current_accuracy = correct / total if total else 0
    previous = rows[1:]
    previous_accuracy = sum(1 for row in previous if bool(row["is_correct"])) / len(previous) if previous else 0
    breakthrough = bool(rows and rows[0]["is_correct"] and total >= 5 and current_accuracy >= 0.8 and previous_accuracy < 0.8)
    if streak_wrong >= 3:
        tone = "empathy"
        message = f"这类题连续卡住 {streak_wrong} 次不代表学不会。先停一下，我换个角度帮你拆开关键一步。"
    elif breakthrough:
        tone = "celebration"
        message = f"你在“{question.get('fine_tag') or question.get('knowledge_tag')}”上的近期掌握度首次突破 80%，这次进步有真实记录支撑。"
    elif rows and bool(rows[0]["is_correct"]):
        tone = "encouragement"
        message = "这一步已经走对了，再用一道参数变化题确认不是偶然。"
    else:
        tone = "coaching"
        message = "先别急着重做整题，定位第一个偏离标准步骤的位置会更有效。"
    return {
        "tone": tone,
        "message": message,
        "streak_wrong": streak_wrong,
        "breakthrough_80": breakthrough,
        "knowledge_tag": question.get("knowledge_tag"),
        "fine_tag": question.get("fine_tag"),
        "recent_mastery": round(current_accuracy * 100, 1),
    }


def _submit_answer_sync(user_id: int, payload: AnswerSubmissionRequest) -> dict[str, Any]:
    question = _get_question_sync(payload.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在。")

    question_type = str(question["question_type"])
    selected = (payload.selected_answer or "").strip().upper()
    answer_text = (payload.answer_text or "").strip()
    if question_type == "choice" and not selected:
        raise HTTPException(status_code=422, detail="请选择一个答案后再提交。")
    if question_type != "choice" and not answer_text and not payload.attachment_ids:
        raise HTTPException(status_code=422, detail="请填写答案，或上传作答图片后再提交。")

    has_images = bool(payload.attachment_ids)
    pending_review = has_images and question_type != "choice"
    if pending_review:
        is_correct = None
        score = None
    elif question_type == "choice":
        correct_answer = str(question.get("correct_answer") or "").strip().upper()
        is_correct = bool(selected and selected == correct_answer)
        score = 100.0 if is_correct else 0.0
    else:
        is_correct, score = _score_subjective(answer_text, question, question_type)

    mistake_tags = [] if is_correct is not False else (question.get("mistake_tags") or question.get("common_errors") or ["概念未掌握"])

    insert_query = text(
        """
        INSERT INTO practice_records (
          task_id, user_id, question_id, selected_answer, answer_text, answer_steps, is_correct,
          score, mistake_tags, time_spent_seconds, practice_mode, review_status
        )
        VALUES (
          :task_id, :user_id, :question_id, :selected_answer, :answer_text, :answer_steps, :is_correct,
          :score, :mistake_tags, :time_spent_seconds, :practice_mode, :review_status
        )
        """
    )
    try:
        with SessionLocal() as db:
            if not _get_user_exists(db, user_id):
                raise HTTPException(status_code=404, detail="请先注册或登录后再提交做题记录。")
            attachment_ids = _validate_attachment_ids(db, user_id, payload.attachment_ids)
            assessment_question_id = _validate_assessment_question(db, user_id, payload)
            insert_result = db.execute(
                insert_query,
                {
                    "task_id": payload.task_id,
                    "user_id": user_id,
                    "question_id": payload.question_id,
                    "selected_answer": selected or None,
                    "answer_text": answer_text or None,
                    "answer_steps": json.dumps([step.strip() for step in payload.answer_steps if step.strip()], ensure_ascii=False) or None,
                    "is_correct": None if is_correct is None else (1 if is_correct else 0),
                    "score": score,
                    "mistake_tags": json.dumps(mistake_tags, ensure_ascii=False),
                    "time_spent_seconds": payload.time_spent_seconds,
                    "practice_mode": payload.practice_mode,
                    "review_status": "pending" if pending_review else "auto_graded",
                },
            )
            record_id = int(insert_result.lastrowid)
            for sort_order, file_id in enumerate(attachment_ids, start=1):
                db.execute(
                    text(
                        """
                        INSERT INTO answer_attachments (practice_record_id, uploaded_file_id, sort_order)
                        VALUES (:record_id, :file_id, :sort_order)
                        """
                    ),
                    {"record_id": record_id, "file_id": file_id, "sort_order": sort_order},
                )
            if assessment_question_id is not None:
                db.execute(
                    text(
                        """
                        UPDATE assessment_session_questions
                        SET practice_record_id = :record_id, answered_at = CURRENT_TIMESTAMP
                        WHERE id = :assessment_question_id
                        """
                    ),
                    {"record_id": record_id, "assessment_question_id": assessment_question_id},
                )
            db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="做题记录保存失败，请检查数据库连接。") from exc

    next_items = _random_questions_sync(
        stage=question.get("stage"),
        course=question.get("course"),
        knowledge_tag=question.get("knowledge_tag"),
        question_type=None,
        limit=3,
    )
    solution = ensure_solution_steps_sync(payload.question_id, user_id)
    step_feedback = score_answer_steps(payload.answer_steps, solution.get("steps") or [])
    if payload.answer_steps:
        with SessionLocal() as db:
            db.execute(
                text("UPDATE practice_records SET step_feedback=:feedback WHERE id=:record_id AND user_id=:user_id"),
                {"feedback": json.dumps(step_feedback, ensure_ascii=False), "record_id": record_id, "user_id": user_id},
            )
            db.commit()
    response = {
        "task_id": payload.task_id,
        "record_id": record_id,
        "question_id": payload.question_id,
        "is_correct": is_correct,
        "score": score,
        "review_status": "pending" if pending_review else "auto_graded",
        "pending_review": pending_review,
        "attachment_count": len(payload.attachment_ids),
        "correct_answer": question.get("correct_answer"),
        "standard_answer": question.get("standard_answer"),
        "analysis_text": question.get("analysis_text"),
        "key_steps": question.get("key_steps"),
        "solution_steps": solution.get("steps") or [],
        "solution_steps_source": solution.get("source"),
        "solution_steps_review_status": solution.get("review_status"),
        "step_feedback": step_feedback,
        "common_errors": question.get("common_errors"),
        "mistake_tags": mistake_tags,
        "next_recommendation": {
            "title": f"{question.get('fine_tag') or question.get('knowledge_tag')} 巩固练习",
            "stage": question.get("stage"),
            "course": question.get("course"),
            "knowledge_tag": question.get("knowledge_tag"),
            "questions": next_items,
        },
    }
    if payload.practice_mode == "assessment":
        assessment_state = _assessment_after_submit_sync(user_id, payload.task_id)
        response.update(assessment_state)
    response["evaluation"] = evaluate(user_id, payload.task_id).model_dump()
    response["review_brief"] = _practice_review_brief_sync(user_id, payload.task_id)
    signal = _practice_companion_signal_sync(user_id, question)
    signal["teacher_help_signals_created"] = create_help_signals_sync(user_id, question, signal["streak_wrong"])
    response["companion_signal"] = signal
    response["review_brief"]["companion"] = signal
    if signal["streak_wrong"] >= 3:
        response["review_brief"].setdefault("actions", []).append(
            {
                "label": "换个角度再讲一次",
                "type": "prompt",
                "prompt": "这类题我已经连续做错，请换一种直观方法讲清楚关键概念，并带我走完第一步。",
                "context": {"type": "question", "record_id": record_id},
            }
        )
    if signal["breakthrough_80"]:
        response["celebration_card"] = {
            "type": "celebration",
            "title": "掌握度突破 80%",
            "summary": signal["message"],
            "metrics": [{"label": "近期掌握度", "value": f"{signal['recent_mastery']:g}%"}],
            "actions": [{"label": "查看成就", "type": "navigate", "target": "/achievements"}],
        }
    return response
