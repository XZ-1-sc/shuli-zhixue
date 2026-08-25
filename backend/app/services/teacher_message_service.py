from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text

from ..database.session import SessionLocal


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _teacher_student_class(db: Any, teacher_id: int, student_id: int) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT c.id, c.name
            FROM classes c
            JOIN class_members cm ON cm.class_id=c.id AND cm.status='active'
            WHERE c.teacher_id=:teacher_id AND c.status='active' AND cm.student_id=:student_id
            ORDER BY c.id LIMIT 1
            """
        ),
        {"teacher_id": teacher_id, "student_id": student_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能与当前任教班级中的学生联系。")
    return dict(row)


def _student_teacher_class(db: Any, student_id: int, teacher_id: int) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT c.id, c.name
            FROM classes c
            JOIN class_members cm ON cm.class_id=c.id AND cm.status='active'
            WHERE c.teacher_id=:teacher_id AND c.status='active' AND cm.student_id=:student_id
            ORDER BY c.id LIMIT 1
            """
        ),
        {"teacher_id": teacher_id, "student_id": student_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能与当前所在班级的教师联系。")
    return dict(row)


def _message_payload(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "teacher_id": int(row["teacher_id"]),
        "student_id": int(row["student_id"]),
        "class_id": int(row["class_id"]) if row["class_id"] else None,
        "sender_role": str(row["sender_role"]),
        "message_type": str(row["message_type"]),
        "content": str(row["content"]),
        "is_read": bool(row["is_read"]),
        "created_at": _iso(row["created_at"]),
    }


def teacher_conversations_sync(teacher_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT u.id AS student_id, u.username, COALESCE(u.nickname,u.username) AS nickname,
                       GROUP_CONCAT(DISTINCT c.name ORDER BY c.name SEPARATOR '、') AS class_name,
                       (SELECT content FROM teacher_student_messages last_message
                        WHERE last_message.teacher_id=:teacher_id AND last_message.student_id=u.id
                        ORDER BY last_message.created_at DESC,last_message.id DESC LIMIT 1) AS latest_message,
                       (SELECT created_at FROM teacher_student_messages last_message
                        WHERE last_message.teacher_id=:teacher_id AND last_message.student_id=u.id
                        ORDER BY last_message.created_at DESC,last_message.id DESC LIMIT 1) AS latest_at,
                       (SELECT COUNT(*) FROM teacher_student_messages unread
                        WHERE unread.teacher_id=:teacher_id AND unread.student_id=u.id
                          AND unread.sender_role='student' AND unread.is_read=0) AS unread_count
                FROM classes c
                JOIN class_members cm ON cm.class_id=c.id AND cm.status='active'
                JOIN users u ON u.id=cm.student_id
                WHERE c.teacher_id=:teacher_id AND c.status='active'
                GROUP BY u.id,u.username,u.nickname
                ORDER BY latest_at IS NULL,latest_at DESC,u.username
                """
            ),
            {"teacher_id": teacher_id},
        ).mappings().all()
    return {
        "items": [
            {
                "student_id": int(row["student_id"]),
                "username": str(row["username"]),
                "nickname": str(row["nickname"]),
                "class_name": str(row["class_name"] or ""),
                "latest_message": str(row["latest_message"] or ""),
                "latest_at": _iso(row["latest_at"]),
                "unread_count": int(row["unread_count"] or 0),
            }
            for row in rows
        ]
    }


def student_conversations_sync(student_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT u.id AS teacher_id, u.username, COALESCE(u.nickname,u.username) AS nickname,
                       GROUP_CONCAT(DISTINCT c.name ORDER BY c.name SEPARATOR '、') AS class_name,
                       (SELECT content FROM teacher_student_messages last_message
                        WHERE last_message.teacher_id=u.id AND last_message.student_id=:student_id
                        ORDER BY last_message.created_at DESC,last_message.id DESC LIMIT 1) AS latest_message,
                       (SELECT created_at FROM teacher_student_messages last_message
                        WHERE last_message.teacher_id=u.id AND last_message.student_id=:student_id
                        ORDER BY last_message.created_at DESC,last_message.id DESC LIMIT 1) AS latest_at,
                       (SELECT COUNT(*) FROM teacher_student_messages unread
                        WHERE unread.teacher_id=u.id AND unread.student_id=:student_id
                          AND unread.sender_role='teacher' AND unread.is_read=0) AS unread_count
                FROM class_members cm
                JOIN classes c ON c.id=cm.class_id AND c.status='active'
                JOIN users u ON u.id=c.teacher_id
                WHERE cm.student_id=:student_id AND cm.status='active'
                GROUP BY u.id,u.username,u.nickname
                ORDER BY latest_at IS NULL,latest_at DESC,u.username
                """
            ),
            {"student_id": student_id},
        ).mappings().all()
    return {
        "items": [
            {
                "teacher_id": int(row["teacher_id"]),
                "username": str(row["username"]),
                "nickname": str(row["nickname"]),
                "class_name": str(row["class_name"] or ""),
                "latest_message": str(row["latest_message"] or ""),
                "latest_at": _iso(row["latest_at"]),
                "unread_count": int(row["unread_count"] or 0),
            }
            for row in rows
        ]
    }


def message_thread_sync(actor_id: int, counterpart_id: int, actor_role: str) -> dict[str, Any]:
    with SessionLocal() as db:
        if actor_role == "teacher":
            teacher_id, student_id = actor_id, counterpart_id
            class_row = _teacher_student_class(db, teacher_id, student_id)
            incoming_role = "student"
        else:
            teacher_id, student_id = counterpart_id, actor_id
            class_row = _student_teacher_class(db, student_id, teacher_id)
            incoming_role = "teacher"
        db.execute(
            text(
                """
                UPDATE teacher_student_messages SET is_read=1
                WHERE teacher_id=:teacher_id AND student_id=:student_id
                  AND sender_role=:incoming_role AND is_read=0
                """
            ),
            {"teacher_id": teacher_id, "student_id": student_id, "incoming_role": incoming_role},
        )
        if actor_role == "teacher":
            notification_types = ("student_message", "student_message")
            action_url = f"/teacher/messages?student_id={student_id}"
        else:
            notification_types = ("teacher_message", "teacher_advice")
            action_url = f"/messages?teacher_id={teacher_id}"
        db.execute(
            text(
                """
                UPDATE user_notifications SET is_read=1
                WHERE user_id=:actor_id AND type IN (:type_one,:type_two)
                  AND action_url=:action_url AND is_read=0
                """
            ),
            {
                "actor_id": actor_id,
                "type_one": notification_types[0],
                "type_two": notification_types[1],
                "action_url": action_url,
            },
        )
        rows = db.execute(
            text(
                """
                SELECT id,teacher_id,student_id,class_id,sender_role,message_type,content,is_read,created_at
                FROM teacher_student_messages
                WHERE teacher_id=:teacher_id AND student_id=:student_id
                ORDER BY created_at,id
                """
            ),
            {"teacher_id": teacher_id, "student_id": student_id},
        ).mappings().all()
        db.commit()
    return {"class": {"id": int(class_row["id"]), "name": str(class_row["name"])}, "items": [_message_payload(row) for row in rows]}


def _insert_message(
    db: Any,
    *,
    teacher_id: int,
    student_id: int,
    class_id: int,
    sender_role: str,
    content: str,
    message_type: str = "chat",
) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO teacher_student_messages
              (teacher_id,student_id,class_id,sender_role,message_type,content)
            VALUES (:teacher_id,:student_id,:class_id,:sender_role,:message_type,:content)
            """
        ),
        {
            "teacher_id": teacher_id,
            "student_id": student_id,
            "class_id": class_id,
            "sender_role": sender_role,
            "message_type": message_type,
            "content": content,
        },
    )
    recipient_id = student_id if sender_role == "teacher" else teacher_id
    notification_type = "teacher_message" if sender_role == "teacher" else "student_message"
    title = "老师给你发来新消息" if sender_role == "teacher" else "学生给你发来新消息"
    action_url = f"/messages?teacher_id={teacher_id}" if sender_role == "teacher" else f"/teacher/messages?student_id={student_id}"
    db.execute(
        text(
            """
            INSERT INTO user_notifications (user_id,type,title,content,action_url)
            VALUES (:recipient_id,:notification_type,:title,:content,:action_url)
            """
        ),
        {
            "recipient_id": recipient_id,
            "notification_type": notification_type,
            "title": title,
            "content": content,
            "action_url": action_url,
        },
    )
    return int(result.lastrowid)


def send_message_sync(actor_id: int, counterpart_id: int, actor_role: str, content: str) -> dict[str, Any]:
    normalized = content.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="消息内容不能为空。")
    with SessionLocal() as db:
        if actor_role == "teacher":
            teacher_id, student_id = actor_id, counterpart_id
            class_row = _teacher_student_class(db, teacher_id, student_id)
        else:
            teacher_id, student_id = counterpart_id, actor_id
            class_row = _student_teacher_class(db, student_id, teacher_id)
        message_id = _insert_message(
            db,
            teacher_id=teacher_id,
            student_id=student_id,
            class_id=int(class_row["id"]),
            sender_role=actor_role,
            content=normalized,
        )
        db.commit()
        row = db.execute(
            text("SELECT * FROM teacher_student_messages WHERE id=:id"), {"id": message_id}
        ).mappings().one()
    return _message_payload(row)


def unread_count_sync(user_id: int, role: str) -> dict[str, int]:
    field = "teacher_id" if role in {"teacher", "admin"} else "student_id"
    incoming_role = "student" if role in {"teacher", "admin"} else "teacher"
    with SessionLocal() as db:
        count = db.execute(
            text(
                f"SELECT COUNT(*) FROM teacher_student_messages WHERE {field}=:user_id AND sender_role=:incoming_role AND is_read=0"
            ),
            {"user_id": user_id, "incoming_role": incoming_role},
        ).scalar()
    return {"unread_count": int(count or 0)}
