import json
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text

from ..api.schemas import MessageSendRequest
from ..database.session import SessionLocal


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _json_data(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return fallback


def _user_role(db: Any, user_id: int) -> str:
    role = db.execute(text("SELECT role FROM users WHERE id=:id AND status=1"), {"id": user_id}).scalar()
    if not role:
        raise HTTPException(status_code=404, detail="联系人不存在或已停用。")
    return str(role)


def _validate_relationship(db: Any, actor_id: int, target_id: int, relation: str) -> dict[str, Any]:
    if actor_id == target_id:
        raise HTTPException(status_code=422, detail="不能与自己发起会话。")
    actor_role = _user_role(db, actor_id)
    target_role = _user_role(db, target_id)
    if relation == "teacher_student":
        if {actor_role, target_role} != {"teacher", "student"} and not (
            "admin" in {actor_role, target_role} and "student" in {actor_role, target_role}
        ):
            raise HTTPException(status_code=422, detail="师生会话必须由一名教师和一名学生组成。")
        teacher_id = actor_id if actor_role in {"teacher", "admin"} else target_id
        student_id = target_id if teacher_id == actor_id else actor_id
        row = db.execute(
            text(
                """
                SELECT c.id,c.name
                FROM classes c JOIN class_members cm ON cm.class_id=c.id AND cm.status='active'
                WHERE c.teacher_id=:teacher_id AND c.status='active' AND cm.student_id=:student_id
                ORDER BY c.id LIMIT 1
                """
            ),
            {"teacher_id": teacher_id, "student_id": student_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能联系当前活跃任教关系中的师生。")
        return {"teacher_id": teacher_id, "student_id": student_id, "class_id": int(row["id"]), "class_name": str(row["name"])}
    if relation != "student_student" or actor_role != "student" or target_role != "student":
        raise HTTPException(status_code=422, detail="同学会话必须由两名学生组成。")
    network = db.execute(
        text(
            """
            SELECT source_class.teacher_id,source_class.id AS source_class_id,target_class.id AS target_class_id
            FROM class_members source_member
            JOIN classes source_class ON source_class.id=source_member.class_id AND source_class.status='active'
            JOIN classes target_class ON target_class.teacher_id=source_class.teacher_id AND target_class.status='active'
            JOIN class_members target_member ON target_member.class_id=target_class.id AND target_member.status='active'
            WHERE source_member.student_id=:actor_id AND source_member.status='active'
              AND target_member.student_id=:target_id
            LIMIT 1
            """
        ),
        {"actor_id": actor_id, "target_id": target_id},
    ).mappings().first()
    if not network:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能联系同一教师网络内的学生。")
    return {"teacher_id": int(network["teacher_id"]), "source_class_id": int(network["source_class_id"]), "target_class_id": int(network["target_class_id"])}


def contacts_sync(user_id: int, role: str, search: str | None = None) -> dict[str, Any]:
    term = (search or "").strip()
    like = f"%{term}%"
    with SessionLocal() as db:
        if role in {"teacher", "admin"}:
            rows = db.execute(
                text(
                    """
                    SELECT DISTINCT u.id AS user_id,u.username,COALESCE(u.nickname,u.username) AS nickname,
                           c.id AS class_id,c.name AS class_name
                    FROM classes c
                    JOIN class_members cm ON cm.class_id=c.id AND cm.status='active'
                    JOIN users u ON u.id=cm.student_id AND u.status=1
                    WHERE c.teacher_id=:user_id AND c.status='active'
                      AND (:term='' OR u.username LIKE :like OR COALESCE(u.nickname,'') LIKE :like)
                    ORDER BY c.name,u.username
                    """
                ),
                {"user_id": user_id, "term": term, "like": like},
            ).mappings().all()
            items = [
                {"user_id": int(row["user_id"]), "username": str(row["username"]), "nickname": str(row["nickname"]), "role": "student", "relation": "teacher_student", "class_id": int(row["class_id"]), "class_name": str(row["class_name"])}
                for row in rows
            ]
            sections: dict[int, dict[str, Any]] = {}
            for item in items:
                section = sections.setdefault(item["class_id"], {"key": f"class-{item['class_id']}", "label": item["class_name"], "items": []})
                section["items"].append(item)
            return {"groups": [{"key": "students", "label": "我的学生", "sections": list(sections.values()), "items": items}], "items": items}

        teachers = db.execute(
            text(
                """
                SELECT DISTINCT u.id AS user_id,u.username,COALESCE(u.nickname,u.username) AS nickname,
                       c.id AS class_id,c.name AS class_name
                FROM class_members cm JOIN classes c ON c.id=cm.class_id AND c.status='active'
                JOIN users u ON u.id=c.teacher_id AND u.status=1
                WHERE cm.student_id=:user_id AND cm.status='active'
                  AND (:term='' OR u.username LIKE :like OR COALESCE(u.nickname,'') LIKE :like)
                ORDER BY u.username,c.name
                """
            ),
            {"user_id": user_id, "term": term, "like": like},
        ).mappings().all()
        peers = db.execute(
            text(
                """
                SELECT DISTINCT peer.id AS user_id,peer.username,COALESCE(peer.nickname,peer.username) AS nickname,
                       target_class.id AS class_id,target_class.name AS class_name,
                       source_class.teacher_id
                FROM class_members source_member
                JOIN classes source_class ON source_class.id=source_member.class_id AND source_class.status='active'
                JOIN classes target_class ON target_class.teacher_id=source_class.teacher_id AND target_class.status='active'
                JOIN class_members target_member ON target_member.class_id=target_class.id AND target_member.status='active'
                JOIN users peer ON peer.id=target_member.student_id AND peer.status=1
                WHERE source_member.student_id=:user_id AND source_member.status='active'
                  AND peer.id<>:user_id
                  AND (:term='' OR peer.username LIKE :like OR COALESCE(peer.nickname,'') LIKE :like)
                ORDER BY peer.username,target_class.name
                """
            ),
            {"user_id": user_id, "term": term, "like": like},
        ).mappings().all()
    teacher_items = [
        {"user_id": int(row["user_id"]), "username": str(row["username"]), "nickname": str(row["nickname"]), "role": "teacher", "relation": "teacher_student", "class_id": int(row["class_id"]), "class_name": str(row["class_name"])}
        for row in teachers
    ]
    seen: set[int] = set()
    peer_items = []
    for row in peers:
        peer_id = int(row["user_id"])
        if peer_id in seen:
            continue
        seen.add(peer_id)
        peer_items.append({"user_id": peer_id, "username": str(row["username"]), "nickname": str(row["nickname"]), "role": "student", "relation": "student_student", "class_id": int(row["class_id"]), "class_name": str(row["class_name"])})
    return {"groups": [{"key": "teachers", "label": "我的教师", "items": teacher_items}, {"key": "peers", "label": "同一教师网络的同学", "items": peer_items}], "items": teacher_items + peer_items}


def _conversation(db: Any, user_id: int, role: str, conversation_id: int) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT c.*,other.id AS other_id,other.username AS other_username,
                   COALESCE(other.nickname,other.username) AS other_nickname,other.role AS other_role
            FROM conversations c
            JOIN users other ON other.id=CASE WHEN c.participant_a=:user_id THEN c.participant_b ELSE c.participant_a END
            WHERE c.id=:conversation_id AND (c.participant_a=:user_id OR c.participant_b=:user_id)
            LIMIT 1
            """
        ),
        {"conversation_id": conversation_id, "user_id": user_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在或当前账号不是参与者。")
    if role in {"teacher", "admin"} and str(row["relation"]) != "teacher_student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="教师无权查看学生之间的私密会话。")
    _validate_relationship(db, user_id, int(row["other_id"]), str(row["relation"]))
    return dict(row)


def _ensure_conversation(db: Any, user_id: int, target_id: int, relation: str) -> int:
    _validate_relationship(db, user_id, target_id, relation)
    participant_a, participant_b = sorted((user_id, target_id))
    result = db.execute(
        text(
            """
            INSERT INTO conversations (participant_a,participant_b,relation)
            VALUES (:participant_a,:participant_b,:relation)
            ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)
            """
        ),
        {"participant_a": participant_a, "participant_b": participant_b, "relation": relation},
    )
    return int(result.lastrowid)


def start_conversation_sync(user_id: int, role: str, target_id: int, relation: str) -> dict[str, Any]:
    with SessionLocal() as db:
        conversation_id = _ensure_conversation(db, user_id, target_id, relation)
        db.commit()
        row = _conversation(db, user_id, role, conversation_id)
    return {"conversation_id": conversation_id, "relation": relation, "other": {"id": int(row["other_id"]), "username": str(row["other_username"]), "nickname": str(row["other_nickname"]), "role": str(row["other_role"])}}


def conversations_sync(user_id: int, role: str, relation: str | None = None) -> dict[str, Any]:
    clauses = ["(c.participant_a=:user_id OR c.participant_b=:user_id)"]
    params: dict[str, Any] = {"user_id": user_id}
    if role in {"teacher", "admin"}:
        clauses.append("c.relation='teacher_student'")
    if relation:
        clauses.append("c.relation=:relation")
        params["relation"] = relation
    with SessionLocal() as db:
        rows = db.execute(
            text(
                f"""
                SELECT c.id,c.relation,c.last_message_at,c.created_at,
                       other.id AS other_id,other.username AS other_username,
                       COALESCE(other.nickname,other.username) AS other_nickname,other.role AS other_role,
                       latest.content AS latest_content,latest.attachment_ids AS latest_attachments,
                       latest.question_ref AS latest_question_ref,latest.message_type AS latest_type,
                       (SELECT COUNT(*) FROM messages unread
                        WHERE unread.conversation_id=c.id AND unread.sender_id<>:user_id AND unread.is_read=0) AS unread_count
                FROM conversations c
                JOIN users other ON other.id=CASE WHEN c.participant_a=:user_id THEN c.participant_b ELSE c.participant_a END
                LEFT JOIN messages latest ON latest.id=(SELECT lm.id FROM messages lm WHERE lm.conversation_id=c.id ORDER BY lm.created_at DESC,lm.id DESC LIMIT 1)
                WHERE {' AND '.join(clauses)}
                ORDER BY c.last_message_at IS NULL,c.last_message_at DESC,c.id DESC
                """
            ),
            params,
        ).mappings().all()
    items = []
    for row in rows:
        attachments = _json_data(row["latest_attachments"], [])
        question_ref = _json_data(row["latest_question_ref"], None)
        preview = str(row["latest_content"] or "")
        if not preview and attachments:
            preview = "[图片]"
        if not preview and question_ref:
            preview = "[题目引用]"
        items.append({"id": int(row["id"]), "relation": str(row["relation"]), "last_message_at": _iso(row["last_message_at"]), "latest_message": preview, "latest_type": str(row["latest_type"] or "chat"), "unread_count": int(row["unread_count"] or 0), "other": {"id": int(row["other_id"]), "username": str(row["other_username"]), "nickname": str(row["other_nickname"]), "role": str(row["other_role"])}})
    return {"items": items, "total": len(items)}


def _attachment_payloads(db: Any, attachment_ids: list[int]) -> list[dict[str, Any]]:
    if not attachment_ids:
        return []
    placeholders = ",".join(f":file_{index}" for index in range(len(attachment_ids)))
    rows = db.execute(
        text(f"SELECT id,original_name,mime_type,size_bytes,width,height FROM uploaded_files WHERE id IN ({placeholders})"),
        {f"file_{index}": file_id for index, file_id in enumerate(attachment_ids)},
    ).mappings().all()
    by_id = {int(row["id"]): row for row in rows}
    return [{"id": file_id, "name": str(by_id[file_id]["original_name"]), "mime_type": str(by_id[file_id]["mime_type"]), "size_bytes": int(by_id[file_id]["size_bytes"]), "width": int(by_id[file_id]["width"] or 0), "height": int(by_id[file_id]["height"] or 0), "url": f"/api/files/{file_id}"} for file_id in attachment_ids if file_id in by_id]


def _message_payload(db: Any, row: Any) -> dict[str, Any]:
    attachment_ids = [int(value) for value in _json_data(row["attachment_ids"], [])]
    return {"id": int(row["id"]), "conversation_id": int(row["conversation_id"]), "sender_id": int(row["sender_id"]), "message_type": str(row["message_type"]), "content": str(row["content"] or ""), "attachments": _attachment_payloads(db, attachment_ids), "question_ref": _json_data(row["question_ref"], None), "is_read": bool(row["is_read"]), "created_at": _iso(row["created_at"])}


def conversation_messages_sync(user_id: int, role: str, conversation_id: int, limit: int, before_id: int | None) -> dict[str, Any]:
    with SessionLocal() as db:
        conversation = _conversation(db, user_id, role, conversation_id)
        rows = db.execute(
            text(
                """
                SELECT id,conversation_id,sender_id,message_type,content,attachment_ids,question_ref,is_read,created_at
                FROM messages
                WHERE conversation_id=:conversation_id AND (:before_id IS NULL OR id<:before_id)
                ORDER BY id DESC LIMIT :fetch_limit
                """
            ),
            {"conversation_id": conversation_id, "before_id": before_id, "fetch_limit": limit + 1},
        ).mappings().all()
        has_more = len(rows) > limit
        page = list(reversed(rows[:limit]))
        items = [_message_payload(db, row) for row in page]
    return {"conversation": {"id": conversation_id, "relation": str(conversation["relation"]), "other": {"id": int(conversation["other_id"]), "username": str(conversation["other_username"]), "nickname": str(conversation["other_nickname"]), "role": str(conversation["other_role"])}}, "items": items, "has_more": has_more, "next_before_id": items[0]["id"] if has_more and items else None}


def _validate_attachments(db: Any, user_id: int, attachment_ids: list[int]) -> list[int]:
    if not attachment_ids:
        return []
    placeholders = ",".join(f":file_{index}" for index in range(len(attachment_ids)))
    params = {f"file_{index}": file_id for index, file_id in enumerate(attachment_ids)} | {"user_id": user_id}
    rows = db.execute(text(f"SELECT id,mime_type FROM uploaded_files WHERE user_id=:user_id AND id IN ({placeholders})"), params).mappings().all()
    found = {int(row["id"]): str(row["mime_type"]) for row in rows}
    if set(found) != set(attachment_ids) or any(not mime.startswith("image/") for mime in found.values()):
        raise HTTPException(status_code=422, detail="消息附件不存在、不属于当前账号或不是图片。")
    return attachment_ids


def _normalize_question_ref(db: Any, user_id: int, role: str, value: Any) -> dict[str, Any] | None:
    if not value:
        return None
    question_id = int(value.question_id)
    if role in {"teacher", "admin"}:
        access_clause = "q.created_by=:user_id OR (q.publish_status='published' AND q.visibility='public') OR EXISTS (SELECT 1 FROM assignment_questions aq JOIN assignments a ON a.id=aq.assignment_id WHERE aq.question_id=q.id AND a.teacher_id=:user_id)"
    else:
        access_clause = "(q.publish_status='published' AND q.visibility='public') OR EXISTS (SELECT 1 FROM practice_records pr WHERE pr.question_id=q.id AND pr.user_id=:user_id) OR EXISTS (SELECT 1 FROM assignment_questions aq JOIN assignments a ON a.id=aq.assignment_id JOIN class_members cm ON cm.class_id=a.class_id WHERE aq.question_id=q.id AND a.status IN ('published','closed') AND cm.student_id=:user_id AND cm.status='active')"
    row = db.execute(text(f"SELECT q.id,q.question_text,q.knowledge_tag,q.course FROM questions q WHERE q.id=:question_id AND q.deleted_at IS NULL AND ({access_clause}) LIMIT 1"), {"question_id": question_id, "user_id": user_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号无权引用这道题。")
    record_id = int(value.record_id) if value.record_id else None
    if record_id:
        record = db.execute(text("SELECT id FROM practice_records WHERE id=:record_id AND user_id=:user_id AND question_id=:question_id"), {"record_id": record_id, "user_id": user_id, "question_id": question_id}).scalar()
        if not record:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能引用自己的作答记录。")
    return {"question_id": question_id, "record_id": record_id, "text": str(row["question_text"])[:500], "knowledge_tag": str(row["knowledge_tag"]), "course": str(row["course"])}


def _insert_message(db: Any, conversation: dict[str, Any], sender_id: int, payload: MessageSendRequest) -> int:
    attachment_ids = _validate_attachments(db, sender_id, payload.attachment_ids)
    sender_role = _user_role(db, sender_id)
    question_ref = _normalize_question_ref(db, sender_id, sender_role, payload.question_ref)
    result = db.execute(
        text(
            """
            INSERT INTO messages (conversation_id,sender_id,message_type,content,attachment_ids,question_ref)
            VALUES (:conversation_id,:sender_id,:message_type,:content,:attachment_ids,:question_ref)
            """
        ),
        {"conversation_id": conversation["id"], "sender_id": sender_id, "message_type": payload.message_type, "content": payload.content, "attachment_ids": json.dumps(attachment_ids) if attachment_ids else None, "question_ref": json.dumps(question_ref, ensure_ascii=False) if question_ref else None},
    )
    db.execute(text("UPDATE conversations SET last_message_at=NOW() WHERE id=:id"), {"id": conversation["id"]})
    recipient_id = int(conversation["participant_b"] if int(conversation["participant_a"]) == sender_id else conversation["participant_a"])
    recipient_role = _user_role(db, recipient_id)
    relation = str(conversation["relation"])
    if relation == "student_student":
        notification_type, title = "peer_message", "同学给你发来新消息"
    elif sender_role in {"teacher", "admin"}:
        notification_type, title = ("teacher_advice", "老师发来学习调整建议") if payload.message_type == "advice" else ("teacher_message", "老师给你发来新消息")
    else:
        notification_type, title = "student_message", "学生给你发来新消息"
    action_url = f"/teacher/messages?conversation_id={conversation['id']}" if recipient_role in {"teacher", "admin"} else f"/messages?conversation_id={conversation['id']}"
    preview = payload.content or ("[图片]" if attachment_ids else "[题目引用]")
    db.execute(text("INSERT INTO user_notifications (user_id,type,title,content,action_url) VALUES (:recipient,:type,:title,:content,:url)"), {"recipient": recipient_id, "type": notification_type, "title": title, "content": preview, "url": action_url})
    audit_payload = json.dumps({"relation": relation, "content_length": len(payload.content or ""), "attachment_count": len(attachment_ids), "has_question_ref": bool(question_ref)}, ensure_ascii=False)
    db.execute(text("INSERT INTO audit_logs (actor_user_id,action,entity_type,entity_id,payload) VALUES (:actor,'message.created','conversation',:conversation_id,:payload)"), {"actor": sender_id, "conversation_id": conversation["id"], "payload": audit_payload})
    return int(result.lastrowid)


def send_conversation_message_sync(user_id: int, role: str, conversation_id: int, payload: MessageSendRequest) -> dict[str, Any]:
    if payload.message_type == "advice" and role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="只有教师可以发送学习调整建议。")
    with SessionLocal() as db:
        conversation = _conversation(db, user_id, role, conversation_id)
        message_id = _insert_message(db, conversation, user_id, payload)
        db.commit()
        row = db.execute(text("SELECT * FROM messages WHERE id=:id"), {"id": message_id}).mappings().one()
        result = _message_payload(db, row)
    return result


def mark_conversation_read_sync(user_id: int, role: str, conversation_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        _conversation(db, user_id, role, conversation_id)
        result = db.execute(text("UPDATE messages SET is_read=1 WHERE conversation_id=:conversation_id AND sender_id<>:user_id AND is_read=0"), {"conversation_id": conversation_id, "user_id": user_id})
        db.execute(text("UPDATE user_notifications SET is_read=1 WHERE user_id=:user_id AND action_url=:url AND type IN ('teacher_message','student_message','peer_message','teacher_advice')"), {"user_id": user_id, "url": f"/teacher/messages?conversation_id={conversation_id}" if role in {"teacher", "admin"} else f"/messages?conversation_id={conversation_id}"})
        db.commit()
    return {"conversation_id": conversation_id, "read_count": int(result.rowcount or 0)}


def unread_count_sync(user_id: int, role: str) -> dict[str, int]:
    relation_clause = "AND c.relation='teacher_student'" if role in {"teacher", "admin"} else ""
    with SessionLocal() as db:
        count = db.execute(text(f"SELECT COUNT(*) FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE (c.participant_a=:user_id OR c.participant_b=:user_id) AND m.sender_id<>:user_id AND m.is_read=0 {relation_clause}"), {"user_id": user_id}).scalar()
    return {"unread_count": int(count or 0)}
