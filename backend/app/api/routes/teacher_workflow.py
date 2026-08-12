import asyncio
import io
import json
import uuid
from datetime import datetime
from typing import Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ...database.session import SessionLocal
from ...security import require_teacher
from ...utils.question_document_parser import QuestionDocumentError, parse_question_document
from .learning import _parse_json_list, _row_to_question, _score_subjective
from .teacher import _audit, _ensure_teacher_tables_sync, _owned_class


router = APIRouter(prefix="/api/teacher", tags=["teacher-workflow"])

QUESTION_TYPES = {"choice", "blank", "calculation", "proof", "comprehensive"}
TYPE_LABELS = {
    "choice": "选择题",
    "blank": "填空题",
    "calculation": "计算题",
    "proof": "证明题",
    "comprehensive": "综合题",
}


class QuestionWriteRequest(BaseModel):
    question_type: Literal["choice", "blank", "calculation", "proof", "comprehensive"]
    stage: str = Field(min_length=2, max_length=16)
    course: str = Field(min_length=1, max_length=128)
    knowledge_tag: str = Field(min_length=1, max_length=160)
    fine_tag: str = Field(min_length=1, max_length=160)
    difficulty: int = Field(default=3, ge=1, le=5)
    question_text: str = Field(min_length=2, max_length=12000)
    option_a: str | None = Field(default=None, max_length=4000)
    option_b: str | None = Field(default=None, max_length=4000)
    option_c: str | None = Field(default=None, max_length=4000)
    option_d: str | None = Field(default=None, max_length=4000)
    correct_answer: str | None = Field(default=None, max_length=16)
    standard_answer: str = Field(min_length=1, max_length=12000)
    analysis_text: str = Field(min_length=1, max_length=20000)
    key_steps: list[str] = Field(default_factory=list, max_length=20)
    common_errors: list[str] = Field(default_factory=list, max_length=20)
    mistake_tags: list[str] = Field(default_factory=list, max_length=20)
    attachment_ids: list[int] = Field(default_factory=list, max_length=5)
    analysis_attachment_ids: list[int] = Field(default_factory=list, max_length=5)
    visibility: Literal["public", "class"] = "public"
    publish_status: Literal["draft", "published"] = "draft"

    @model_validator(mode="after")
    def validate_choice(self) -> "QuestionWriteRequest":
        if self.question_type == "choice":
            if not all([self.option_a, self.option_b, self.option_c, self.option_d]):
                raise ValueError("选择题必须填写 A、B、C、D 四个选项。")
            if (self.correct_answer or "").strip().upper() not in {"A", "B", "C", "D"}:
                raise ValueError("选择题正确答案必须是 A、B、C 或 D。")
        return self


class AssignmentWriteRequest(BaseModel):
    class_id: int = Field(ge=1)
    title: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    question_ids: list[int] = Field(min_length=1, max_length=100)
    points: list[float] | None = None
    starts_at: datetime | None = None
    due_at: datetime | None = None
    time_limit_minutes: int | None = Field(default=None, ge=5, le=600)
    max_attempts: int = Field(default=1, ge=1, le=5)
    show_analysis_after_submit: bool = True
    publish: bool = False

    @model_validator(mode="after")
    def validate_assignment(self) -> "AssignmentWriteRequest":
        if len(set(self.question_ids)) != len(self.question_ids):
            raise ValueError("作业题目不能重复。")
        if self.points is not None and len(self.points) != len(self.question_ids):
            raise ValueError("题目分值数量必须和题目数量一致。")
        if self.due_at and self.starts_at and self.due_at <= self.starts_at:
            raise ValueError("截止时间必须晚于开始时间。")
        return self


class QuestionImportCommitRequest(BaseModel):
    questions: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    publish_status: Literal["draft", "published"] = "draft"
    visibility: Literal["public", "class"] = "public"
    source_file_name: str = Field(default="导入文件", max_length=255)
    skip_duplicates: bool = True
    reuse_duplicates: bool = False


class ReviewRequest(BaseModel):
    score: float = Field(ge=0, le=100)
    feedback: str = Field(min_length=1, max_length=4000)
    correction_required: bool = False


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _json(value: list[str]) -> str:
    return json.dumps([str(item).strip() for item in value if str(item).strip()], ensure_ascii=False)


def _managed_student(db: Any, teacher_id: int, student_id: int) -> None:
    exists = db.execute(
        text(
            """
            SELECT 1
            FROM class_members AS cm
            JOIN classes AS c ON c.id = cm.class_id
            WHERE c.teacher_id = :teacher_id AND c.status = 'active'
              AND cm.student_id = :student_id AND cm.status = 'active'
            LIMIT 1
            """
        ),
        {"teacher_id": teacher_id, "student_id": student_id},
    ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="学生不存在，或不在你管理的班级中。")


def _teacher_question_source_id(db: Any) -> int:
    source_id = db.execute(
        text("SELECT id FROM source_attributions WHERE source_name = '教师自建题库' LIMIT 1")
    ).scalar()
    if source_id:
        return int(source_id)
    result = db.execute(
        text(
            """
            INSERT INTO source_attributions
              (source_name, source_url, license_name, license_url, usage_note)
            VALUES
              ('教师自建题库', 'local://teacher-authored', '教师原创/内部教学使用',
               'local://teacher-authored', '教师端创建、维护并发布的校内教学题目。')
            """
        )
    )
    return int(result.lastrowid)


def _question_dict(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["type_label"] = TYPE_LABELS.get(str(item["question_type"]), str(item["question_type"]))
    item["options"] = {
        key: value
        for key, value in {
            "A": item.get("option_a"),
            "B": item.get("option_b"),
            "C": item.get("option_c"),
            "D": item.get("option_d"),
        }.items()
        if value
    }
    item["key_steps"] = _parse_json_list(item.get("key_steps"))
    item["common_errors"] = _parse_json_list(item.get("common_errors"))
    item["mistake_tags"] = _parse_json_list(item.get("mistake_tags"))
    for key in ("created_at", "updated_at", "published_at"):
        item[key] = _iso(item.get(key))
    item["editable"] = bool(item.get("created_by"))
    item.setdefault("attachments", [])
    item.setdefault("analysis_attachments", [])
    return item


def _question_columns() -> str:
    return """
      q.id, q.source_id, q.created_by, q.visibility, q.publish_status, q.version,
      q.published_at, q.source_question_no, q.source_path, q.question_type,
      q.stage, q.course, q.knowledge_node_id, q.knowledge_tag, q.fine_tag,
      q.difficulty, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d,
      q.correct_answer, q.standard_answer, q.analysis_text, q.key_steps,
      q.common_errors, q.mistake_tags, q.created_at, q.updated_at,
      (SELECT COUNT(*) FROM question_attachments qa WHERE qa.question_id=q.id AND qa.attachment_type='question') AS attachment_count,
      (SELECT COUNT(*) FROM question_attachments qa WHERE qa.question_id=q.id AND qa.attachment_type='analysis') AS analysis_attachment_count,
      s.source_name
    """


def _student_list_sync(teacher_id: int, class_id: int | None, search: str | None) -> dict[str, Any]:
    _ensure_teacher_tables_sync()
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


def _questions_sync(
    teacher_id: int,
    scope: str,
    search: str | None,
    stage: str | None,
    course: str | None,
    question_type: str | None,
    publish_status: str | None,
    include_legacy: bool,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    clauses = ["q.deleted_at IS NULL"]
    params: dict[str, Any] = {"teacher_id": teacher_id, "offset": (page - 1) * page_size, "limit": page_size}
    if scope == "mine":
        clauses.append("q.created_by = :teacher_id")
    elif scope == "public":
        clauses.append("q.publish_status = 'published' AND q.visibility = 'public'")
    else:
        clauses.append("(q.created_by = :teacher_id OR (q.publish_status = 'published' AND q.visibility = 'public'))")
    if not include_legacy:
        clauses.append("(q.created_by IS NOT NULL OR s.source_name <> 'WeBWorK Open Problem Library')")
    for column, value in (("stage", stage), ("course", course), ("question_type", question_type), ("publish_status", publish_status)):
        if value:
            clauses.append(f"q.{column} = :{column}")
            params[column] = value
    if search:
        clauses.append("(q.question_text LIKE :search OR q.knowledge_tag LIKE :search OR q.fine_tag LIKE :search)")
        params["search"] = f"%{search.strip()}%"
    where = " AND ".join(clauses)
    with SessionLocal() as db:
        total = int(
            db.execute(
                text(
                    f"SELECT COUNT(*) FROM questions AS q "
                    f"JOIN source_attributions AS s ON s.id=q.source_id WHERE {where}"
                ),
                params,
            ).scalar()
            or 0
        )
        rows = db.execute(
            text(
                f"""
                SELECT {_question_columns()}
                FROM questions AS q
                JOIN source_attributions AS s ON s.id = q.source_id
                WHERE {where}
                ORDER BY (q.created_by = :teacher_id) DESC, q.updated_at DESC, q.id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()
        summary = db.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       SUM(q.created_by = :teacher_id) AS mine,
                       SUM(q.created_by = :teacher_id AND q.publish_status = 'draft') AS drafts,
                       SUM(q.created_by = :teacher_id AND q.publish_status = 'published') AS published
                FROM questions AS q
                JOIN source_attributions AS s ON s.id=q.source_id
                WHERE q.deleted_at IS NULL
                  AND (q.created_by=:teacher_id OR (q.publish_status='published' AND q.visibility='public'))
                  AND (q.created_by IS NOT NULL OR s.source_name <> 'WeBWorK Open Problem Library')
                """
            ),
            {"teacher_id": teacher_id},
        ).mappings().one()
    return {
        "items": [_question_dict(row) | {"editable": row["created_by"] == teacher_id} for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": {key: int(summary[key] or 0) for key in ("total", "mine", "drafts", "published")},
    }


def _get_owned_question(db: Any, teacher_id: int, question_id: int) -> dict[str, Any]:
    row = db.execute(
        text(f"SELECT {_question_columns()} FROM questions AS q JOIN source_attributions AS s ON s.id=q.source_id WHERE q.id=:question_id AND q.created_by=:teacher_id AND q.deleted_at IS NULL"),
        {"question_id": question_id, "teacher_id": teacher_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="题目不存在，或不是你创建的题目。")
    return dict(row)


def _question_values(payload: QuestionWriteRequest) -> dict[str, Any]:
    return {
        **payload.model_dump(exclude={"key_steps", "common_errors", "mistake_tags", "attachment_ids", "analysis_attachment_ids"}),
        "correct_answer": (payload.correct_answer or "").strip().upper() or None,
        "key_steps": _json(payload.key_steps),
        "common_errors": _json(payload.common_errors),
        "mistake_tags": _json(payload.mistake_tags),
        "published_at": datetime.now() if payload.publish_status == "published" else None,
    }


def _question_attachments(db: Any, question_id: int) -> dict[str, list[dict[str, Any]]]:
    rows = db.execute(
        text(
            """
            SELECT qa.attachment_type, uf.id, uf.original_name, uf.mime_type, uf.size_bytes
            FROM question_attachments qa
            JOIN uploaded_files uf ON uf.id=qa.uploaded_file_id
            WHERE qa.question_id=:question_id
            ORDER BY qa.attachment_type,qa.sort_order,qa.id
            """
        ),
        {"question_id": question_id},
    ).mappings().all()
    result: dict[str, list[dict[str, Any]]] = {"attachments": [], "analysis_attachments": []}
    for row in rows:
        key = "attachments" if row["attachment_type"] == "question" else "analysis_attachments"
        result[key].append(
            {
                "id": int(row["id"]),
                "name": str(row["original_name"]),
                "mime_type": str(row["mime_type"]),
                "size_bytes": int(row["size_bytes"]),
                "url": f"/api/files/{int(row['id'])}",
            }
        )
    return result


def _sync_question_attachments(
    db: Any,
    teacher_id: int,
    question_id: int,
    question_ids: list[int],
    analysis_ids: list[int],
) -> None:
    all_ids = [int(item) for item in question_ids + analysis_ids]
    if len(set(all_ids)) != len(all_ids):
        raise HTTPException(status_code=422, detail="同一张图片不能同时作为题干图和解析图。")
    if all_ids:
        placeholders = ",".join(f":file_{index}" for index in range(len(all_ids)))
        params = {f"file_{index}": file_id for index, file_id in enumerate(all_ids)}
        params.update({"teacher_id": teacher_id, "question_id": question_id})
        rows = db.execute(
            text(
                f"""
                SELECT uf.id
                FROM uploaded_files uf
                LEFT JOIN answer_attachments aa ON aa.uploaded_file_id=uf.id
                LEFT JOIN question_attachments qa ON qa.uploaded_file_id=uf.id
                WHERE uf.user_id=:teacher_id AND uf.id IN ({placeholders})
                  AND aa.id IS NULL AND (qa.id IS NULL OR qa.question_id=:question_id)
                """
            ),
            params,
        ).all()
        if {int(row[0]) for row in rows} != set(all_ids):
            raise HTTPException(status_code=409, detail="部分题目图片不存在、并非当前教师上传，或已经绑定其他内容。")
    db.execute(text("DELETE FROM question_attachments WHERE question_id=:question_id"), {"question_id": question_id})
    for attachment_type, ids in (("question", question_ids), ("analysis", analysis_ids)):
        for sort_order, file_id in enumerate(ids, start=1):
            db.execute(
                text(
                    """
                    INSERT INTO question_attachments (question_id,uploaded_file_id,attachment_type,sort_order)
                    VALUES (:question_id,:file_id,:attachment_type,:sort_order)
                    """
                ),
                {"question_id": question_id, "file_id": file_id, "attachment_type": attachment_type, "sort_order": sort_order},
            )


def _create_question_sync(teacher_id: int, payload: QuestionWriteRequest) -> dict[str, Any]:
    with SessionLocal() as db:
        source_id = _teacher_question_source_id(db)
        knowledge_node_id = db.execute(
            text("SELECT id FROM knowledge_nodes WHERE stage_name=:stage AND course_name=:course AND name IN (:knowledge_tag,:fine_tag) ORDER BY level DESC LIMIT 1"),
            {"stage": payload.stage, "course": payload.course, "knowledge_tag": payload.knowledge_tag, "fine_tag": payload.fine_tag},
        ).scalar()
        source_no = f"teacher-{teacher_id}-{uuid.uuid4().hex[:16]}"
        values = _question_values(payload) | {
            "source_id": source_id,
            "created_by": teacher_id,
            "source_question_no": source_no,
            "source_path": f"teacher/{teacher_id}/{source_no}",
            "knowledge_node_id": knowledge_node_id,
        }
        result = db.execute(
            text(
                """
                INSERT INTO questions (
                  source_id, created_by, visibility, publish_status, published_at,
                  source_question_no, source_path, question_type, stage, course,
                  knowledge_node_id, knowledge_tag, fine_tag, difficulty, question_text,
                  option_a, option_b, option_c, option_d, correct_answer, standard_answer,
                  analysis_text, key_steps, common_errors, mistake_tags
                ) VALUES (
                  :source_id, :created_by, :visibility, :publish_status, :published_at,
                  :source_question_no, :source_path, :question_type, :stage, :course,
                  :knowledge_node_id, :knowledge_tag, :fine_tag, :difficulty, :question_text,
                  :option_a, :option_b, :option_c, :option_d, :correct_answer, :standard_answer,
                  :analysis_text, :key_steps, :common_errors, :mistake_tags
                )
                """
            ),
            values,
        )
        question_id = int(result.lastrowid)
        _sync_question_attachments(db, teacher_id, question_id, payload.attachment_ids, payload.analysis_attachment_ids)
        _audit(db, teacher_id, "question.created", "question", question_id, {"status": payload.publish_status, "course": payload.course})
        db.commit()
        row = _get_owned_question(db, teacher_id, question_id)
        attachments = _question_attachments(db, question_id)
    return _question_dict(row) | attachments | {"editable": True}


def _update_question_sync(teacher_id: int, question_id: int, payload: QuestionWriteRequest) -> dict[str, Any]:
    with SessionLocal() as db:
        existing = _get_owned_question(db, teacher_id, question_id)
        if existing["publish_status"] == "archived":
            raise HTTPException(status_code=409, detail="已归档题目不能直接编辑，请先复制为新题。")
        values = _question_values(payload) | {"question_id": question_id, "teacher_id": teacher_id}
        db.execute(
            text(
                """
                UPDATE questions SET
                  visibility=:visibility, publish_status=:publish_status,
                  published_at=CASE WHEN :publish_status='published' THEN COALESCE(published_at,:published_at) ELSE NULL END,
                  version=version+1, question_type=:question_type, stage=:stage, course=:course,
                  knowledge_tag=:knowledge_tag, fine_tag=:fine_tag, difficulty=:difficulty,
                  question_text=:question_text, option_a=:option_a, option_b=:option_b,
                  option_c=:option_c, option_d=:option_d, correct_answer=:correct_answer,
                  standard_answer=:standard_answer, analysis_text=:analysis_text,
                  key_steps=:key_steps, common_errors=:common_errors, mistake_tags=:mistake_tags
                WHERE id=:question_id AND created_by=:teacher_id
                """
            ),
            values,
        )
        _sync_question_attachments(db, teacher_id, question_id, payload.attachment_ids, payload.analysis_attachment_ids)
        _audit(db, teacher_id, "question.updated", "question", question_id, {"status": payload.publish_status})
        db.commit()
        row = _get_owned_question(db, teacher_id, question_id)
        attachments = _question_attachments(db, question_id)
    return _question_dict(row) | attachments | {"editable": True}


def _change_question_status_sync(teacher_id: int, question_id: int, next_status: str) -> dict[str, Any]:
    with SessionLocal() as db:
        _get_owned_question(db, teacher_id, question_id)
        db.execute(
            text(
                """
                UPDATE questions
                SET publish_status=:status,
                    published_at=CASE WHEN :status='published' THEN COALESCE(published_at,NOW()) ELSE published_at END,
                    version=version+1
                WHERE id=:question_id AND created_by=:teacher_id
                """
            ),
            {"status": next_status, "question_id": question_id, "teacher_id": teacher_id},
        )
        _audit(db, teacher_id, f"question.{next_status}", "question", question_id, {})
        db.commit()
        row = _get_owned_question(db, teacher_id, question_id)
    return _question_dict(row) | {"editable": True}


def _copy_question_sync(teacher_id: int, question_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        source = db.execute(
            text(
                f"""
                SELECT {_question_columns()}
                FROM questions AS q
                JOIN source_attributions AS s ON s.id=q.source_id
                WHERE q.id=:question_id AND q.deleted_at IS NULL
                  AND (q.created_by=:teacher_id OR (q.publish_status='published' AND q.visibility='public'))
                LIMIT 1
                """
            ),
            {"question_id": question_id, "teacher_id": teacher_id},
        ).mappings().first()
    if not source:
        raise HTTPException(status_code=404, detail="题目不存在或无权复制。")

    payload = QuestionWriteRequest(
        question_type=str(source["question_type"]),
        stage=str(source["stage"]),
        course=str(source["course"]),
        knowledge_tag=str(source["knowledge_tag"]),
        fine_tag=str(source["fine_tag"]),
        difficulty=int(source["difficulty"]),
        question_text=f"{source['question_text']}（副本）",
        option_a=source["option_a"],
        option_b=source["option_b"],
        option_c=source["option_c"],
        option_d=source["option_d"],
        correct_answer=source["correct_answer"],
        standard_answer=str(source["standard_answer"]),
        analysis_text=str(source["analysis_text"]),
        key_steps=_parse_json_list(source["key_steps"]),
        common_errors=_parse_json_list(source["common_errors"]),
        mistake_tags=_parse_json_list(source["mistake_tags"]),
        visibility="class",
        publish_status="draft",
    )
    copied = _create_question_sync(teacher_id, payload)
    with SessionLocal() as db:
        _audit(
            db,
            teacher_id,
            "question.copied",
            "question",
            int(copied["id"]),
            {"source_question_id": question_id},
        )
        db.commit()
    return copied | {
        "copied_from": question_id,
        "copy_notice": "已复制为你的草稿题；原题附件未复制，请按需重新上传。",
    }


def _random_questions_sync(
    teacher_id: int,
    count: int,
    stage: str | None,
    course: str | None,
    question_type: str | None,
) -> dict[str, Any]:
    clauses = [
        "q.deleted_at IS NULL",
        "q.publish_status='published'",
        "(q.created_by=:teacher_id OR q.visibility='public')",
        "(q.created_by IS NOT NULL OR s.source_name <> 'WeBWorK Open Problem Library')",
    ]
    params: dict[str, Any] = {"teacher_id": teacher_id, "limit": count}
    for column, value in (("stage", stage), ("course", course), ("question_type", question_type)):
        if value:
            clauses.append(f"q.{column}=:{column}")
            params[column] = value
    with SessionLocal() as db:
        rows = db.execute(
            text(
                f"""
                SELECT {_question_columns()}
                FROM questions AS q
                JOIN source_attributions AS s ON s.id=q.source_id
                WHERE {' AND '.join(clauses)}
                ORDER BY RAND()
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
    return {
        "items": [_question_dict(row) | {"editable": row["created_by"] == teacher_id} for row in rows],
        "requested_count": count,
        "selected_count": len(rows),
        "filters": {"stage": stage, "course": course, "question_type": question_type},
    }


def _commit_question_import_sync(teacher_id: int, request: QuestionImportCommitRequest) -> dict[str, Any]:
    created: list[dict[str, Any]] = []
    available: list[dict[str, Any]] = []
    duplicate_count = 0
    reused_count = 0
    errors: list[dict[str, Any]] = []
    seen_in_request: set[str] = set()
    for index, raw in enumerate(request.questions, start=1):
        normalized = dict(raw)
        normalized["publish_status"] = request.publish_status
        normalized["visibility"] = request.visibility
        fingerprint = "".join(str(normalized.get("question_text") or "").split()).lower()
        try:
            points = float(raw.get("points") or 10)
            if not 1 <= points <= 100:
                raise ValueError("题目分值必须在 1 到 100 之间。")
            payload = QuestionWriteRequest.model_validate(normalized)
            if request.skip_duplicates and fingerprint in seen_in_request:
                duplicate_count += 1
                continue
            if request.skip_duplicates:
                with SessionLocal() as db:
                    duplicate = db.execute(
                        text(
                            f"""
                            SELECT {_question_columns()}
                            FROM questions AS q
                            JOIN source_attributions AS s ON s.id=q.source_id
                            WHERE q.created_by=:teacher_id AND q.deleted_at IS NULL
                              AND q.question_text=:question_text
                            LIMIT 1
                            """
                        ),
                        {"teacher_id": teacher_id, "question_text": payload.question_text},
                    ).mappings().first()
                if duplicate:
                    if request.reuse_duplicates and duplicate["publish_status"] != "archived":
                        if duplicate["publish_status"] != "published":
                            reused = _change_question_status_sync(
                                teacher_id,
                                int(duplicate["id"]),
                                "published",
                            )
                        else:
                            reused = _question_dict(duplicate)
                        reused |= {"editable": True, "points": points, "reused": True}
                        available.append(reused)
                        reused_count += 1
                        seen_in_request.add(fingerprint)
                        continue
                    if not request.reuse_duplicates:
                        duplicate_count += 1
                        continue
            item = _create_question_sync(teacher_id, payload)
            item["points"] = points
            created.append(item)
            available.append(item)
            seen_in_request.add(fingerprint)
        except Exception as exc:
            errors.append(
                {
                    "row": raw.get("source_row", index),
                    "message": str(getattr(exc, "detail", exc))[:500],
                }
            )
    with SessionLocal() as db:
        _audit(
            db,
            teacher_id,
            "question.imported",
            "question_import",
            None,
            {
                "source_file_name": request.source_file_name,
                "created_count": len(created),
                "duplicate_count": duplicate_count,
                "reused_count": reused_count,
                "error_count": len(errors),
            },
        )
        db.commit()
    return {
        "created_count": len(created),
        "question_ids": [int(item["id"]) for item in available],
        "questions": available,
        "duplicate_count": duplicate_count,
        "reused_count": reused_count,
        "error_count": len(errors),
        "errors": errors[:50],
        "source_file_name": request.source_file_name,
    }


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
        db.execute(
            text(
                """
                UPDATE assignments SET class_id=:class_id,title=:title,description=:description,
                  status=:status,starts_at=:starts_at,due_at=:due_at,time_limit_minutes=:time_limit,
                  max_attempts=:max_attempts,show_analysis_after_submit=:show_analysis,
                  total_score=:total_score,published_at=CASE WHEN :status='published' THEN NOW() ELSE NULL END
                WHERE id=:assignment_id AND teacher_id=:teacher_id
                """
            ),
            {"class_id": payload.class_id, "title": payload.title.strip(), "description": (payload.description or "").strip() or None, "status": next_status, "starts_at": payload.starts_at, "due_at": payload.due_at, "time_limit": payload.time_limit_minutes, "max_attempts": payload.max_attempts, "show_analysis": 1 if payload.show_analysis_after_submit else 0, "total_score": total_score, "assignment_id": assignment_id, "teacher_id": teacher_id},
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


@router.get("/students")
async def students(
    class_id: int | None = Query(default=None, ge=1),
    search: str | None = Query(default=None, max_length=64),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(_student_list_sync, int(current["id"]), class_id, search)


@router.get("/students/{student_id}")
async def student_detail(student_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_student_detail_sync, int(current["id"]), student_id)


@router.get("/students/{student_id}/preview")
async def student_preview(student_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    data = await asyncio.to_thread(_student_detail_sync, int(current["id"]), student_id)
    return data | {"read_only": True, "notice": "当前为教师只读预览，不会修改学生数据。"}


@router.get("/questions")
async def questions(
    scope: Literal["all", "mine", "public"] = "all",
    search: str | None = Query(default=None, max_length=160),
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
    question_type: str | None = Query(default=None, max_length=32),
    publish_status: str | None = Query(default=None, max_length=32),
    include_legacy: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=5, le=100),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _questions_sync,
        int(current["id"]),
        scope,
        search,
        stage,
        course,
        question_type,
        publish_status,
        include_legacy,
        page,
        page_size,
    )


@router.get("/questions/random")
async def random_questions(
    count: int = Query(default=10, ge=1, le=50),
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
    question_type: str | None = Query(default=None, max_length=32),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    if question_type and question_type not in QUESTION_TYPES:
        raise HTTPException(status_code=422, detail="题型参数不正确。")
    return await asyncio.to_thread(
        _random_questions_sync,
        int(current["id"]),
        count,
        stage,
        course,
        question_type,
    )


@router.get("/questions/{question_id}")
async def question_detail(question_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(text(f"SELECT {_question_columns()} FROM questions q JOIN source_attributions s ON s.id=q.source_id WHERE q.id=:id AND q.deleted_at IS NULL AND (q.created_by=:teacher OR (q.publish_status='published' AND q.visibility='public'))"), {"id": question_id, "teacher": current["id"]}).mappings().first()
        attachments = _question_attachments(db, question_id) if row else {}
    if not row:
        raise HTTPException(status_code=404, detail="题目不存在或无权查看。")
    return _question_dict(row) | attachments | {"editable": row["created_by"] == current["id"]}


@router.post("/questions", status_code=status.HTTP_201_CREATED)
async def create_question(payload: QuestionWriteRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_create_question_sync, int(current["id"]), payload)


@router.post("/questions/{question_id}/copy", status_code=status.HTTP_201_CREATED)
async def copy_question(question_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_copy_question_sync, int(current["id"]), question_id)


@router.put("/questions/{question_id}")
async def update_question(question_id: int, payload: QuestionWriteRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_update_question_sync, int(current["id"]), question_id, payload)


@router.post("/questions/{question_id}/publish")
async def publish_question(question_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_change_question_status_sync, int(current["id"]), question_id, "published")


@router.post("/questions/{question_id}/archive")
async def archive_question(question_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_change_question_status_sync, int(current["id"]), question_id, "archived")


async def _read_question_import(file: UploadFile) -> tuple[bytes, str]:
    filename = file.filename or "未命名文件"
    raw = await file.read(15 * 1024 * 1024 + 1)
    await file.close()
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="导入文件不能超过 15 MB。")
    if not raw:
        raise HTTPException(status_code=422, detail="上传文件为空。")
    return raw, filename


@router.get("/question-imports/template")
async def question_import_template(current: dict[str, Any] = Depends(require_teacher)) -> Response:
    del current
    rows = [
        {
            "题型": "选择题",
            "阶段": "大一",
            "课程": "高等数学（上）",
            "知识点": "函数极限",
            "细分标签": "极限运算",
            "难度": 2,
            "题干": "当 x 趋于 0 时，sin(x)/x 的极限是（ ）。",
            "选项A": "0",
            "选项B": "1",
            "选项C": "不存在",
            "选项D": "无穷大",
            "正确答案": "B",
            "标准答案": "B",
            "解析": "利用重要极限 lim(x→0) sin(x)/x = 1。",
            "关键步骤": "识别重要极限|直接代入结论",
            "常见错误": "误认为可直接代入得到 0/0",
            "错因标签": "重要极限",
            "分值": 5,
        },
        {
            "题型": "计算题",
            "阶段": "大一",
            "课程": "高等数学（上）",
            "知识点": "导数",
            "细分标签": "复合函数求导",
            "难度": 3,
            "题干": "求函数 y=sin(x²) 的导数。",
            "选项A": "",
            "选项B": "",
            "选项C": "",
            "选项D": "",
            "正确答案": "",
            "标准答案": "y'=2x cos(x²)",
            "解析": "令 u=x²，使用复合函数链式法则。",
            "关键步骤": "令 u=x²|外层求导|乘以内层导数",
            "常见错误": "遗漏内层导数 2x",
            "错因标签": "链式法则",
            "分值": 10,
        },
    ]
    buffer = io.BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index=False, engine="openpyxl")
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="math-question-import-template.xlsx"'},
    )


@router.post("/question-imports/preview")
async def preview_question_import(
    file: UploadFile = File(...),
    default_stage: str = Form(default=""),
    default_course: str = Form(default=""),
    default_knowledge_tag: str = Form(default=""),
    default_fine_tag: str = Form(default=""),
    default_difficulty: int = Form(default=3),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    raw, filename = await _read_question_import(file)
    defaults = {
        "stage": default_stage,
        "course": default_course,
        "knowledge_tag": default_knowledge_tag,
        "fine_tag": default_fine_tag,
        "difficulty": max(1, min(5, default_difficulty)),
    }
    try:
        result = await asyncio.to_thread(parse_question_document, raw, filename, defaults)
    except QuestionDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    with SessionLocal() as db:
        _audit(
            db,
            int(current["id"]),
            "question.import_previewed",
            "question_import",
            None,
            {"file_name": filename, "total_detected": result["total_detected"], "valid_count": result["valid_count"]},
        )
        db.commit()
    return result


@router.post("/question-imports/commit", status_code=status.HTTP_201_CREATED)
async def commit_question_import(
    payload: QuestionImportCommitRequest,
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(_commit_question_import_sync, int(current["id"]), payload)


@router.post("/question-imports", status_code=status.HTTP_201_CREATED)
async def import_questions(file: UploadFile = File(...), current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    """Compatibility endpoint for older clients; new clients preview before committing."""
    raw, filename = await _read_question_import(file)
    try:
        preview = await asyncio.to_thread(parse_question_document, raw, filename, {})
    except QuestionDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    valid = [item for item in preview["questions"] if item["valid"]]
    if not valid:
        raise HTTPException(status_code=422, detail="文件中没有通过校验的题目，请使用预览导入检查错误。")
    request = QuestionImportCommitRequest(questions=valid, source_file_name=filename)
    return await asyncio.to_thread(_commit_question_import_sync, int(current["id"]), request)


@router.get("/assignments")
async def assignments(
    class_id: int | None = Query(default=None, ge=1),
    assignment_status: str | None = Query(default=None, alias="status", max_length=32),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(_assignments_sync, int(current["id"]), class_id, assignment_status)


@router.post("/assignments", status_code=status.HTTP_201_CREATED)
async def create_assignment(payload: AssignmentWriteRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_create_assignment_sync, int(current["id"]), payload)


@router.get("/assignments/{assignment_id}")
async def assignment_detail(assignment_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_assignment_detail_sync, int(current["id"]), assignment_id)


@router.put("/assignments/{assignment_id}")
async def update_assignment(assignment_id: int, payload: AssignmentWriteRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_update_assignment_sync, int(current["id"]), assignment_id, payload)


@router.post("/assignments/{assignment_id}/publish")
async def publish_assignment(assignment_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_publish_assignment_sync, int(current["id"]), assignment_id)


@router.post("/assignments/{assignment_id}/close")
async def close_assignment(assignment_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_close_assignment_sync, int(current["id"]), assignment_id)


@router.post("/assignments/{assignment_id}/archive")
async def archive_assignment(assignment_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, bool]:
    return await asyncio.to_thread(_archive_assignment_sync, int(current["id"]), assignment_id)


@router.get("/review-queue")
async def review_queue(
    assignment_id: int | None = Query(default=None, ge=1),
    review_status: Literal["pending", "graded"] = "pending",
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(_review_queue_sync, int(current["id"]), assignment_id, review_status)


@router.post("/submissions/{record_id}/grade")
async def grade_submission(record_id: int, payload: ReviewRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_grade_sync, int(current["id"]), record_id, payload)
