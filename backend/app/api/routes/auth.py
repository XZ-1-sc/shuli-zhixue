import asyncio
import hashlib
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from ...database.session import SessionLocal
from ...security import (
    SESSION_COOKIE_NAME,
    create_auth_session_sync,
    current_session_user,
    revoke_auth_session_sync,
)
from ...utils.password import hash_password, verify_password


router = APIRouter(prefix="/api", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    role: Literal["student", "teacher"] = "student"
    remember: bool = True


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: Literal["student", "teacher"] = "student"
    teacher_invite_code: str | None = Field(default=None, max_length=128)
    remember: bool = True


class LoginResponse(BaseModel):
    user_id: int
    username: str
    role: Literal["student", "teacher", "admin"]
    current_stage: str | None = None
    message: str


def _raise_database_error(exc: SQLAlchemyError) -> None:
    detail = "数据库暂时不可用，请检查 MySQL 和 DATABASE_URL。"
    if isinstance(exc, OperationalError) and "1045" in str(exc):
        detail = "数据库账号或密码不正确，请检查 backend/.env 里的 DATABASE_URL。"
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail) from exc


def _cookie_is_secure(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    return request.url.scheme == "https" or forwarded_proto == "https"


def _consume_teacher_invite_code(db: Any, submitted_code: str) -> int:
    code_hash = hashlib.sha256(submitted_code.encode("utf-8")).hexdigest()
    row = db.execute(
        text(
            """
            SELECT id
            FROM teacher_invite_codes
            WHERE code_hash = :code_hash
              AND status = 'active'
              AND (expires_at IS NULL OR expires_at > NOW())
              AND (max_uses IS NULL OR used_count < max_uses)
            LIMIT 1
            FOR UPDATE
            """
        ),
        {"code_hash": code_hash},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="教师邀请码无效、已过期或已用完。")
    code_id = int(row["id"])
    db.execute(
        text(
            """
            UPDATE teacher_invite_codes
            SET used_count = used_count + 1, last_used_at = NOW(), updated_at = CURRENT_TIMESTAMP
            WHERE id = :code_id
            """
        ),
        {"code_id": code_id},
    )
    return code_id


def _login_sync(payload: LoginRequest) -> LoginResponse:
    username = payload.username.strip()
    query = text(
        """
        SELECT id, username, password_hash, role, current_stage
        FROM users
        WHERE username = :username AND status = 1
        LIMIT 1
        """
    )
    try:
        with SessionLocal() as db:
            row = db.execute(query, {"username": username}).mappings().first()
            if not row or not verify_password(payload.password, row["password_hash"]):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误。")
            if str(row["role"]) != payload.role:
                role_name = "教师" if payload.role == "teacher" else "学生"
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"该账号不是{role_name}账号，请切换登录身份。",
                )
            db.execute(text("UPDATE users SET last_login_at = NOW() WHERE id = :user_id"), {"user_id": row["id"]})
            db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        _raise_database_error(exc)

    return LoginResponse(
        user_id=int(row["id"]),
        username=str(row["username"]),
        role=str(row["role"]),
        current_stage=str(row["current_stage"] or "大一"),
        message="登录成功",
    )


def _register_sync(payload: RegisterRequest) -> LoginResponse:
    username = payload.username.strip()
    if len(username) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="用户名至少需要 2 个字符。")

    insert_query = text(
        """
        INSERT INTO users (username, password_hash, nickname, role, current_stage)
        VALUES (:username, :password_hash, :nickname, :role, :current_stage)
        """
    )
    try:
        with SessionLocal() as db:
            if payload.role == "teacher":
                submitted_code = (payload.teacher_invite_code or "").strip()
                if not submitted_code:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请输入教师邀请码。")
                _consume_teacher_invite_code(db, submitted_code)
            result = db.execute(
                insert_query,
                {
                    "username": username,
                    "password_hash": hash_password(payload.password),
                    "nickname": username,
                    "role": payload.role,
                    "current_stage": "大一",
                },
            )
            if payload.role == "teacher":
                db.execute(
                    text(
                        """
                        INSERT INTO teacher_profiles (user_id, display_name)
                        VALUES (:user_id, :display_name)
                        """
                    ),
                    {"user_id": int(result.lastrowid), "display_name": username},
                )
            db.commit()
            user_id = int(result.lastrowid)
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在，请换一个用户名。") from exc
    except SQLAlchemyError as exc:
        _raise_database_error(exc)

    return LoginResponse(
        user_id=user_id,
        username=username,
        role=payload.role,
        current_stage="大一",
        message="注册成功",
    )


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, response: Response, request: Request) -> LoginResponse:
    result = await asyncio.to_thread(_login_sync, payload)
    token, max_age = await asyncio.to_thread(create_auth_session_sync, result.user_id, payload.remember)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=_cookie_is_secure(request),
        path="/",
    )
    return result


@router.post("/register", response_model=LoginResponse)
async def register(payload: RegisterRequest, response: Response, request: Request) -> LoginResponse:
    result = await asyncio.to_thread(_register_sync, payload)
    token, max_age = await asyncio.to_thread(create_auth_session_sync, result.user_id, payload.remember)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=_cookie_is_secure(request),
        path="/",
    )
    return result


@router.get("/auth/me", response_model=LoginResponse)
async def auth_me(request: Request) -> LoginResponse:
    user = await asyncio.to_thread(current_session_user, request)
    return LoginResponse(
        user_id=user["id"],
        username=user["username"],
        role=user["role"],
        current_stage=user["current_stage"],
        message="登录状态有效",
    )


@router.post("/auth/logout")
async def auth_logout(request: Request, response: Response) -> dict[str, str]:
    await asyncio.to_thread(revoke_auth_session_sync, request.cookies.get(SESSION_COOKIE_NAME))
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"message": "已退出登录"}
