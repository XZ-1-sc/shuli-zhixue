import json
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..api.routes.teacher import _owned_class
from ..api.schemas import MessageSendRequest
from ..database.repositories.teacher_students import _student_detail_sync
from ..database.session import SessionLocal
from ..utils.llm_client import call_llm_json
from .message_service import _ensure_conversation, _insert_message


class AdviceContent(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def generate_advice_drafts_sync(teacher_id: int, class_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        class_row = _owned_class(db, teacher_id, class_id)
        members = db.execute(
            text(
                """
                SELECT u.id,u.username,COALESCE(u.nickname,u.username) AS nickname
                FROM class_members cm JOIN users u ON u.id=cm.student_id
                WHERE cm.class_id=:class_id AND cm.status='active'
                ORDER BY u.username
                """
            ),
            {"class_id": class_id},
        ).mappings().all()
        existing_ids = {
            int(value)
            for value in db.execute(
                text("SELECT student_id FROM advice_drafts WHERE class_id=:class_id AND status='draft'"),
                {"class_id": class_id},
            ).scalars().all()
        }

    generated: list[int] = []
    skipped: list[int] = []
    for member in members:
        student_id = int(member["id"])
        if student_id in existing_ids:
            skipped.append(student_id)
            continue
        detail = _student_detail_sync(teacher_id, student_id)
        profile = detail["profile"]
        weak = detail["weak_points"][:3]
        assignments = detail["assignments"][:3]
        weak_text = "、".join(str(item["fine_tag"]) for item in weak) or "基础知识"
        fallback = AdviceContent(
            content=(
                f"{profile['nickname']}同学：结合你近期 {profile['practice_count']} 次作答和 {profile['accuracy']:g}% 的正确率，"
                f"建议本周优先巩固{weak_text}。每天安排 20—30 分钟完成基础题与一道变式题，"
                "订正时写清错误原因，并在一周后用同知识点练习复测。"
            )
        )
        advice, _ = call_llm_json(
            [
                {
                    "role": "system",
                    "content": "你是教师的学习建议起草助手。请面向学生写一段具体、温和、可执行的调整建议，不虚构数据，不宣称已发送。",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "class": {"name": class_row["name"], "course": class_row["course"]},
                            "profile": profile,
                            "weak_points": weak,
                            "recent_assignments": assignments,
                        },
                        ensure_ascii=False,
                        default=str,
                    )[:16000],
                },
            ],
            AdviceContent,
            fallback=fallback,
            agent_name="teacher_student_advice",
            temperature=0.25,
        )
        with SessionLocal() as db:
            duplicate = db.execute(
                text(
                    "SELECT id FROM advice_drafts WHERE class_id=:class_id AND student_id=:student_id AND status='draft' LIMIT 1"
                ),
                {"class_id": class_id, "student_id": student_id},
            ).scalar()
            if duplicate:
                skipped.append(student_id)
                continue
            result = db.execute(
                text(
                    """
                    INSERT INTO advice_drafts (teacher_id,class_id,student_id,content)
                    VALUES (:teacher_id,:class_id,:student_id,:content)
                    """
                ),
                {"teacher_id": teacher_id, "class_id": class_id, "student_id": student_id, "content": advice.content},
            )
            db.commit()
            generated.append(int(result.lastrowid))
    return {"class_id": class_id, "generated_count": len(generated), "skipped_count": len(skipped), "draft_ids": generated}


def advice_drafts_sync(teacher_id: int, class_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        _owned_class(db, teacher_id, class_id)
        rows = db.execute(
            text(
                """
                SELECT d.id,d.class_id,d.student_id,d.content,d.status,d.created_at,d.updated_at,d.sent_at,
                       u.username,COALESCE(u.nickname,u.username) AS nickname,
                       latest.title AS latest_assignment,
                       latest.total_score,latest.max_score,latest.submitted_at
                FROM advice_drafts d
                JOIN users u ON u.id=d.student_id
                LEFT JOIN (
                  SELECT ranked.user_id,ranked.title,ranked.total_score,ranked.max_score,ranked.submitted_at
                  FROM (
                    SELECT aa.user_id,a.title,aa.total_score,aa.max_score,aa.submitted_at,
                           ROW_NUMBER() OVER(PARTITION BY aa.user_id ORDER BY aa.submitted_at DESC,aa.id DESC) AS row_no
                    FROM assignment_attempts aa JOIN assignments a ON a.id=aa.assignment_id
                    WHERE a.class_id=:class_id AND aa.submitted_at IS NOT NULL
                  ) ranked WHERE ranked.row_no=1
                ) latest ON latest.user_id=d.student_id
                WHERE d.teacher_id=:teacher_id AND d.class_id=:class_id AND d.status='draft'
                ORDER BY d.updated_at DESC,d.id DESC
                """
            ),
            {"teacher_id": teacher_id, "class_id": class_id},
        ).mappings().all()
    items = []
    for row in rows:
        score = float(row["total_score"] or 0) if row["total_score"] is not None else None
        max_score = float(row["max_score"] or 0) if row["max_score"] is not None else None
        items.append(
            {
                "id": int(row["id"]),
                "class_id": int(row["class_id"]),
                "student_id": int(row["student_id"]),
                "username": str(row["username"]),
                "nickname": str(row["nickname"]),
                "content": str(row["content"]),
                "status": str(row["status"]),
                "latest_assignment": str(row["latest_assignment"] or ""),
                "latest_score": score,
                "latest_max_score": max_score,
                "created_at": _iso(row["created_at"]),
                "updated_at": _iso(row["updated_at"]),
                "sent_at": _iso(row["sent_at"]),
            }
        )
    return {"items": items, "total": len(items)}


def update_advice_draft_sync(teacher_id: int, draft_id: int, content: str) -> dict[str, Any]:
    normalized = content.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="建议内容不能为空。")
    with SessionLocal() as db:
        result = db.execute(
            text(
                """
                UPDATE advice_drafts d JOIN classes c ON c.id=d.class_id
                SET d.content=:content
                WHERE d.id=:draft_id AND d.teacher_id=:teacher_id AND c.teacher_id=:teacher_id AND d.status='draft'
                """
            ),
            {"content": normalized, "draft_id": draft_id, "teacher_id": teacher_id},
        )
        db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="建议草稿不存在、已发送或不属于当前教师。")
    return {"id": draft_id, "content": normalized, "status": "draft"}


def _send_draft(db: Any, teacher_id: int, draft_id: int) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT d.*,c.name AS class_name
            FROM advice_drafts d JOIN classes c ON c.id=d.class_id
            WHERE d.id=:draft_id AND d.teacher_id=:teacher_id AND c.teacher_id=:teacher_id AND d.status='draft'
            LIMIT 1 FOR UPDATE
            """
        ),
        {"draft_id": draft_id, "teacher_id": teacher_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"建议草稿 {draft_id} 不存在、已发送或无权访问。")
    conversation_id = _ensure_conversation(db, teacher_id, int(row["student_id"]), "teacher_student")
    conversation = db.execute(
        text("SELECT * FROM conversations WHERE id=:conversation_id"),
        {"conversation_id": conversation_id},
    ).mappings().one()
    message_id = _insert_message(
        db,
        dict(conversation),
        teacher_id,
        MessageSendRequest(content=str(row["content"]), message_type="advice"),
    )
    db.execute(text("UPDATE advice_drafts SET status='sent',sent_at=NOW() WHERE id=:id"), {"id": draft_id})
    return {
        "draft_id": draft_id,
        "message_id": message_id,
        "conversation_id": conversation_id,
        "student_id": int(row["student_id"]),
    }


def send_advice_draft_sync(teacher_id: int, draft_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        result = _send_draft(db, teacher_id, draft_id)
        db.commit()
    return result


def batch_send_advice_drafts_sync(teacher_id: int, draft_ids: list[int]) -> dict[str, Any]:
    unique_ids = list(dict.fromkeys(draft_ids))
    with SessionLocal() as db:
        items = [_send_draft(db, teacher_id, draft_id) for draft_id in unique_ids]
        db.commit()
    return {"items": items, "sent_count": len(items)}
