import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text

from ..api.routes.teacher import _owned_class
from ..api.teacher_schemas import TeacherExperienceRequest, TeacherPreferenceRequest
from ..database.session import SessionLocal


def _experience_dict(row: Any) -> dict[str, Any]:
    return {
        **dict(row),
        "id": int(row["id"]),
        "teacher_id": int(row["teacher_id"]),
        "class_id": int(row["class_id"]) if row["class_id"] else None,
        "question_id": int(row["question_id"]) if row["question_id"] else None,
        "usage_count": int(row["usage_count"] or 0),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def experiences_sync(teacher_id: int, knowledge_tag: str | None = None, question_id: int | None = None) -> dict[str, Any]:
    clauses = ["te.teacher_id=:teacher_id", "te.status='active'"]
    params: dict[str, Any] = {"teacher_id": teacher_id}
    if knowledge_tag:
        clauses.append("te.knowledge_tag=:knowledge_tag")
        params["knowledge_tag"] = knowledge_tag
    if question_id:
        clauses.append("te.question_id=:question_id")
        params["question_id"] = question_id
    with SessionLocal() as db:
        rows = db.execute(text(f"SELECT te.* FROM teacher_experiences te WHERE {' AND '.join(clauses)} ORDER BY te.updated_at DESC,te.id DESC LIMIT 100"), params).mappings().all()
    return {"items": [_experience_dict(row) for row in rows], "total": len(rows)}


def create_experience_sync(teacher_id: int, payload: TeacherExperienceRequest) -> dict[str, Any]:
    with SessionLocal() as db:
        if payload.class_id:
            _owned_class(db, teacher_id, payload.class_id)
        if payload.question_id:
            allowed = db.execute(
                text("SELECT 1 FROM questions WHERE id=:id AND deleted_at IS NULL AND (created_by=:teacher OR (publish_status='published' AND visibility='public'))"),
                {"id": payload.question_id, "teacher": teacher_id},
            ).first()
            if not allowed:
                raise HTTPException(status_code=404, detail="题目不存在或无权关联。")
        result = db.execute(
            text(
                """
                INSERT INTO teacher_experiences
                  (teacher_id,class_id,question_id,knowledge_tag,experience_text)
                VALUES (:teacher_id,:class_id,:question_id,:knowledge_tag,:experience_text)
                """
            ),
            {"teacher_id": teacher_id, **payload.model_dump()},
        )
        db.commit()
        row = db.execute(text("SELECT * FROM teacher_experiences WHERE id=:id"), {"id": int(result.lastrowid)}).mappings().one()
    return _experience_dict(row)


def archive_experience_sync(teacher_id: int, experience_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        result = db.execute(text("UPDATE teacher_experiences SET status='archived' WHERE id=:id AND teacher_id=:teacher_id AND status='active'"), {"id": experience_id, "teacher_id": teacher_id})
        if not result.rowcount:
            raise HTTPException(status_code=404, detail="教学经验不存在。")
        db.commit()
    return {"id": experience_id, "archived": True}


def preference_sync(teacher_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(text("SELECT * FROM teacher_ai_preferences WHERE teacher_id=:teacher_id"), {"teacher_id": teacher_id}).mappings().first()
    if not row:
        return {"tone": "清晰、鼓励、重方法", "scoring_strictness": "balanced", "preferred_types": [], "style_notes": "", "assistant_enabled": True, "ai_disclosure_required": True}
    item = dict(row)
    preferred = item.get("preferred_types")
    if isinstance(preferred, str):
        try:
            preferred = json.loads(preferred)
        except json.JSONDecodeError:
            preferred = []
    return {"tone": item["tone"], "scoring_strictness": item["scoring_strictness"], "preferred_types": preferred or [], "style_notes": item["style_notes"] or "", "assistant_enabled": bool(item["assistant_enabled"]), "ai_disclosure_required": True}


def save_preference_sync(teacher_id: int, payload: TeacherPreferenceRequest) -> dict[str, Any]:
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO teacher_ai_preferences
                  (teacher_id,tone,scoring_strictness,preferred_types,style_notes,assistant_enabled)
                VALUES (:teacher_id,:tone,:strictness,:types,:notes,:enabled)
                ON DUPLICATE KEY UPDATE tone=VALUES(tone),scoring_strictness=VALUES(scoring_strictness),
                  preferred_types=VALUES(preferred_types),style_notes=VALUES(style_notes),assistant_enabled=VALUES(assistant_enabled)
                """
            ),
            {"teacher_id": teacher_id, "tone": payload.tone, "strictness": payload.scoring_strictness, "types": json.dumps(payload.preferred_types, ensure_ascii=False), "notes": payload.style_notes, "enabled": 1 if payload.assistant_enabled else 0},
        )
        db.commit()
    return preference_sync(teacher_id)


def teacher_memory_context_sync(teacher_id: int, *, knowledge_tag: str | None = None, question_id: int | None = None) -> dict[str, Any]:
    experience_data = experiences_sync(teacher_id, knowledge_tag, question_id)
    with SessionLocal() as db:
        adjustment_rows = db.execute(
            text(
                """
                SELECT teacher_adjustments_json
                FROM assignments
                WHERE teacher_id=:teacher_id AND ai_generated=1 AND teacher_adjustments_json IS NOT NULL
                ORDER BY updated_at DESC LIMIT 12
                """
            ),
            {"teacher_id": teacher_id},
        ).scalars().all()
    adjustments = []
    for raw in adjustment_rows:
        if isinstance(raw, dict):
            adjustments.append(raw)
            continue
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            adjustments.append(parsed)
    return {
        "preference": preference_sync(teacher_id),
        "experiences": [item["experience_text"] for item in experience_data["items"][:12]],
        "recent_paper_adjustments": adjustments,
        "disclosure": "输出由 AI 按教师已保存的偏好辅助生成，发送前应由教师确认。",
    }
