import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..session import SessionLocal


def _question_access(db, user: dict[str, Any], question_id: int, *, owner_required: bool = False) -> dict[str, Any]:
    question = db.execute(text("SELECT id,created_by FROM questions WHERE id=:id AND deleted_at IS NULL"), {"id": question_id}).mappings().first()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在。")
    user_id = int(user["id"])
    if user["role"] == "student":
        answered = db.execute(text("SELECT 1 FROM practice_records WHERE user_id=:user_id AND question_id=:question_id LIMIT 1"),
                              {"user_id": user_id, "question_id": question_id}).first()
        if not answered:
            raise HTTPException(status_code=403, detail="完成本题作答后才能查看讨论。")
    elif user["role"] in {"teacher", "admin"}:
        if owner_required and user["role"] != "admin" and int(question["created_by"] or 0) != user_id:
            raise HTTPException(status_code=403, detail="只有题目创建教师可以执行此操作。")
        if not owner_required and user["role"] != "admin" and int(question["created_by"] or 0) != user_id:
            managed = db.execute(text("""
                SELECT 1 FROM practice_records pr
                JOIN class_members cm ON cm.student_id=pr.user_id AND cm.status='active'
                JOIN classes c ON c.id=cm.class_id AND c.teacher_id=:teacher_id AND c.status='active'
                WHERE pr.question_id=:question_id LIMIT 1
            """), {"teacher_id": user_id, "question_id": question_id}).first()
            if not managed:
                raise HTTPException(status_code=403, detail="该题讨论不属于当前教师管理范围。")
    else:
        raise HTTPException(status_code=403, detail="当前账号没有讨论区权限。")
    return dict(question)


def _comment_row(db, comment_id: int) -> dict[str, Any]:
    row = db.execute(text("SELECT * FROM question_comments WHERE id=:id"), {"id": comment_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="评论不存在。")
    return dict(row)


def _question_comments_sync(user: dict[str, Any], question_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        _question_access(db, user, question_id)
        rows = db.execute(text("""
            SELECT qc.id,qc.question_id,qc.user_id,qc.parent_id,qc.content,qc.image_ids,
                   qc.upvotes,qc.is_best,qc.status,qc.created_at,u.nickname,u.username,u.role,
                   EXISTS(SELECT 1 FROM comment_upvotes cu WHERE cu.comment_id=qc.id AND cu.user_id=:viewer_id) liked
            FROM question_comments qc JOIN users u ON u.id=qc.user_id
            WHERE qc.question_id=:question_id AND (qc.status='active' OR qc.user_id=:viewer_id)
            ORDER BY qc.is_best DESC,qc.upvotes DESC,qc.created_at,qc.id
        """), {"question_id": question_id, "viewer_id": int(user["id"])}).mappings().all()
    items = []
    for row in rows:
        image_ids = row["image_ids"] if isinstance(row["image_ids"], list) else json.loads(row["image_ids"] or "[]")
        items.append({"id": int(row["id"]), "question_id": int(row["question_id"]), "user_id": int(row["user_id"]),
                      "parent_id": int(row["parent_id"]) if row["parent_id"] else None, "content": str(row["content"] or ""),
                      "images": [{"id": int(file_id), "url": f"/api/files/{int(file_id)}"} for file_id in image_ids],
                      "upvotes": int(row["upvotes"] or 0), "is_best": bool(row["is_best"]), "liked": bool(row["liked"]),
                      "status": str(row["status"]), "author": str(row["nickname"] or row["username"]),
                      "author_role": str(row["role"]), "created_at": row["created_at"].isoformat() if row["created_at"] else None})
    return {"question_id": question_id, "items": items, "total": len(items), "can_comment": True}


def _create_question_comment_sync(user: dict[str, Any], question_id: int, payload: Any) -> dict[str, Any]:
    with SessionLocal() as db:
        _question_access(db, user, question_id)
        if payload.parent_id:
            parent = _comment_row(db, payload.parent_id)
            if int(parent["question_id"]) != question_id:
                raise HTTPException(status_code=422, detail="回复的评论不属于当前题目。")
        if payload.image_ids:
            rows = db.execute(text("SELECT id FROM uploaded_files WHERE user_id=:user_id"), {"user_id": int(user["id"])}).scalars().all()
            owned = {int(item) for item in rows}
            if any(file_id not in owned for file_id in payload.image_ids):
                raise HTTPException(status_code=403, detail="评论图片必须由当前账号上传。")
        result = db.execute(text("""
            INSERT INTO question_comments(question_id,user_id,parent_id,content,image_ids)
            VALUES(:question_id,:user_id,:parent_id,:content,:image_ids)
        """), {"question_id": question_id, "user_id": int(user["id"]), "parent_id": payload.parent_id,
                 "content": payload.content, "image_ids": json.dumps(payload.image_ids)})
        comment_id = int(result.lastrowid)
        db.commit()
    return {"id": comment_id, "created": True}


def _upvote_comment_sync(user: dict[str, Any], comment_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        comment = _comment_row(db, comment_id)
        _question_access(db, user, int(comment["question_id"]))
        if comment["status"] != "active":
            raise HTTPException(status_code=409, detail="已隐藏评论不能点赞。")
        created = True
        try:
            db.execute(text("INSERT INTO comment_upvotes(comment_id,user_id) VALUES(:comment_id,:user_id)"),
                       {"comment_id": comment_id, "user_id": int(user["id"])})
            db.execute(text("UPDATE question_comments SET upvotes=upvotes+1 WHERE id=:id"), {"id": comment_id})
            db.commit()
        except IntegrityError:
            db.rollback()
            created = False
        count = int(db.execute(text("SELECT upvotes FROM question_comments WHERE id=:id"), {"id": comment_id}).scalar() or 0)
    return {"comment_id": comment_id, "liked": True, "created": created, "upvotes": count}


def _best_comment_sync(user: dict[str, Any], comment_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        comment = _comment_row(db, comment_id)
        _question_access(db, user, int(comment["question_id"]), owner_required=True)
        if comment["status"] != "active":
            raise HTTPException(status_code=409, detail="已隐藏评论不能设为最佳。")
        db.execute(text("UPDATE question_comments SET is_best=0 WHERE question_id=:question_id"), {"question_id": comment["question_id"]})
        db.execute(text("UPDATE question_comments SET is_best=1 WHERE id=:id"), {"id": comment_id})
    return {"comment_id": comment_id, "is_best": True}


def _hide_comment_sync(user: dict[str, Any], comment_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        comment = _comment_row(db, comment_id)
        _question_access(db, user, int(comment["question_id"]), owner_required=True)
        db.execute(text("UPDATE question_comments SET status='hidden',is_best=0 WHERE id=:id"), {"id": comment_id})
    return {"comment_id": comment_id, "status": "hidden"}
