import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ...database.repositories.chat import (
    CHAT_SYSTEM_PROMPT,
    _assert_chat_session_owner_sync,
    _chat_history_sync,
    _chat_sessions_sync,
    _enforce_chat_rate_limit,
    _load_chat_context,
    _normalize_session_id,
    _save_chat_message,
)
from ...database.repositories.diagnosis import _diagnose_sync
from ...security import require_student_user
from ...utils.llm_client import call_llm
from ..schemas import ChatRequest


router = APIRouter(prefix="/api", tags=["chat"])


async def _chat_event_stream(user_id: int, request: ChatRequest):
    session_id = _normalize_session_id(request.session_id)
    await asyncio.to_thread(_assert_chat_session_owner_sync, user_id, session_id)
    previous_messages = await asyncio.to_thread(_load_chat_context, user_id, session_id)
    diagnosis = await asyncio.to_thread(_diagnose_sync, user_id)
    messages = [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"当前诊断摘要：{diagnosis.get('summary')}；薄弱点：{json.dumps(diagnosis.get('weak_points'), ensure_ascii=False)}",
        },
        *previous_messages,
        {"role": "user", "content": f"<student_input>{request.message}</student_input>"},
    ]
    reply = await asyncio.to_thread(call_llm, messages)
    if not reply:
        reply = "我建议先做一组极限与连续的基础题，再把错误按“概念混淆 / 计算失误 / 思路断点”三类标注。"

    await asyncio.to_thread(_save_chat_message, user_id, session_id, "user", request.message)
    await asyncio.to_thread(_save_chat_message, user_id, session_id, "assistant", reply)

    yield f"data: {json.dumps({'session_id': session_id}, ensure_ascii=False)}\n\n"
    for char in reply:
        yield f"data: {json.dumps({'delta': char}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.025)
    yield "data: [DONE]\n\n"


@router.post("/chat")
async def chat(
    request: ChatRequest,
    current: dict[str, Any] = Depends(require_student_user),
) -> StreamingResponse:
    user_id = int(current["id"])
    _enforce_chat_rate_limit(user_id)
    return StreamingResponse(
        _chat_event_stream(user_id, request),
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
    current: dict[str, Any] = Depends(require_student_user),
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
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    user_id = int(current["id"])
    sessions = await asyncio.to_thread(_chat_sessions_sync, user_id, limit)
    return {"user_id": user_id, "sessions": sessions}
