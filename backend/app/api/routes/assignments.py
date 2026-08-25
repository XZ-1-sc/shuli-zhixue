import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from ...agents.evaluator import evaluate
from ...database.session import SessionLocal
from ...database.repositories.questions import _get_question_sync, _validate_attachment_ids
from ...database.repositories.diagnosis import _practice_review_brief_sync
from ...security import require_student
from ...services.scoring import _score_subjective
from ..utils import _parse_json_list, _question_select_sql, _row_to_question


router = APIRouter(prefix="/api/assignments", tags=["student-assignments"])


class AssignmentAnswerRequest(BaseModel):
    assignment_question_id: int = Field(ge=1)
    selected_answer: str | None = Field(default=None, max_length=16)
    answer_text: str | None = Field(default=None, max_length=12000)
    attachment_ids: list[int] = Field(default_factory=list, max_length=5)
    time_spent_seconds: int = Field(default=0, ge=0, le=86400)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _parse_ids(value: Any) -> list[int]:
    if isinstance(value, list):
        return [int(item) for item in value]
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [int(item) for item in parsed] if isinstance(parsed, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _assignment_for_student(db: Any, user_id: int, assignment_id: int, *, allow_closed: bool = True) -> dict[str, Any]:
    allowed = "('published','closed')" if allow_closed else "('published')"
    row = db.execute(
        text(
            f"""
            SELECT a.*, c.name AS class_name, c.stage, c.course, u.username AS teacher_name
            FROM assignments AS a
            JOIN classes AS c ON c.id=a.class_id AND c.status='active'
            JOIN class_members AS cm ON cm.class_id=c.id AND cm.student_id=:user_id AND cm.status='active'
            JOIN users AS u ON u.id=a.teacher_id
            WHERE a.id=:assignment_id AND a.status IN {allowed}
            LIMIT 1
            """
        ),
        {"user_id": user_id, "assignment_id": assignment_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="作业不存在，尚未发布，或你不在对应班级中。")
    return dict(row)


def _attempt(db: Any, assignment_id: int, user_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text(
            """
            SELECT * FROM assignment_attempts
            WHERE assignment_id=:assignment_id AND user_id=:user_id
            ORDER BY attempt_no DESC LIMIT 1
            """
        ),
        {"assignment_id": assignment_id, "user_id": user_id},
    ).mappings().first()
    return dict(row) if row else None


def _remaining_seconds(assignment: dict[str, Any], attempt: dict[str, Any] | None) -> int | None:
    if not attempt or not assignment.get("time_limit_minutes"):
        return None
    deadline = attempt["started_at"] + timedelta(minutes=int(assignment["time_limit_minutes"]))
    return max(0, int((deadline - datetime.now()).total_seconds()))


def _assignment_base(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(item["id"]),
        "title": str(item["title"]),
        "description": str(item.get("description") or ""),
        "class_id": int(item["class_id"]),
        "class_name": str(item["class_name"]),
        "teacher_name": str(item.get("teacher_name") or "任课教师"),
        "stage": str(item.get("stage") or ""),
        "course": str(item.get("course") or ""),
        "status": str(item["status"]),
        "starts_at": _iso(item.get("starts_at")),
        "due_at": _iso(item.get("due_at")),
        "time_limit_minutes": int(item["time_limit_minutes"]) if item.get("time_limit_minutes") else None,
        "max_attempts": int(item.get("max_attempts") or 1),
        "show_analysis_after_submit": bool(item.get("show_analysis_after_submit")),
        "total_score": float(item.get("total_score") or 0),
        "published_at": _iso(item.get("published_at")),
    }


def _list_sync(user_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT a.*,c.name AS class_name,c.stage,c.course,u.username AS teacher_name,
                       COUNT(DISTINCT aq.id) AS question_count,
                       aa.id AS attempt_id,aa.attempt_no,aa.status AS attempt_status,aa.total_score AS attempt_score,
                       aa.max_score,aa.started_at,aa.submitted_at,aa.graded_at,
                       COUNT(DISTINCT ans.id) AS answered_count,
                       SUM(CASE WHEN ans.review_status='pending' THEN 1 ELSE 0 END) AS pending_review
                FROM assignments AS a
                JOIN classes AS c ON c.id=a.class_id AND c.status='active'
                JOIN class_members AS cm ON cm.class_id=c.id AND cm.student_id=:user_id AND cm.status='active'
                JOIN users AS u ON u.id=a.teacher_id
                LEFT JOIN assignment_questions AS aq ON aq.assignment_id=a.id
                LEFT JOIN assignment_attempts AS aa ON aa.id=(
                  SELECT latest.id FROM assignment_attempts AS latest
                  WHERE latest.assignment_id=a.id AND latest.user_id=:user_id
                  ORDER BY latest.attempt_no DESC LIMIT 1
                )
                LEFT JOIN assignment_answers AS ans ON ans.attempt_id=aa.id
                WHERE a.status IN ('published','closed')
                GROUP BY a.id,c.name,c.stage,c.course,u.username,aa.id,aa.attempt_no,aa.status,aa.total_score,
                         aa.max_score,aa.started_at,aa.submitted_at,aa.graded_at
                ORDER BY (aa.id IS NULL) DESC,(a.due_at IS NULL),a.due_at,a.created_at DESC
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
    items = []
    for row in rows:
        item = _assignment_base(dict(row))
        item.update(
            {
                "question_count": int(row["question_count"] or 0),
                "attempt_id": int(row["attempt_id"]) if row["attempt_id"] else None,
                "attempt_no": int(row["attempt_no"] or 0),
                "attempt_status": str(row["attempt_status"] or "not_started"),
                "attempt_score": float(row["attempt_score"] or 0) if row["attempt_score"] is not None else None,
                "max_score": float(row["max_score"] or row["total_score"] or 0),
                "answered_count": int(row["answered_count"] or 0),
                "pending_review": int(row["pending_review"] or 0),
                "started_at": _iso(row["started_at"]),
                "submitted_at": _iso(row["submitted_at"]),
                "graded_at": _iso(row["graded_at"]),
                "overdue": bool(row["due_at"] and row["due_at"] < datetime.now() and not row["submitted_at"]),
            }
        )
        items.append(item)
    return {"items": items, "total": len(items), "pending_count": sum(1 for item in items if item["attempt_status"] in {"not_started", "in_progress", "returned"})}


def _detail_sync(user_id: int, assignment_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        assignment = _assignment_for_student(db, user_id, assignment_id)
        attempt = _attempt(db, assignment_id, user_id)
        reveal = bool(attempt and attempt["status"] in {"submitted", "grading", "graded", "returned"} and assignment["show_analysis_after_submit"])
        rows = db.execute(
            text(
                f"""
                SELECT aq.id AS assignment_question_id,aq.sort_order,aq.points,aq.required,
                       {_question_select_sql()},
                       ans.id AS assignment_answer_id,ans.selected_answer AS saved_selected_answer,
                       ans.answer_text AS saved_answer_text,ans.attachment_ids AS saved_attachment_ids,
                       ans.is_correct AS saved_is_correct,ans.score AS saved_score,
                       ans.review_status AS saved_review_status,ans.teacher_feedback AS saved_teacher_feedback,
                       ans.answered_at AS saved_answered_at
                FROM assignment_questions AS aq
                JOIN questions AS q ON q.id=aq.question_id
                JOIN source_attributions AS s ON s.id=q.source_id
                LEFT JOIN assignment_answers AS ans ON ans.assignment_question_id=aq.id
                  AND ans.attempt_id=:attempt_id
                WHERE aq.assignment_id=:assignment_id ORDER BY aq.sort_order
                """
            ),
            {"assignment_id": assignment_id, "attempt_id": attempt["id"] if attempt else 0},
        ).mappings().all()
    questions = []
    for row in rows:
        question = _row_to_question(row, include_answer=reveal)
        question.update(
            {
                "assignment_question_id": int(row["assignment_question_id"]),
                "sort_order": int(row["sort_order"]),
                "points": float(row["points"]),
                "required": bool(row["required"]),
                "saved_answer": {
                    "id": int(row["assignment_answer_id"]) if row["assignment_answer_id"] else None,
                    "selected_answer": row["saved_selected_answer"],
                    "answer_text": row["saved_answer_text"],
                    "attachment_ids": _parse_ids(row["saved_attachment_ids"]),
                    "is_correct": bool(row["saved_is_correct"]) if row["saved_is_correct"] is not None and reveal else None,
                    "score": float(row["saved_score"] or 0) if row["saved_score"] is not None and reveal else None,
                    "review_status": str(row["saved_review_status"] or "unanswered"),
                    "teacher_feedback": row["saved_teacher_feedback"] if reveal else None,
                    "answered_at": _iso(row["saved_answered_at"]),
                },
            }
        )
        questions.append(question)
    attempt_payload = None
    if attempt:
        attempt_payload = {
            **attempt,
            "id": int(attempt["id"]),
            "assignment_id": int(attempt["assignment_id"]),
            "user_id": int(attempt["user_id"]),
            "attempt_no": int(attempt["attempt_no"] or 1),
            "total_score": float(attempt["total_score"] or 0) if attempt["total_score"] is not None else None,
            "max_score": float(attempt["max_score"] or 0),
            "started_at": _iso(attempt["started_at"]),
            "submitted_at": _iso(attempt["submitted_at"]),
            "graded_at": _iso(attempt["graded_at"]),
            "created_at": _iso(attempt["created_at"]),
            "updated_at": _iso(attempt["updated_at"]),
            "remaining_seconds": _remaining_seconds(assignment, attempt),
            "time_expired": _remaining_seconds(assignment, attempt) == 0,
        }
    return {"assignment": _assignment_base(assignment), "attempt": attempt_payload, "questions": questions, "answers_revealed": reveal}


def _start_sync(user_id: int, assignment_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        assignment = _assignment_for_student(db, user_id, assignment_id, allow_closed=False)
        if assignment["starts_at"] and assignment["starts_at"] > datetime.now():
            raise HTTPException(status_code=409, detail="作业尚未到开始时间。")
        if assignment["due_at"] and assignment["due_at"] < datetime.now():
            raise HTTPException(status_code=409, detail="作业已超过截止时间，无法开始。")
        existing = _attempt(db, assignment_id, user_id)
        if existing:
            if existing["status"] == "returned":
                db.execute(
                    text(
                        "UPDATE assignment_attempts SET status='in_progress',total_score=0,"
                        "submitted_at=NULL,graded_at=NULL,teacher_feedback=NULL WHERE id=:id"
                    ),
                    {"id": existing["id"]},
                )
                db.execute(text("UPDATE assignment_answers SET practice_record_id=NULL,attachment_ids=JSON_ARRAY(),is_correct=NULL,score=NULL,review_status='saved',teacher_feedback=NULL,reviewed_at=NULL,answered_at=NULL WHERE attempt_id=:id"), {"id": existing["id"]})
                db.commit()
            elif existing["status"] == "in_progress":
                pass
            elif existing["status"] in {"submitted", "grading"}:
                raise HTTPException(status_code=409, detail="这份作业正在等待批改，暂时不能再次作答。")
            elif int(existing["attempt_no"] or 1) >= int(assignment["max_attempts"] or 1):
                raise HTTPException(status_code=409, detail="这份作业的作答次数已经用完。")
            else:
                next_attempt = int(existing["attempt_no"] or 1) + 1
                result = db.execute(
                    text(
                        "INSERT INTO assignment_attempts "
                        "(assignment_id,user_id,attempt_no,max_score) "
                        "VALUES (:assignment_id,:user_id,:attempt_no,:max_score)"
                    ),
                    {
                        "assignment_id": assignment_id,
                        "user_id": user_id,
                        "attempt_no": next_attempt,
                        "max_score": assignment["total_score"],
                    },
                )
                attempt_id = int(result.lastrowid)
                db.commit()
                existing = db.execute(
                    text("SELECT * FROM assignment_attempts WHERE id=:id"), {"id": attempt_id}
                ).mappings().one()
        else:
            result = db.execute(
                text("INSERT INTO assignment_attempts (assignment_id,user_id,max_score) VALUES (:assignment_id,:user_id,:max_score)"),
                {"assignment_id": assignment_id, "user_id": user_id, "max_score": assignment["total_score"]},
            )
            attempt_id = int(result.lastrowid)
            db.commit()
            existing = db.execute(text("SELECT * FROM assignment_attempts WHERE id=:id"), {"id": attempt_id}).mappings().one()
    return _detail_sync(user_id, assignment_id)


def _save_answer_sync(user_id: int, assignment_id: int, payload: AssignmentAnswerRequest) -> dict[str, Any]:
    with SessionLocal() as db:
        assignment = _assignment_for_student(db, user_id, assignment_id, allow_closed=False)
        if assignment["due_at"] and assignment["due_at"] < datetime.now():
            raise HTTPException(status_code=409, detail="作业已超过截止时间，不能继续保存答案。")
        attempt = _attempt(db, assignment_id, user_id)
        if not attempt or attempt["status"] != "in_progress":
            raise HTTPException(status_code=409, detail="请先开始作业，或该作业已经提交。")
        if _remaining_seconds(assignment, attempt) == 0:
            raise HTTPException(status_code=409, detail="作业限时已结束，请交卷查看结果。")
        aq = db.execute(
            text("SELECT id,question_id,points FROM assignment_questions WHERE id=:id AND assignment_id=:assignment_id"),
            {"id": payload.assignment_question_id, "assignment_id": assignment_id},
        ).mappings().first()
        if not aq:
            raise HTTPException(status_code=404, detail="作业题目不存在。")
        question = _get_question_sync(int(aq["question_id"]), allow_private=True)
        if not question:
            raise HTTPException(status_code=404, detail="题目不存在。")
        selected = (payload.selected_answer or "").strip().upper()
        answer_text = (payload.answer_text or "").strip()
        if question["question_type"] == "choice" and selected not in {"A", "B", "C", "D"}:
            raise HTTPException(status_code=422, detail="请选择 A、B、C 或 D。")
        if question["question_type"] != "choice" and not answer_text and not payload.attachment_ids:
            raise HTTPException(status_code=422, detail="请填写答案或上传作答图片。")
        attachment_ids = _validate_attachment_ids(db, user_id, payload.attachment_ids)
        requires_manual_review = (
            question["question_type"] in {"proof", "comprehensive"}
            or bool(payload.attachment_ids)
        )
        if requires_manual_review and question["question_type"] != "choice":
            is_correct, normalized_score, review_status = None, None, "pending"
        elif question["question_type"] == "choice":
            is_correct = selected == str(question.get("correct_answer") or "").upper()
            normalized_score, review_status = 100.0 if is_correct else 0.0, "auto_graded"
        else:
            is_correct, normalized_score = _score_subjective(answer_text, question, str(question["question_type"]))
            review_status = "auto_graded"
        points_score = None if normalized_score is None else round(float(aq["points"]) * normalized_score / 100, 2)
        db.execute(
            text(
                """
                INSERT INTO assignment_answers
                  (attempt_id,assignment_question_id,selected_answer,answer_text,attachment_ids,
                   time_spent_seconds,is_correct,score,review_status,answered_at)
                VALUES
                  (:attempt,:question,:selected,:answer_text,:attachments,:time_spent,:is_correct,
                   :score,:review_status,NOW())
                ON DUPLICATE KEY UPDATE selected_answer=VALUES(selected_answer),answer_text=VALUES(answer_text),
                   attachment_ids=VALUES(attachment_ids),time_spent_seconds=VALUES(time_spent_seconds),
                   is_correct=VALUES(is_correct),score=VALUES(score),review_status=VALUES(review_status),
                   teacher_feedback=NULL,answered_at=NOW()
                """
            ),
            {"attempt": attempt["id"], "question": aq["id"], "selected": selected or None, "answer_text": answer_text or None, "attachments": json.dumps(attachment_ids), "time_spent": payload.time_spent_seconds, "is_correct": None if is_correct is None else (1 if is_correct else 0), "score": points_score, "review_status": review_status},
        )
        db.commit()
    return {"saved": True, "assignment_question_id": payload.assignment_question_id, "review_status": review_status, "attachment_count": len(attachment_ids)}


def _submit_sync(user_id: int, assignment_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        assignment = _assignment_for_student(db, user_id, assignment_id, allow_closed=False)
        if assignment["due_at"] and assignment["due_at"] < datetime.now():
            raise HTTPException(status_code=409, detail="作业已超过截止时间，不能交卷。")
        attempt = _attempt(db, assignment_id, user_id)
        if not attempt or attempt["status"] != "in_progress":
            raise HTTPException(status_code=409, detail="作业未开始或已经提交。")
        time_expired = _remaining_seconds(assignment, attempt) == 0
        required_count = int(db.execute(text("SELECT COUNT(*) FROM assignment_questions WHERE assignment_id=:id AND required=1"), {"id": assignment_id}).scalar() or 0)
        answered_count = int(db.execute(text("SELECT COUNT(*) FROM assignment_answers WHERE attempt_id=:id AND answered_at IS NOT NULL"), {"id": attempt["id"]}).scalar() or 0)
        if answered_count < required_count and not time_expired:
            raise HTTPException(status_code=422, detail=f"还有 {required_count - answered_count} 道必答题未完成。")
        answers = db.execute(
            text(
                """
                SELECT ans.*,aq.question_id,aq.points,q.mistake_tags,q.common_errors
                FROM assignment_answers AS ans
                JOIN assignment_questions AS aq ON aq.id=ans.assignment_question_id
                JOIN questions AS q ON q.id=aq.question_id
                WHERE ans.attempt_id=:attempt_id ORDER BY aq.sort_order
                """
            ), {"attempt_id": attempt["id"]}
        ).mappings().all()
        pending = 0
        for answer in answers:
            attachment_ids = _parse_ids(answer["attachment_ids"])
            normalized_score = None if answer["score"] is None else round(float(answer["score"]) / max(float(answer["points"]), 0.01) * 100, 2)
            mistakes = [] if answer["is_correct"] else (_parse_json_list(answer["mistake_tags"]) or _parse_json_list(answer["common_errors"]) or ["知识点需巩固"])
            result = db.execute(
                text(
                    """
                    INSERT INTO practice_records
                      (task_id,user_id,question_id,selected_answer,answer_text,is_correct,score,mistake_tags,
                       time_spent_seconds,practice_mode,assignment_id,assignment_attempt_id,review_status)
                    VALUES
                      (:task_id,:user_id,:question_id,:selected,:answer_text,:is_correct,:score,:mistakes,
                       :time_spent,'assignment',:assignment_id,:attempt_id,:review_status)
                    """
                ),
                {"task_id": f"assignment-{attempt['id']}", "user_id": user_id, "question_id": answer["question_id"], "selected": answer["selected_answer"], "answer_text": answer["answer_text"], "is_correct": answer["is_correct"], "score": normalized_score, "mistakes": json.dumps(mistakes, ensure_ascii=False), "time_spent": answer["time_spent_seconds"], "assignment_id": assignment_id, "attempt_id": attempt["id"], "review_status": "pending" if answer["review_status"] == "pending" else "auto_graded"},
            )
            record_id = int(result.lastrowid)
            for order, file_id in enumerate(_validate_attachment_ids(db, user_id, attachment_ids), start=1):
                db.execute(text("INSERT INTO answer_attachments (practice_record_id,uploaded_file_id,sort_order) VALUES (:record,:file,:sort)"), {"record": record_id, "file": file_id, "sort": order})
            db.execute(text("UPDATE assignment_answers SET practice_record_id=:record WHERE id=:id"), {"record": record_id, "id": answer["id"]})
            pending += 1 if answer["review_status"] == "pending" else 0
        total_score = float(db.execute(text("SELECT COALESCE(SUM(score),0) FROM assignment_answers WHERE attempt_id=:id"), {"id": attempt["id"]}).scalar() or 0)
        next_status = "grading" if pending else "graded"
        db.execute(text("UPDATE assignment_attempts SET status=:status,submitted_at=NOW(),total_score=:score,graded_at=CASE WHEN :status='graded' THEN NOW() ELSE NULL END WHERE id=:id"), {"status": next_status, "score": total_score, "id": attempt["id"]})
        db.execute(text("INSERT INTO user_notifications (user_id,type,title,content,action_url) VALUES (:teacher,'assignment','学生已提交作业',:content,:url)"), {"teacher": assignment["teacher_id"], "content": f"学生已提交《{assignment['title']}》，待批改 {pending} 题。", "url": f"/teacher/assignments/{assignment_id}"})
        report_stats = db.execute(
            text(
                """
                SELECT COUNT(ans.id) AS answer_count,
                       ROUND(AVG(CASE WHEN ans.is_correct IS NOT NULL THEN ans.is_correct END)*100,1) AS accuracy,
                       SUM(CASE WHEN ans.review_status='pending' THEN 1 ELSE 0 END) AS pending_count,
                       COUNT(DISTINCT q.knowledge_tag) AS knowledge_count
                FROM assignment_attempts aa
                JOIN assignment_answers ans ON ans.attempt_id=aa.id
                JOIN assignment_questions aq ON aq.id=ans.assignment_question_id
                JOIN questions q ON q.id=aq.question_id
                WHERE aa.assignment_id=:assignment_id AND aa.submitted_at IS NOT NULL
                """
            ),
            {"assignment_id": assignment_id},
        ).mappings().one()
        report_content = (
            f"《{assignment['title']}》当前累计 {int(report_stats['answer_count'] or 0)} 次作答，"
            f"已判定题正确率 {float(report_stats['accuracy'] or 0):g}%，覆盖 {int(report_stats['knowledge_count'] or 0)} 个知识点，"
            f"待人工批改 {int(report_stats['pending_count'] or 0)} 题。"
        )
        db.execute(
            text(
                """
                INSERT INTO user_notifications (user_id,type,title,content,action_url)
                VALUES (:teacher,'assignment_report','作业分析摘要已更新',:content,:url)
                """
            ),
            {"teacher": assignment["teacher_id"], "content": report_content, "url": f"/teacher/assignments/{assignment_id}"},
        )
        db.commit()
        evaluation_task_id = f"assignment-{attempt['id']}"
    data = _detail_sync(user_id, assignment_id)
    data["evaluation"] = evaluate(user_id, evaluation_task_id).model_dump()
    data["review_brief"] = _practice_review_brief_sync(
        user_id,
        evaluation_task_id,
        title=f"《{assignment['title']}》作业复盘",
        assignment_id=assignment_id,
    )
    return data


@router.get("")
async def list_assignments(current: dict[str, Any] = Depends(require_student)) -> dict[str, Any]:
    return await asyncio.to_thread(_list_sync, int(current["id"]))


@router.get("/{assignment_id}")
async def assignment_detail(assignment_id: int, current: dict[str, Any] = Depends(require_student)) -> dict[str, Any]:
    return await asyncio.to_thread(_detail_sync, int(current["id"]), assignment_id)


@router.post("/{assignment_id}/start")
async def start_assignment(assignment_id: int, current: dict[str, Any] = Depends(require_student)) -> dict[str, Any]:
    return await asyncio.to_thread(_start_sync, int(current["id"]), assignment_id)


@router.put("/{assignment_id}/answers")
async def save_answer(assignment_id: int, payload: AssignmentAnswerRequest, current: dict[str, Any] = Depends(require_student)) -> dict[str, Any]:
    return await asyncio.to_thread(_save_answer_sync, int(current["id"]), assignment_id, payload)


@router.post("/{assignment_id}/submit")
async def submit_assignment(assignment_id: int, current: dict[str, Any] = Depends(require_student)) -> dict[str, Any]:
    return await asyncio.to_thread(_submit_sync, int(current["id"]), assignment_id)


@router.get("/{assignment_id}/result")
async def assignment_result(assignment_id: int, current: dict[str, Any] = Depends(require_student)) -> dict[str, Any]:
    data = await asyncio.to_thread(_detail_sync, int(current["id"]), assignment_id)
    if not data["attempt"] or data["attempt"]["status"] == "in_progress":
        raise HTTPException(status_code=409, detail="请提交作业后再查看结果。")
    return data
