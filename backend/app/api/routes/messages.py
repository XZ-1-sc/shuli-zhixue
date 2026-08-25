import asyncio
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query

from ...security import current_session_user
from ...services.message_service import (
    contacts_sync,
    conversation_messages_sync,
    conversations_sync,
    mark_conversation_read_sync,
    send_conversation_message_sync,
    start_conversation_sync,
    unread_count_sync,
)
from ..schemas import MessageSendRequest, MessageStartRequest


router = APIRouter(prefix="/api/messages", tags=["messages"])


@router.get("/contacts")
async def contacts(search: str | None = Query(default=None, max_length=64), current: dict[str, Any] = Depends(current_session_user)) -> dict[str, Any]:
    return await asyncio.to_thread(contacts_sync, int(current["id"]), str(current["role"]), search)


@router.get("/conversations")
async def conversations(relation: Literal["teacher_student", "student_student"] | None = None, current: dict[str, Any] = Depends(current_session_user)) -> dict[str, Any]:
    return await asyncio.to_thread(conversations_sync, int(current["id"]), str(current["role"]), relation)


@router.post("/conversations/start")
async def start_conversation(payload: MessageStartRequest, current: dict[str, Any] = Depends(current_session_user)) -> dict[str, Any]:
    return await asyncio.to_thread(start_conversation_sync, int(current["id"]), str(current["role"]), payload.target_user_id, payload.relation)


@router.get("/conversations/{conversation_id}")
async def conversation_messages(conversation_id: int, limit: int = Query(default=50, ge=1, le=50), before_id: int | None = Query(default=None, ge=1), current: dict[str, Any] = Depends(current_session_user)) -> dict[str, Any]:
    return await asyncio.to_thread(conversation_messages_sync, int(current["id"]), str(current["role"]), conversation_id, limit, before_id)


@router.post("/conversations/{conversation_id}")
async def send_conversation_message(conversation_id: int, payload: MessageSendRequest, current: dict[str, Any] = Depends(current_session_user)) -> dict[str, Any]:
    return await asyncio.to_thread(send_conversation_message_sync, int(current["id"]), str(current["role"]), conversation_id, payload)


@router.post("/conversations/{conversation_id}/read")
async def mark_conversation_read(conversation_id: int, current: dict[str, Any] = Depends(current_session_user)) -> dict[str, Any]:
    return await asyncio.to_thread(mark_conversation_read_sync, int(current["id"]), str(current["role"]), conversation_id)


@router.get("/unread-count")
async def message_unread_count(current: dict[str, Any] = Depends(current_session_user)) -> dict[str, int]:
    return await asyncio.to_thread(unread_count_sync, int(current["id"]), str(current["role"]))
