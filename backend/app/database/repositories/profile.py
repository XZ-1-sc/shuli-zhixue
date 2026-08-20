from typing import Any

from fastapi import HTTPException
from sqlalchemy import text

from ..session import SessionLocal
from ...api.schemas import NoteRequest, NoteUpdateRequest
from ...api.utils import _json_safe
from .common import _get_user_exists


def _messages_sync(user_id: int) -> dict[str, Any]:
    query = text(
        """
        SELECT id, type, title, content, is_read, created_at
        FROM user_notifications
        WHERE user_id = :user_id OR user_id IS NULL
        ORDER BY is_read ASC, created_at DESC, id DESC
        LIMIT 80
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query, {"user_id": user_id}).mappings().all()
    items = [
        {
            "id": int(row["id"]),
            "type": str(row["type"]),
            "title": str(row["title"]),
            "content": str(row["content"]),
            "is_read": bool(row["is_read"]),
            "created_at": _json_safe(row["created_at"]),
        }
        for row in rows
    ]
    return {"user_id": user_id, "unread_count": sum(1 for item in items if not item["is_read"]), "items": items}

def _profile_summary_sync(user_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        user_row = db.execute(
            text(
                """
                SELECT id, username, nickname, current_stage, created_at, last_login_at
                FROM users
                WHERE id = :user_id
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
    if not user_row:
        raise HTTPException(status_code=404, detail="用户不存在，请先登录。")

    records = _recent_records_sync(user_id, 200)
    answered = [record for record in records if record.get("is_correct") is not None]
    correct_count = sum(1 for record in answered if bool(record.get("is_correct")))
    accuracy = round(correct_count / len(answered) * 100, 1) if answered else 0.0
    total_seconds = sum(int(record.get("time_spent_seconds") or 0) for record in records)
    diagnosis = _diagnose_sync(user_id)
    goal = _get_goal_sync(user_id)
    recent_records = [
        {
            "question_id": int(record["question_id"]),
            "course": record["course"],
            "knowledge_tag": record["knowledge_tag"],
            "question_type": record["question_type"],
            "score": float(record.get("score") or 0),
            "is_correct": bool(record.get("is_correct")),
            "answered_at": record.get("answered_at"),
        }
        for record in records[:8]
    ]
    return {
        "user": {
            "id": int(user_row["id"]),
            "username": str(user_row["username"]),
            "nickname": user_row["nickname"] or user_row["username"],
            "current_stage": user_row["current_stage"] or goal["target_stage"],
            "created_at": _json_safe(user_row["created_at"]),
            "last_login_at": _json_safe(user_row["last_login_at"]),
        },
        "goal": goal,
        "stats": {
            "practice_count": len(records),
            "answered_count": len(answered),
            "correct_count": correct_count,
            "accuracy": accuracy,
            "study_hours": round(total_seconds / 3600, 1),
        },
        "weak_points": diagnosis.get("weak_points", [])[:5],
        "recent_records": recent_records,
    }

def _achievements_sync(user_id: int) -> dict[str, Any]:
    records = _recent_records_sync(user_id, 300)
    answered = [record for record in records if record.get("is_correct") is not None]
    correct_count = sum(1 for record in answered if bool(record.get("is_correct")))
    accuracy = round(correct_count / len(answered) * 100, 1) if answered else 0.0
    wrong_book_count = sum(1 for record in records if record.get("practice_mode") == "wrong_book")
    proof_count = sum(1 for record in records if record.get("question_type") == "proof")
    mock_count = sum(1 for record in records if record.get("practice_mode") == "mock")
    badges = [
        {"code": "first_step", "title": "启程", "description": "完成首道练习题。", "unlocked": len(records) >= 1, "progress": min(len(records), 1), "target": 1},
        {"code": "steady_learner", "title": "稳定推进", "description": "累计完成 3 道练习题。", "unlocked": len(records) >= 3, "progress": min(len(records), 3), "target": 3},
        {"code": "question_builder", "title": "题感建立", "description": "累计完成 20 道练习题。", "unlocked": len(records) >= 20, "progress": min(len(records), 20), "target": 20},
        {"code": "accurate_solver", "title": "准确解题", "description": "至少 10 题且正确率达到 80%。", "unlocked": len(answered) >= 10 and accuracy >= 80, "progress": int(accuracy), "target": 80},
        {"code": "wrong_book", "title": "错题回炉", "description": "完成一次错题本回炉练习。", "unlocked": wrong_book_count > 0, "progress": min(wrong_book_count, 1), "target": 1},
        {"code": "proof_beginner", "title": "证明入门", "description": "完成至少 1 道证明题。", "unlocked": proof_count > 0, "progress": min(proof_count, 1), "target": 1},
        {"code": "mock_exam", "title": "模拟演练", "description": "完成至少 1 次模拟考试题目。", "unlocked": mock_count > 0, "progress": min(mock_count, 1), "target": 1},
    ]
    return {
        "user_id": user_id,
        "stats": {"practice_count": len(records), "accuracy": accuracy, "correct_count": correct_count},
        "badges": badges,
    }

def _resources_sync(stage: str | None, course: str | None) -> dict[str, Any]:
    filters = []
    params: dict[str, Any] = {"limit": 80}
    if stage:
        filters.append("stage = :stage")
        params["stage"] = stage
    if course:
        filters.append("course = :course")
        params["course"] = course
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""
    query = text(
        f"""
        SELECT id, stage, course, title, resource_type, description, url, difficulty, created_at
        FROM learning_resources
        {where_clause}
        ORDER BY FIELD(stage, '大一', '大二', '大三', '大四'), course, difficulty, id
        LIMIT :limit
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query, params).mappings().all()
    return {
        "stage": stage,
        "course": course,
        "items": [
            {
                "id": int(row["id"]),
                "stage": row["stage"],
                "course": row["course"],
                "title": row["title"],
                "resource_type": row["resource_type"],
                "description": row["description"],
                "url": row["url"],
                "difficulty": int(row["difficulty"] or 1),
                "created_at": _json_safe(row["created_at"]),
            }
            for row in rows
        ],
    }

def _notes_sync(user_id: int) -> dict[str, Any]:
    query = text(
        """
        SELECT id, title, content, course, knowledge_tag, created_at, updated_at
        FROM user_notes
        WHERE user_id = :user_id
        ORDER BY updated_at DESC, id DESC
        LIMIT 100
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query, {"user_id": user_id}).mappings().all()
        note_ids = [int(row["id"]) for row in rows]
        attachment_rows = []
        if note_ids:
            placeholders = ", ".join(f":note_{index}" for index in range(len(note_ids)))
            params = {f"note_{index}": note_id for index, note_id in enumerate(note_ids)}
            attachment_rows = db.execute(
                text(
                    f"""
                    SELECT na.note_id, uf.id, uf.original_name, uf.mime_type, uf.size_bytes,
                           uf.width, uf.height, na.sort_order
                    FROM note_attachments AS na
                    JOIN uploaded_files AS uf ON uf.id = na.uploaded_file_id
                    WHERE na.note_id IN ({placeholders})
                    ORDER BY na.note_id, na.sort_order, na.id
                    """
                ),
                params,
            ).mappings().all()
    attachments_by_note: dict[int, list[dict[str, Any]]] = {note_id: [] for note_id in note_ids}
    for attachment in attachment_rows:
        file_id = int(attachment["id"])
        mime_type = str(attachment["mime_type"])
        attachments_by_note[int(attachment["note_id"])].append(
            {
                "id": file_id,
                "name": str(attachment["original_name"]),
                "mime_type": mime_type,
                "size_bytes": int(attachment["size_bytes"] or 0),
                "width": int(attachment["width"] or 0),
                "height": int(attachment["height"] or 0),
                "is_image": mime_type.startswith("image/"),
                "url": f"/api/files/{file_id}",
            }
        )
    return {
        "user_id": user_id,
        "items": [
            {
                "id": int(row["id"]),
                "title": row["title"],
                "content": row["content"],
                "course": row["course"],
                "knowledge_tag": row["knowledge_tag"],
                "attachments": attachments_by_note.get(int(row["id"]), []),
                "created_at": _json_safe(row["created_at"]),
                "updated_at": _json_safe(row["updated_at"]),
            }
            for row in rows
        ],
    }

def _validate_note_attachment_ids(
    db: Any,
    user_id: int,
    attachment_ids: list[int],
    note_id: int | None = None,
) -> list[int]:
    unique_ids = list(dict.fromkeys(int(file_id) for file_id in attachment_ids))
    if len(unique_ids) != len(attachment_ids) or len(unique_ids) > 10:
        raise HTTPException(status_code=422, detail="笔记附件不能重复，且最多保留 10 个。")
    if not unique_ids:
        return []
    placeholders = ", ".join(f":file_{index}" for index in range(len(unique_ids)))
    params: dict[str, Any] = {f"file_{index}": file_id for index, file_id in enumerate(unique_ids)}
    params.update({"user_id": user_id, "note_id": note_id or 0})
    rows = db.execute(
        text(
            f"""
            SELECT uf.id
            FROM uploaded_files AS uf
            LEFT JOIN answer_attachments AS aa ON aa.uploaded_file_id = uf.id
            LEFT JOIN question_attachments AS qa ON qa.uploaded_file_id = uf.id
            LEFT JOIN note_attachments AS na ON na.uploaded_file_id = uf.id
            WHERE uf.id IN ({placeholders}) AND uf.user_id = :user_id
              AND aa.id IS NULL AND qa.id IS NULL
              AND (na.id IS NULL OR na.note_id = :note_id)
            """
        ),
        params,
    ).scalars().all()
    if {int(file_id) for file_id in rows} != set(unique_ids):
        raise HTTPException(status_code=422, detail="部分附件不存在、已被使用，或不属于当前账号。")
    return unique_ids

def _sync_note_attachments(
    db: Any,
    note_id: int,
    user_id: int,
    attachment_ids: list[int],
) -> list[str]:
    requested = _validate_note_attachment_ids(db, user_id, attachment_ids, note_id)
    existing_rows = db.execute(
        text(
            """
            SELECT na.uploaded_file_id, uf.storage_key
            FROM note_attachments AS na
            JOIN uploaded_files AS uf ON uf.id = na.uploaded_file_id
            WHERE na.note_id = :note_id
            """
        ),
        {"note_id": note_id},
    ).mappings().all()
    existing = {int(row["uploaded_file_id"]): str(row["storage_key"]) for row in existing_rows}
    removed_ids = set(existing) - set(requested)
    removed_keys = [existing[file_id] for file_id in removed_ids]

    for file_id in removed_ids:
        db.execute(
            text("DELETE FROM note_attachments WHERE note_id = :note_id AND uploaded_file_id = :file_id"),
            {"note_id": note_id, "file_id": file_id},
        )
        db.execute(text("DELETE FROM uploaded_files WHERE id = :file_id"), {"file_id": file_id})
    for sort_order, file_id in enumerate(requested, start=1):
        if file_id in existing:
            db.execute(
                text(
                    """
                    UPDATE note_attachments SET sort_order = :sort_order
                    WHERE note_id = :note_id AND uploaded_file_id = :file_id
                    """
                ),
                {"note_id": note_id, "file_id": file_id, "sort_order": sort_order},
            )
        else:
            db.execute(
                text(
                    """
                    INSERT INTO note_attachments (note_id, uploaded_file_id, sort_order)
                    VALUES (:note_id, :file_id, :sort_order)
                    """
                ),
                {"note_id": note_id, "file_id": file_id, "sort_order": sort_order},
            )
    return removed_keys

def _remove_note_files(storage_keys: list[str]) -> None:
    if not storage_keys:
        return
    from .uploads import _upload_root

    root = _upload_root()
    for storage_key in storage_keys:
        path = (root / storage_key).resolve()
        if root in path.parents:
            path.unlink(missing_ok=True)

def _create_note_sync(user_id: int, payload: NoteRequest) -> dict[str, Any]:
    if not payload.content.strip() and not payload.attachment_ids:
        raise HTTPException(status_code=422, detail="请填写笔记内容或至少上传一个附件。")
    storage_keys: list[str] = []
    with SessionLocal() as db:
        if not _get_user_exists(db, user_id):
            raise HTTPException(status_code=404, detail="用户不存在，请先登录。")
        result = db.execute(
            text(
                """
                INSERT INTO user_notes (user_id, title, content, course, knowledge_tag)
                VALUES (:user_id, :title, :content, :course, :knowledge_tag)
                """
            ),
            {"user_id": user_id, **payload.model_dump(exclude={"attachment_ids"})},
        )
        note_id = int(result.lastrowid)
        storage_keys = _sync_note_attachments(db, note_id, user_id, payload.attachment_ids)
        db.commit()
    _remove_note_files(storage_keys)
    notes = _notes_sync(user_id)["items"]
    return next(item for item in notes if item["id"] == note_id)

def _update_note_sync(note_id: int, user_id: int, payload: NoteUpdateRequest) -> dict[str, Any]:
    update_data = payload.model_dump(exclude_none=True)
    update_data["note_id"] = note_id
    update_data["user_id"] = user_id
    fields = [key for key in ("title", "content", "course", "knowledge_tag") if key in update_data]
    has_attachment_update = payload.attachment_ids is not None
    if not fields and not has_attachment_update:
        raise HTTPException(status_code=400, detail="没有可更新的笔记内容。")
    storage_keys: list[str] = []
    with SessionLocal() as db:
        current_note = db.execute(
            text("SELECT content FROM user_notes WHERE id = :note_id AND user_id = :user_id LIMIT 1"),
            {"note_id": note_id, "user_id": user_id},
        ).mappings().first()
        if not current_note:
            raise HTTPException(status_code=404, detail="没有找到这条笔记。")
        existing_ids = [
            int(file_id)
            for file_id in db.execute(
                text("SELECT uploaded_file_id FROM note_attachments WHERE note_id = :note_id ORDER BY sort_order, id"),
                {"note_id": note_id},
            ).scalars().all()
        ]
        next_content = payload.content if payload.content is not None else str(current_note["content"] or "")
        next_attachments = payload.attachment_ids if payload.attachment_ids is not None else existing_ids
        if not next_content.strip() and not next_attachments:
            raise HTTPException(status_code=422, detail="请填写笔记内容或至少保留一个附件。")
        if fields:
            assignments = ", ".join(f"{field} = :{field}" for field in fields)
            db.execute(
                text(
                    f"""
                    UPDATE user_notes
                    SET {assignments}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :note_id AND user_id = :user_id
                    """
                ),
                update_data,
            )
        if has_attachment_update:
            storage_keys = _sync_note_attachments(db, note_id, user_id, payload.attachment_ids or [])
        db.commit()
    _remove_note_files(storage_keys)
    notes = _notes_sync(user_id)["items"]
    return next(item for item in notes if item["id"] == note_id)

def _delete_note_sync(note_id: int, user_id: int) -> dict[str, Any]:
    storage_keys: list[str] = []
    with SessionLocal() as db:
        attachment_rows = db.execute(
            text(
                """
                SELECT uf.id, uf.storage_key
                FROM note_attachments AS na
                JOIN uploaded_files AS uf ON uf.id = na.uploaded_file_id
                JOIN user_notes AS un ON un.id = na.note_id
                WHERE na.note_id = :note_id AND un.user_id = :user_id
                """
            ),
            {"note_id": note_id, "user_id": user_id},
        ).mappings().all()
        result = db.execute(
            text("DELETE FROM user_notes WHERE id = :note_id AND user_id = :user_id"),
            {"note_id": note_id, "user_id": user_id},
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="没有找到这条笔记。")
        for row in attachment_rows:
            db.execute(text("DELETE FROM uploaded_files WHERE id = :file_id"), {"file_id": int(row["id"])})
            storage_keys.append(str(row["storage_key"]))
        db.commit()
    _remove_note_files(storage_keys)
    return {"deleted": True, "id": note_id}

