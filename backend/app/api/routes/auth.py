import asyncio

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from ...database.session import SessionLocal
from ...utils.password import hash_password, verify_password


router = APIRouter(prefix="/api", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginResponse(BaseModel):
    user_id: int
    username: str
    message: str


def _raise_database_error(exc: SQLAlchemyError) -> None:
    detail = "数据库暂时不可用，请检查 MySQL 和 DATABASE_URL。"
    if isinstance(exc, OperationalError) and "1045" in str(exc):
        detail = "数据库账号或密码不正确，请检查 backend/.env 里的 DATABASE_URL。"

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=detail,
    ) from exc


def _login_sync(payload: LoginRequest) -> LoginResponse:
    username = payload.username.strip()
    query = text(
        """
        SELECT id, username, password_hash
        FROM users
        WHERE username = :username
        LIMIT 1
        """
    )

    try:
        with SessionLocal() as db:
            row = db.execute(query, {"username": username}).mappings().first()
    except SQLAlchemyError as exc:
        _raise_database_error(exc)

    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误。",
        )

    return LoginResponse(
        user_id=int(row["id"]),
        username=str(row["username"]),
        message="登录成功",
    )


def _register_sync(payload: RegisterRequest) -> LoginResponse:
    username = payload.username.strip()
    if len(username) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="用户名至少需要 2 个字符。",
        )

    password_hash = hash_password(payload.password)
    insert_query = text(
        """
        INSERT INTO users (username, password_hash)
        VALUES (:username, :password_hash)
        """
    )

    try:
        with SessionLocal() as db:
            result = db.execute(
                insert_query,
                {
                    "username": username,
                    "password_hash": password_hash,
                },
            )
            db.commit()
            user_id = int(result.lastrowid)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在，请换一个用户名。",
        ) from exc
    except SQLAlchemyError as exc:
        _raise_database_error(exc)

    return LoginResponse(
        user_id=user_id,
        username=username,
        message="注册成功",
    )


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    return await asyncio.to_thread(_login_sync, payload)


@router.post("/register", response_model=LoginResponse)
async def register(payload: RegisterRequest) -> LoginResponse:
    return await asyncio.to_thread(_register_sync, payload)
