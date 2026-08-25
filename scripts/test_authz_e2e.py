import os
import secrets
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import text

from backend.app.database.repositories.chat import _chat_rate_events, _enforce_chat_rate_limit
from backend.app.database.session import SessionLocal, settings


BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8080").rstrip("/")
PASSWORD = "AuthzTest!2026"


def expect_status(response: httpx.Response, expected: int | set[int]) -> None:
    allowed = {expected} if isinstance(expected, int) else expected
    if response.status_code not in allowed:
        raise AssertionError(f"{response.request.method} {response.request.url}: {response.status_code} {response.text[:300]}")


def register(client: httpx.Client, username: str, role: str = "student") -> dict[str, Any]:
    payload: dict[str, Any] = {"username": username, "password": PASSWORD, "role": role, "remember": False}
    if role == "teacher":
        payload["teacher_invite_code"] = settings.teacher_invite_code
    response = client.post("/api/register", json=payload)
    expect_status(response, 200)
    return response.json()


def assert_session_identity(client: httpx.Client, path: str, current_user_id: int, other_user_id: int) -> None:
    expect_status(client.get(path, params={"user_id": other_user_id}), 403)
    response = client.get(path)
    expect_status(response, 200)
    payload = response.json()
    returned_user_id = payload.get("user_id")
    if returned_user_id is not None and int(returned_user_id) != current_user_id:
        raise AssertionError(f"{path} 返回了非当前会话账号的数据：{returned_user_id}")


def cleanup_users(user_ids: list[int]) -> None:
    if not user_ids:
        return
    placeholders = ", ".join(f":user_{index}" for index in range(len(user_ids)))
    params = {f"user_{index}": user_id for index, user_id in enumerate(user_ids)}
    with SessionLocal() as db:
        db.execute(
            text(
                f"DELETE calls FROM llm_call_log AS calls "
                f"JOIN negotiation_log AS logs ON logs.conversation_id=calls.conversation_id "
                f"WHERE logs.user_id IN ({placeholders})"
            ),
            params,
        )
        db.execute(text(f"DELETE FROM users WHERE id IN ({placeholders})"), params)
        db.commit()


def create_chat_message(user_id: int, session_id: str) -> None:
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO chat_messages (session_id, user_id, role, content)
                VALUES (:session_id, :user_id, 'user', :content)
                """
            ),
            {"session_id": session_id, "user_id": user_id, "content": "会话归属隔离测试"},
        )
        db.commit()


def assert_rate_limit(user_id: int) -> None:
    _chat_rate_events.pop(user_id, None)
    for _ in range(10):
        _enforce_chat_rate_limit(user_id)
    try:
        _enforce_chat_rate_limit(user_id)
    except HTTPException as exc:
        if exc.status_code != 429:
            raise
    else:
        raise AssertionError("聊天限流未在第 11 次请求时返回 429。")
    finally:
        _chat_rate_events.pop(user_id, None)


def main() -> None:
    suffix = secrets.token_hex(6)
    created_user_ids: list[int] = []
    try:
        with httpx.Client(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as student_a, httpx.Client(
            base_url=BASE_URL, timeout=30.0, follow_redirects=True
        ) as student_b, httpx.Client(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as teacher:
            user_a = register(student_a, f"authz_a_{suffix}")
            user_b = register(student_b, f"authz_b_{suffix}")
            teacher_user = register(teacher, f"authz_t_{suffix}", "teacher")
            created_user_ids.extend([int(user_a["user_id"]), int(user_b["user_id"]), int(teacher_user["user_id"])])

            with httpx.Client(base_url=BASE_URL, timeout=15.0) as cookie_probe:
                secure_login = cookie_probe.post(
                    "/api/login",
                    json={"username": user_a["username"], "password": PASSWORD, "role": "student", "remember": False},
                    headers={"X-Forwarded-Proto": "https"},
                )
                expect_status(secure_login, 200)
                if "secure" not in secure_login.headers.get("set-cookie", "").lower():
                    raise AssertionError("HTTPS 转发请求未设置 Secure 会话 Cookie。")

            for path in ("/api/diagnose", "/api/notes", "/api/messages", "/api/chat/history"):
                assert_session_identity(student_a, path, int(user_a["user_id"]), int(user_b["user_id"]))

            foreign_session_id = "00000000-0000-4000-8000-000000000002"
            create_chat_message(int(user_b["user_id"]), foreign_session_id)
            expect_status(student_a.get("/api/chat/history", params={"session_id": foreign_session_id}), 403)

            for path in ("/api/diagnose", "/api/notes", "/api/messages"):
                response = teacher.get(path)
                expect_status(response, 403)
            expect_status(teacher.get("/api/chat/history"), 200)
            expect_status(teacher.get("/api/chat/history", params={"user_id": int(user_a["user_id"])}), 403)

        with httpx.Client(base_url=BASE_URL, timeout=15.0) as anonymous:
            for path in ("/api/diagnose", "/api/practice/random", "/api/resources", "/api/chat/history"):
                response = anonymous.get(path)
                expect_status(response, 401)

        assert_rate_limit(9_000_000)
    finally:
        cleanup_users(created_user_ids)

    print("AUTHZ_E2E_OK: 会话身份隔离、匿名访问和教师越权矩阵全部通过。")


if __name__ == "__main__":
    main()
