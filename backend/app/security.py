import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy import text

from .database.session import SessionLocal


SESSION_COOKIE_NAME = "math_brain_session"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_auth_session_sync(user_id: int, remember: bool = True) -> tuple[str, int]:
    max_age = 30 * 24 * 60 * 60 if remember else 12 * 60 * 60
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now() + timedelta(seconds=max_age)
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO auth_sessions (user_id, token_hash, expires_at)
                VALUES (:user_id, :token_hash, :expires_at)
                """
            ),
            {"user_id": user_id, "token_hash": _token_hash(token), "expires_at": expires_at},
        )
        db.execute(
            text(
                """
                DELETE FROM auth_sessions
                WHERE user_id = :user_id
                  AND (revoked_at IS NOT NULL OR expires_at < NOW())
                """
            ),
            {"user_id": user_id},
        )
        db.commit()
    return token, max_age


def revoke_auth_session_sync(token: str | None) -> None:
    if not token:
        return
    with SessionLocal() as db:
        db.execute(
            text("UPDATE auth_sessions SET revoked_at = NOW() WHERE token_hash = :token_hash AND revoked_at IS NULL"),
            {"token_hash": _token_hash(token)},
        )
        db.commit()


def current_session_user(request: Request) -> dict[str, Any]:
    if "user_id" in request.query_params:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="会话接口不接受 user_id，请使用当前登录账号。")
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录。")

    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT u.id, u.username, u.nickname, u.role, u.current_stage,
                       s.id AS session_id, s.last_seen_at
                FROM auth_sessions AS s
                JOIN users AS u ON u.id = s.user_id
                WHERE s.token_hash = :token_hash
                  AND s.revoked_at IS NULL
                  AND s.expires_at > NOW()
                  AND u.status = 1
                LIMIT 1
                """
            ),
            {"token_hash": _token_hash(token)},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录。")
        db.execute(
            text("UPDATE auth_sessions SET last_seen_at = NOW() WHERE id = :session_id"),
            {"session_id": row["session_id"]},
        )
        db.commit()
    return {
        "id": int(row["id"]),
        "username": str(row["username"]),
        "nickname": str(row["nickname"] or row["username"]),
        "role": str(row["role"]),
        "current_stage": str(row["current_stage"] or "大一"),
    }


def require_teacher(request: Request) -> dict[str, Any]:
    user = current_session_user(request)
    if user["role"] not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号没有教师端权限。")
    return user


def require_student(request: Request) -> dict[str, Any]:
    user = current_session_user(request)
    if user["role"] != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号没有学生端权限。")
    return user


def require_student_user(request: Request) -> dict[str, Any]:
    user = current_session_user(request)
    if user["role"] not in {"student", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号没有学生端权限。")
    if "user_id" in request.query_params:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="学生端接口不接受 user_id，请使用当前会话账号。")
    return user
