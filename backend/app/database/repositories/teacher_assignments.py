import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text

from ..session import SessionLocal
from ...api.teacher_schemas import AssignmentWriteRequest, ReviewRequest
from ...api.routes.teacher import _audit, _owned_class
from ...api.utils import _parse_json_list
from .teacher_common import _iso
from .teacher_questions import _question_columns, _question_dict


def _owned_assignment(db: Any, teacher_id: int, assignment_id: int) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT a.*, c.name AS class_name, c.stage, c.course
            FROM assignments AS a JOIN classes AS c ON c.id=a.class_id
            WHERE a.id=:assignment_id AND a.teacher_id=:teacher_id LIMIT 1
            """
        ),
        {"assignment_id": assignment_id, "teacher_id": teacher_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="作业不存在，或不属于当前教师。")
    return dict(row)

def _assignment_summary_row(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["id"]), "title": str(row["title"]), "description": str(row["description"] or ""),
        "class_id": int(row["class_id"]), "class_name": str(row["class_name"]), "status": str(row["status"]),
        "question_count": int(row["question_count"] or 0), "student_count": int(row["student_count"] or 0),
        "started_count": int(row["started_count"] or 0), "submitted_count": int(row["submitted_count"] or 0),
        "graded_count": int(row["graded_count"] or 0), "pending_review": int(row["pending_review"] or 0),
        "total_score": float(row["total_score"] or 0), "due_at": _iso(row["due_at"]),
        "published_at": _iso(row["published_at"]), "created_at": _iso(row["created_at"]),
    }

def _assignments_sync(teacher_id: int, class_id: int | None, assignment_status: str | None) -> dict[str, Any]:
    clauses = ["a.teacher_id=:teacher_id", "a.status <> 'archived'"]
    params: dict[str, Any] = {"teacher_id": teacher_id}
    if class_id:
        clauses.append("a.class_id=:class_id"); params["class_id"] = class_id
    if assignment_status:
        clauses.append("a.status=:status"); params["status"] = assignment_status
    with SessionLocal() as db:
        rows = db.execute(
            text(
                f"""
                SELECT a.id,a.title,a.description,a.class_id,c.name AS class_name,a.status,a.due_at,
                       a.published_at,a.created_at,a.total_score,
                       COUNT(DISTINCT aq.id) AS question_count,
                       COUNT(DISTINCT cm.student_id) AS student_count,
                       COUNT(DISTINCT aa.id) AS started_count,
                       COUNT(DISTINCT CASE WHEN aa.status IN ('submitted','grading','graded','returned') THEN aa.id END) AS submitted_count,
                       COUNT(DISTINCT CASE WHEN aa.status='graded' THEN aa.id END) AS graded_count,
                       COUNT(DISTINCT CASE WHEN ans.review_status='pending' THEN ans.id END) AS pending_review
                FROM assignments AS a
                JOIN classes AS c ON c.id=a.class_id
                LEFT JOIN assignment_questions AS aq ON aq.assignment_id=a.id
                LEFT JOIN class_members AS cm ON cm.class_id=a.class_id AND cm.status='active'
                LEFT JOIN assignment_attempts AS aa ON aa.id=(
                  SELECT latest.id FROM assignment_attempts AS latest
                  WHERE latest.assignment_id=a.id AND latest.user_id=cm.student_id
                  ORDER BY latest.attempt_no DESC LIMIT 1
                )
                LEFT JOIN assignment_answers AS ans ON ans.attempt_id=aa.id
                WHERE {' AND '.join(clauses)}
                GROUP BY a.id,a.title,a.description,a.class_id,c.name,a.status,a.due_at,a.published_at,a.created_at,a.total_score
                ORDER BY a.created_at DESC
                """
            ), params
        ).mappings().all()
    items = [_assignment_summary_row(row) for row in rows]
    return {"items": items, "total": len(items)}

def _assignment_detail_sync(teacher_id: int, assignment_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        assignment = _owned_assignment(db, teacher_id, assignment_id)
        questions = db.execute(
            text(
                f"""
                SELECT aq.id AS assignment_question_id, aq.sort_order, aq.points, aq.required,
                       {_question_columns()}
                FROM assignment_questions AS aq
                JOIN questions AS q ON q.id=aq.question_id
                JOIN source_attributions AS s ON s.id=q.source_id
                WHERE aq.assignment_id=:assignment_id ORDER BY aq.sort_order
                """
            ), {"assignment_id": assignment_id}
        ).mappings().all()
        students = db.execute(
            text(
                """
                SELECT u.id,u.username,aa.id AS attempt_id,aa.status,aa.started_at,aa.submitted_at,
                       aa.total_score,aa.max_score,aa.teacher_feedback,
                       SUM(CASE WHEN ans.review_status='pending' THEN 1 ELSE 0 END) AS pending_review,
                       COUNT(ans.id) AS answered_count
                FROM class_members AS cm
                JOIN users AS u ON u.id=cm.student_id
                LEFT JOIN assignment_attempts AS aa ON aa.id=(
                  SELECT latest.id FROM assignment_attempts AS latest
                  WHERE latest.assignment_id=:assignment_id AND latest.user_id=u.id
                  ORDER BY latest.attempt_no DESC LIMIT 1
                )
                LEFT JOIN assignment_answers AS ans ON ans.attempt_id=aa.id
                WHERE cm.class_id=:class_id AND cm.status='active'
                GROUP BY u.id,u.username,aa.id,aa.status,aa.started_at,aa.submitted_at,aa.total_score,aa.max_score,aa.teacher_feedback
                ORDER BY aa.submitted_at DESC,u.username
                """
            ), {"assignment_id": assignment_id, "class_id": assignment["class_id"]}
        ).mappings().all()
    return {
        "assignment": {**assignment, "id": int(assignment["id"]), "class_id": int(assignment["class_id"]), "teacher_id": int(assignment["teacher_id"]), "total_score": float(assignment["total_score"] or 0), "show_analysis_after_submit": bool(assignment["show_analysis_after_submit"]), "starts_at": _iso(assignment["starts_at"]), "due_at": _iso(assignment["due_at"]), "published_at": _iso(assignment["published_at"]), "created_at": _iso(assignment["created_at"]), "updated_at": _iso(assignment["updated_at"])},
        "questions": [_question_dict(row) | {"assignment_question_id": int(row["assignment_question_id"]), "sort_order": int(row["sort_order"]), "points": float(row["points"]), "required": bool(row["required"])} for row in questions],
        "students": [{**dict(row), "id": int(row["id"]), "attempt_id": int(row["attempt_id"]) if row["attempt_id"] else None, "total_score": float(row["total_score"] or 0) if row["total_score"] is not None else None, "max_score": float(row["max_score"] or 0), "pending_review": int(row["pending_review"] or 0), "answered_count": int(row["answered_count"] or 0), "started_at": _iso(row["started_at"]), "submitted_at": _iso(row["submitted_at"])} for row in students],
    }

def _validate_assignment_questions(db: Any, teacher_id: int, question_ids: list[int], publishing: bool) -> None:
    placeholders = ",".join(f":q{i}" for i in range(len(question_ids)))
    params = {f"q{i}": qid for i, qid in enumerate(question_ids)} | {"teacher_id": teacher_id}
    visibility_clause = "AND (created_by=:teacher_id OR visibility='public')"
    clause = f"AND (publish_status='published' OR created_by=:teacher_id) {visibility_clause}" if not publishing else f"AND publish_status='published' {visibility_clause}"
    count = db.execute(text(f"SELECT COUNT(*) FROM questions WHERE id IN ({placeholders}) AND deleted_at IS NULL {clause}"), params).scalar()
    if int(count or 0) != len(question_ids):
        raise HTTPException(status_code=422, detail="部分题目不存在、无权使用，或尚未发布。")

def _create_assignment_sync(teacher_id: int, payload: AssignmentWriteRequest) -> dict[str, Any]:
    with SessionLocal() as db:
        class_row = _owned_class(db, teacher_id, payload.class_id)
        _validate_assignment_questions(db, teacher_id, payload.question_ids, payload.publish)
        points = payload.points or [round(100 / len(payload.question_ids), 2)] * len(payload.question_ids)
        total_score = round(sum(points), 2)
        status_value = "published" if payload.publish else "draft"
        result = db.execute(
            text(
                """
                INSERT INTO assignments
                  (teacher_id,class_id,title,description,status,starts_at,due_at,time_limit_minutes,
                   max_attempts,show_analysis_after_submit,total_score,published_at)
                VALUES
                  (:teacher_id,:class_id,:title,:description,:status,:starts_at,:due_at,:time_limit,
                   :max_attempts,:show_analysis,:total_score,:published_at)
                """
            ),
            {"teacher_id": teacher_id, "class_id": payload.class_id, "title": payload.title.strip(), "description": (payload.description or "").strip() or None, "status": status_value, "starts_at": payload.starts_at, "due_at": payload.due_at, "time_limit": payload.time_limit_minutes, "max_attempts": payload.max_attempts, "show_analysis": 1 if payload.show_analysis_after_submit else 0, "total_score": total_score, "published_at": datetime.now() if payload.publish else None},
        )
        assignment_id = int(result.lastrowid)
        for index, (question_id, point) in enumerate(zip(payload.question_ids, points), start=1):
            db.execute(text("INSERT INTO assignment_questions (assignment_id,question_id,sort_order,points) VALUES (:a,:q,:n,:p)"), {"a": assignment_id, "q": question_id, "n": index, "p": point})
        if payload.publish:
            _notify_assignment(db, assignment_id, class_row, payload.title, "新作业已发布")
        _audit(db, teacher_id, "assignment.created", "assignment", assignment_id, {"class_id": payload.class_id, "status": status_value, "question_count": len(payload.question_ids)})
        db.commit()
    return _assignment_detail_sync(teacher_id, assignment_id)

def _update_assignment_sync(teacher_id: int, assignment_id: int, payload: AssignmentWriteRequest) -> dict[str, Any]:
    with SessionLocal() as db:
        assignment = _owned_assignment(db, teacher_id, assignment_id)
        if assignment["status"] != "draft":
            raise HTTPException(status_code=409, detail="只有草稿作业可以编辑。")
        _owned_class(db, teacher_id, payload.class_id)
        _validate_assignment_questions(db, teacher_id, payload.question_ids, payload.publish)
        points = payload.points or [round(100 / len(payload.question_ids), 2)] * len(payload.question_ids)
        total_score = round(sum(points), 2)
        next_status = "published" if payload.publish else "draft"
        previous_rows = db.execute(
            text("SELECT question_id,points,sort_order FROM assignment_questions WHERE assignment_id=:id ORDER BY sort_order"),
            {"id": assignment_id},
        ).mappings().all()
        previous_ids = [int(row["question_id"]) for row in previous_rows]
        adjustment = None
        if bool(assignment.get("ai_generated")):
            next_ids = [int(value) for value in payload.question_ids]
            previous_points = {int(row["question_id"]): float(row["points"] or 0) for row in previous_rows}
            next_points = {question_id: float(point) for question_id, point in zip(next_ids, points)}
            adjustment = {
                "removed_question_ids": [question_id for question_id in previous_ids if question_id not in next_ids],
                "added_question_ids": [question_id for question_id in next_ids if question_id not in previous_ids],
                "reordered": [question_id for question_id in next_ids if question_id in previous_ids]
                != [question_id for question_id in previous_ids if question_id in next_ids],
                "point_changes": [
                    {"question_id": question_id, "from": previous_points[question_id], "to": next_points[question_id]}
                    for question_id in next_ids
                    if question_id in previous_points and previous_points[question_id] != next_points[question_id]
                ],
                "title_changed": str(assignment.get("title") or "") != payload.title.strip(),
                "time_limit_changed": assignment.get("time_limit_minutes") != payload.time_limit_minutes,
                "saved_at": datetime.now().isoformat(timespec="seconds"),
            }
        db.execute(
            text(
                """
                UPDATE assignments SET class_id=:class_id,title=:title,description=:description,
                  status=:status,starts_at=:starts_at,due_at=:due_at,time_limit_minutes=:time_limit,
                  max_attempts=:max_attempts,show_analysis_after_submit=:show_analysis,
                  total_score=:total_score,published_at=CASE WHEN :status='published' THEN NOW() ELSE NULL END,
                  teacher_adjustments_json=COALESCE(:teacher_adjustments_json,teacher_adjustments_json)
                WHERE id=:assignment_id AND teacher_id=:teacher_id
                """
            ),
            {"class_id": payload.class_id, "title": payload.title.strip(), "description": (payload.description or "").strip() or None, "status": next_status, "starts_at": payload.starts_at, "due_at": payload.due_at, "time_limit": payload.time_limit_minutes, "max_attempts": payload.max_attempts, "show_analysis": 1 if payload.show_analysis_after_submit else 0, "total_score": total_score, "teacher_adjustments_json": json.dumps(adjustment, ensure_ascii=False) if adjustment else None, "assignment_id": assignment_id, "teacher_id": teacher_id},
        )
        db.execute(text("DELETE FROM assignment_questions WHERE assignment_id=:id"), {"id": assignment_id})
        for index, (question_id, point) in enumerate(zip(payload.question_ids, points), start=1):
            db.execute(text("INSERT INTO assignment_questions (assignment_id,question_id,sort_order,points) VALUES (:a,:q,:n,:p)"), {"a": assignment_id, "q": question_id, "n": index, "p": point})
        if payload.publish:
            class_row = _owned_class(db, teacher_id, payload.class_id)
            _notify_assignment(db, assignment_id, class_row, payload.title, "新作业已发布")
        _audit(db, teacher_id, "assignment.updated", "assignment", assignment_id, {"status": next_status, "question_count": len(payload.question_ids)})
        db.commit()
    return _assignment_detail_sync(teacher_id, assignment_id)

def _notify_assignment(db: Any, assignment_id: int, class_row: dict[str, Any], title: str, notification_title: str) -> None:
    db.execute(
        text(
            """
            INSERT INTO user_notifications (user_id,type,title,content,action_url)
            SELECT cm.student_id,'assignment',:notification_title,
                   CONCAT(:class_name,'：',:assignment_title),:action_url
            FROM class_members AS cm WHERE cm.class_id=:class_id AND cm.status='active'
            """
        ),
        {"notification_title": notification_title, "class_name": class_row["name"], "assignment_title": title, "action_url": f"/assignments/{assignment_id}", "class_id": class_row["id"]},
    )

def _publish_assignment_sync(teacher_id: int, assignment_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        assignment = _owned_assignment(db, teacher_id, assignment_id)
        if assignment["status"] != "draft":
            raise HTTPException(status_code=409, detail="只有草稿作业可以发布。")
        question_ids = [int(row[0]) for row in db.execute(text("SELECT question_id FROM assignment_questions WHERE assignment_id=:id"), {"id": assignment_id})]
        if not question_ids:
            raise HTTPException(status_code=422, detail="请至少添加一道题后再发布。")
        _validate_assignment_questions(db, teacher_id, question_ids, True)
        db.execute(text("UPDATE assignments SET status='published',published_at=NOW() WHERE id=:id"), {"id": assignment_id})
        _notify_assignment(db, assignment_id, {"id": assignment["class_id"], "name": assignment["class_name"]}, assignment["title"], "新作业已发布")
        _audit(db, teacher_id, "assignment.published", "assignment", assignment_id, {})
        db.commit()
    return _assignment_detail_sync(teacher_id, assignment_id)

def _close_assignment_sync(teacher_id: int, assignment_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        assignment = _owned_assignment(db, teacher_id, assignment_id)
        if assignment["status"] not in {"published", "draft"}:
            raise HTTPException(status_code=409, detail="当前作业不能关闭。")
        db.execute(text("UPDATE assignments SET status='closed' WHERE id=:id"), {"id": assignment_id})
        _audit(db, teacher_id, "assignment.closed", "assignment", assignment_id, {})
        db.commit()
    return _assignment_detail_sync(teacher_id, assignment_id)

def _archive_assignment_sync(teacher_id: int, assignment_id: int) -> dict[str, bool]:
    with SessionLocal() as db:
        assignment = _owned_assignment(db, teacher_id, assignment_id)
        if assignment["status"] == "published":
            raise HTTPException(status_code=409, detail="进行中的作业不能归档，请先结束作业。")
        db.execute(text("UPDATE assignments SET status='archived' WHERE id=:id"), {"id": assignment_id})
        _audit(db, teacher_id, "assignment.archived", "assignment", assignment_id, {})
        db.commit()
    return {"archived": True}

def _review_queue_sync(teacher_id: int, assignment_id: int | None, review_status: str) -> dict[str, Any]:
    clauses = ["pr.review_status=:review_status"]
    params: dict[str, Any] = {"teacher_id": teacher_id, "review_status": review_status}
    if assignment_id:
        clauses.append("pr.assignment_id=:assignment_id"); params["assignment_id"] = assignment_id
    with SessionLocal() as db:
        rows = db.execute(
            text(
                f"""
                SELECT DISTINCT pr.id,u.id AS student_id,u.username,q.question_text,q.question_type,
                       q.course,q.knowledge_tag,q.standard_answer,q.analysis_text,q.key_steps,
                       pr.answer_text,pr.selected_answer,pr.score,pr.teacher_score,pr.teacher_feedback,
                       pr.review_status,pr.answered_at,pr.assignment_id,a.title AS assignment_title,
                       aq.points,aa.id AS assignment_answer_id,
                       GROUP_CONCAT(DISTINCT uf.id ORDER BY uf.id) AS attachment_ids
                FROM practice_records AS pr
                JOIN users AS u ON u.id=pr.user_id
                JOIN questions AS q ON q.id=pr.question_id
                JOIN class_members AS cm ON cm.student_id=u.id AND cm.status='active'
                JOIN classes AS c ON c.id=cm.class_id AND c.teacher_id=:teacher_id AND c.status='active'
                LEFT JOIN assignments AS a ON a.id=pr.assignment_id
                LEFT JOIN assignment_answers AS aa ON aa.practice_record_id=pr.id
                LEFT JOIN assignment_questions AS aq ON aq.id=aa.assignment_question_id
                LEFT JOIN answer_attachments AS att ON att.practice_record_id=pr.id
                LEFT JOIN uploaded_files AS uf ON uf.id=att.uploaded_file_id
                WHERE {' AND '.join(clauses)}
                  AND (pr.assignment_id IS NULL OR a.teacher_id=:teacher_id)
                GROUP BY pr.id,u.id,u.username,q.question_text,q.question_type,q.course,q.knowledge_tag,
                         q.standard_answer,q.analysis_text,q.key_steps,pr.answer_text,pr.selected_answer,
                         pr.score,pr.teacher_score,pr.teacher_feedback,pr.review_status,pr.answered_at,
                         pr.assignment_id,a.title,aq.points,aa.id
                ORDER BY pr.answered_at ASC
                """
            ), params
        ).mappings().all()
    items = []
    for row in rows:
        item = dict(row)
        item["id"] = int(row["id"]); item["student_id"] = int(row["student_id"])
        item["assignment_id"] = int(row["assignment_id"]) if row["assignment_id"] else None
        item["assignment_answer_id"] = int(row["assignment_answer_id"]) if row["assignment_answer_id"] else None
        item["points"] = float(row["points"] or 0) if row["points"] is not None else None
        item["score"] = float(row["score"] or 0) if row["score"] is not None else None
        item["teacher_score"] = float(row["teacher_score"] or 0) if row["teacher_score"] is not None else None
        item["key_steps"] = _parse_json_list(row["key_steps"])
        item["answered_at"] = _iso(row["answered_at"])
        ids = [int(value) for value in str(row["attachment_ids"] or "").split(",") if value]
        item["attachments"] = [{"id": file_id, "url": f"/api/files/{file_id}"} for file_id in ids]
        items.append(item)
    return {"items": items, "total": len(items)}

def _grade_sync(teacher_id: int, record_id: int, payload: ReviewRequest) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT DISTINCT pr.id,pr.user_id,pr.assignment_id,pr.assignment_attempt_id,aa.id AS answer_id,
                       aq.points,aa.attempt_id
                FROM practice_records AS pr
                JOIN class_members AS cm ON cm.student_id=pr.user_id AND cm.status='active'
                JOIN classes AS c ON c.id=cm.class_id AND c.teacher_id=:teacher_id AND c.status='active'
                LEFT JOIN assignments AS assignment_owner ON assignment_owner.id=pr.assignment_id
                LEFT JOIN assignment_answers AS aa ON aa.practice_record_id=pr.id
                LEFT JOIN assignment_questions AS aq ON aq.id=aa.assignment_question_id
                WHERE pr.id=:record_id
                  AND (pr.assignment_id IS NULL OR assignment_owner.teacher_id=:teacher_id)
                LIMIT 1
                """
            ), {"teacher_id": teacher_id, "record_id": record_id}
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="作答不存在，或不属于你管理的学生。")
        db.execute(
            text(
                """
                UPDATE practice_records SET is_correct=:is_correct,score=:score,review_status='graded',
                  teacher_score=:score,teacher_feedback=:feedback,reviewer_id=:teacher_id,
                  reviewed_at=NOW(),correction_required=:correction
                WHERE id=:record_id
                """
            ), {"is_correct": 1 if payload.score >= 60 else 0, "score": payload.score, "feedback": payload.feedback.strip(), "teacher_id": teacher_id, "correction": 1 if payload.correction_required else 0, "record_id": record_id}
        )
        if row["answer_id"]:
            points_score = round(payload.score / 100 * float(row["points"] or 0), 2)
            db.execute(text("UPDATE assignment_answers SET is_correct=:ok,score=:score,review_status='graded',teacher_feedback=:feedback,reviewed_at=NOW() WHERE id=:id"), {"ok": 1 if payload.score >= 60 else 0, "score": points_score, "feedback": payload.feedback.strip(), "id": row["answer_id"]})
            pending = int(db.execute(text("SELECT COUNT(*) FROM assignment_answers WHERE attempt_id=:attempt AND review_status='pending'"), {"attempt": row["attempt_id"]}).scalar() or 0)
            total = float(db.execute(text("SELECT COALESCE(SUM(score),0) FROM assignment_answers WHERE attempt_id=:attempt"), {"attempt": row["attempt_id"]}).scalar() or 0)
            if pending == 0:
                correction_count = int(
                    db.execute(
                        text(
                            "SELECT COUNT(*) FROM practice_records AS pr "
                            "JOIN assignment_answers AS current_answer "
                            "  ON current_answer.practice_record_id=pr.id "
                            "WHERE current_answer.attempt_id=:attempt "
                            "  AND pr.correction_required=1"
                        ),
                        {"attempt": row["attempt_id"]},
                    ).scalar()
                    or 0
                )
                final_status = "returned" if correction_count else "graded"
                db.execute(text("UPDATE assignment_attempts SET status=:status,total_score=:total,graded_at=NOW() WHERE id=:attempt"), {"status": final_status, "total": total, "attempt": row["attempt_id"]})
        db.execute(
            text("INSERT INTO user_notifications (user_id,type,title,content,action_url) VALUES (:user_id,'review','教师已完成批改',:content,:url)"),
            {"user_id": row["user_id"], "content": f"本次作答得分 {payload.score:g} 分。教师评语：{payload.feedback.strip()}", "url": f"/assignments/{row['assignment_id']}" if row["assignment_id"] else "/review"},
        )
        _audit(db, teacher_id, "submission.graded", "practice_record", record_id, payload.model_dump())
        db.commit()
    return {"id": record_id, "review_status": "graded", "score": payload.score, "feedback": payload.feedback, "correction_required": payload.correction_required}
