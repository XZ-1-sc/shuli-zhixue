import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from ...database.repositories.chat import (
    _assert_chat_session_owner_sync,
    _chat_history_sync,
    _chat_sessions_sync,
    _enforce_chat_rate_limit,
    _normalize_session_id,
)
from ...security import current_session_user
from ...services.chat_service import chat_event_stream
from ..schemas import ChatRequest


router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(
    request: ChatRequest,
    current: dict[str, Any] = Depends(current_session_user),
) -> StreamingResponse:
    user_id = int(current["id"])
    role = str(current["role"])
    if role not in {"student", "teacher", "admin"}:
        raise HTTPException(status_code=403, detail="当前账号不能使用小逻。")
    _enforce_chat_rate_limit(user_id)
    return StreamingResponse(
        chat_event_stream(user_id, role, request.message, request.session_id, request.context),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/history")
async def chat_history(
    session_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    user_id = int(current["id"])
    normalized_session = _normalize_session_id(session_id) if session_id else None
    if normalized_session:
        await asyncio.to_thread(_assert_chat_session_owner_sync, user_id, normalized_session)
    messages = await asyncio.to_thread(_chat_history_sync, user_id, normalized_session, limit, offset)
    return {"user_id": user_id, "session_id": normalized_session, "messages": messages}


@router.get("/chat/sessions")
async def chat_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    user_id = int(current["id"])
    sessions = await asyncio.to_thread(_chat_sessions_sync, user_id, limit)
    return {"user_id": user_id, "sessions": sessions}
