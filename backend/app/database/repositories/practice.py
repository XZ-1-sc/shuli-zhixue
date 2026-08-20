import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..session import SessionLocal
from ...api.schemas import AnswerSubmissionRequest
from ...services.scoring import _score_subjective
from .assessment import _assessment_after_submit_sync, _validate_assessment_question
from .common import _get_user_exists
from .questions import _get_question_sync, _random_questions_sync, _validate_attachment_ids


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
          task_id, user_id, question_id, selected_answer, answer_text, is_correct,
          score, mistake_tags, time_spent_seconds, practice_mode, review_status
        )
        VALUES (
          :task_id, :user_id, :question_id, :selected_answer, :answer_text, :is_correct,
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
    response = {
        "task_id": payload.task_id,
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
    return response

