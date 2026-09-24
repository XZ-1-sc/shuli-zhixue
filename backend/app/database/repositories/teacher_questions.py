import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text

from ..session import SessionLocal
from ...api.teacher_schemas import TYPE_LABELS, QuestionImportCommitRequest, QuestionWriteRequest
from ...api.utils import _parse_json_list, _parse_solution_steps
from ...api.routes.teacher import _audit
from .teacher_common import _iso, _json


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
    item["solution_steps"] = _parse_solution_steps(item.get("solution_steps"))
    for key in ("created_at", "updated_at", "published_at"):
        item[key] = _iso(item.get(key))
    item["editable"] = bool(item.get("created_by"))
    item.setdefault("attachments", [])
    item.setdefault("analysis_attachments", [])
    return item

def _question_columns() -> str:
    return """
      q.id, q.source_id, q.created_by, q.visibility, q.publish_status, q.version,
      q.ai_generated, q.source_question_id,
      q.published_at, q.source_question_no, q.source_path, q.question_type,
      q.stage, q.course, q.knowledge_node_id, q.knowledge_tag, q.fine_tag,
      q.difficulty, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d,
      q.correct_answer, q.standard_answer, q.analysis_text, q.key_steps,
      q.common_errors, q.mistake_tags, q.solution_steps, q.steps_source,
      q.steps_review_status, q.created_at, q.updated_at,
      (SELECT COUNT(*) FROM question_attachments qa WHERE qa.question_id=q.id AND qa.attachment_type='question') AS attachment_count,
      (SELECT COUNT(*) FROM question_attachments qa WHERE qa.question_id=q.id AND qa.attachment_type='analysis') AS analysis_attachment_count,
      s.source_name
    """

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
                       ,SUM(q.created_by = :teacher_id AND q.ai_generated = 1 AND q.publish_status = 'draft') AS ai_drafts
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
        "summary": {key: int(summary[key] or 0) for key in ("total", "mine", "drafts", "published", "ai_drafts")},
    }


def _question_detail_sync(teacher_id: int, question_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            text(
                f"SELECT {_question_columns()} FROM questions q "
                "JOIN source_attributions s ON s.id=q.source_id "
                "WHERE q.id=:id AND q.deleted_at IS NULL "
                "AND (q.created_by=:teacher OR (q.publish_status='published' AND q.visibility='public'))"
            ),
            {"id": question_id, "teacher": teacher_id},
        ).mappings().first()
        attachments = _question_attachments(db, question_id) if row else {}
    if not row:
        raise HTTPException(status_code=404, detail="题目不存在或无权查看。")
    return _question_dict(row) | attachments | {"editable": row["created_by"] == teacher_id}


def _audit_question_import_preview_sync(
    teacher_id: int,
    file_name: str,
    total_detected: int,
    valid_count: int,
) -> None:
    with SessionLocal() as db:
        _audit(
            db,
            teacher_id,
            "question.import_previewed",
            "question_import",
            None,
            {"file_name": file_name, "total_detected": total_detected, "valid_count": valid_count},
        )
        db.commit()

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

def _create_question_sync(
    teacher_id: int, payload: QuestionWriteRequest, *, ai_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if ai_source is not None and (payload.publish_status != "draft" or payload.visibility != "class"):
        raise HTTPException(status_code=422, detail="AI 出题只能保存为私有草稿。")
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
            "source_path": f"{'teacher-ai' if ai_source is not None else 'teacher'}/{teacher_id}/{source_no}",
            "knowledge_node_id": knowledge_node_id,
            "ai_generated": 1 if ai_source is not None else 0,
            "source_question_id": (ai_source or {}).get("source_question_id"),
        }
        result = db.execute(
            text(
                """
                INSERT INTO questions (
                  source_id, created_by, visibility, publish_status, published_at, ai_generated, source_question_id,
                  source_question_no, source_path, question_type, stage, course,
                  knowledge_node_id, knowledge_tag, fine_tag, difficulty, question_text,
                  option_a, option_b, option_c, option_d, correct_answer, standard_answer,
                  analysis_text, key_steps, common_errors, mistake_tags
                ) VALUES (
                  :source_id, :created_by, :visibility, :publish_status, :published_at, :ai_generated, :source_question_id,
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
        if ai_source is not None:
            _audit(db, teacher_id, "question.ai_generated", "question", question_id, ai_source)
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
