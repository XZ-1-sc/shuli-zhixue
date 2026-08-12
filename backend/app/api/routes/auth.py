import asyncio
import hmac
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from ...database.session import SessionLocal, settings
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


def _ensure_auth_schema_sync() -> None:
    with SessionLocal() as db:
        role_column_exists = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'users'
                  AND COLUMN_NAME = 'role'
                """
            )
        ).scalar_one()
        if not role_column_exists:
            db.execute(
                text(
                    """
                    ALTER TABLE users
                    ADD COLUMN role ENUM('student', 'teacher', 'admin')
                    NOT NULL DEFAULT 'student' AFTER email
                    """
                )
            )

        role_index_exists = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'users'
                  AND INDEX_NAME = 'idx_users_role_status'
                """
            )
        ).scalar_one()
        if not role_index_exists:
            db.execute(text("CREATE INDEX idx_users_role_status ON users (role, status)"))

        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS teacher_profiles (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  user_id BIGINT UNSIGNED NOT NULL,
                  display_name VARCHAR(64) NOT NULL,
                  organization VARCHAR(160) NULL,
                  verification_status ENUM('verified', 'disabled') NOT NULL DEFAULT 'verified',
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  UNIQUE KEY uk_teacher_profiles_user (user_id),
                  CONSTRAINT fk_teacher_profiles_user
                    FOREIGN KEY (user_id) REFERENCES users (id)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
                """
            )
        )
        db.commit()


def _login_sync(payload: LoginRequest) -> LoginResponse:
    _ensure_auth_schema_sync()
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
    _ensure_auth_schema_sync()
    username = payload.username.strip()
    if len(username) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="用户名至少需要 2 个字符。")

    if payload.role == "teacher":
        configured_code = settings.teacher_invite_code.strip()
        submitted_code = (payload.teacher_invite_code or "").strip()
        if not configured_code:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="教师注册暂未配置邀请码，请联系系统管理员。",
            )
        if not hmac.compare_digest(submitted_code, configured_code):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="教师邀请码无效。")

    insert_query = text(
        """
        INSERT INTO users (username, password_hash, nickname, role, current_stage)
        VALUES (:username, :password_hash, :nickname, :role, :current_stage)
        """
    )
    try:
        with SessionLocal() as db:
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
async def login(payload: LoginRequest, response: Response) -> LoginResponse:
    result = await asyncio.to_thread(_login_sync, payload)
    token, max_age = await asyncio.to_thread(create_auth_session_sync, result.user_id, payload.remember)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return result


@router.post("/register", response_model=LoginResponse)
async def register(payload: RegisterRequest, response: Response) -> LoginResponse:
    result = await asyncio.to_thread(_register_sync, payload)
    token, max_age = await asyncio.to_thread(create_auth_session_sync, result.user_id, payload.remember)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=False,
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
