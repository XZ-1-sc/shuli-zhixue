import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ...security import current_session_user, require_student, require_teacher
from ...services.teacher_message_service import (
    message_thread_sync,
    send_message_sync,
    student_conversations_sync,
    teacher_conversations_sync,
    unread_count_sync,
)


router = APIRouter(tags=["teacher-messages"])


class MessageWriteRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


@router.get("/api/teacher/messages")
async def teacher_messages(current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(teacher_conversations_sync, int(current["id"]))


@router.get("/api/teacher/messages/thread")
async def teacher_message_thread(
    student_id: int = Query(ge=1), current: dict[str, Any] = Depends(require_teacher)
) -> dict[str, Any]:
    return await asyncio.to_thread(message_thread_sync, int(current["id"]), student_id, "teacher")


@router.post("/api/teacher/messages/thread")
async def send_teacher_message(
    payload: MessageWriteRequest,
    student_id: int = Query(ge=1),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(send_message_sync, int(current["id"]), student_id, "teacher", payload.content)


@router.get("/api/messages/teachers")
async def student_teachers(current: dict[str, Any] = Depends(require_student)) -> dict[str, Any]:
    return await asyncio.to_thread(student_conversations_sync, int(current["id"]))


@router.get("/api/messages/thread")
async def student_message_thread(
    teacher_id: int = Query(ge=1), current: dict[str, Any] = Depends(require_student)
) -> dict[str, Any]:
    return await asyncio.to_thread(message_thread_sync, int(current["id"]), teacher_id, "student")


@router.post("/api/messages/thread")
async def send_student_message(
    payload: MessageWriteRequest,
    teacher_id: int = Query(ge=1),
    current: dict[str, Any] = Depends(require_student),
) -> dict[str, Any]:
    return await asyncio.to_thread(send_message_sync, int(current["id"]), teacher_id, "student", payload.content)


@router.get("/api/messages/unread-count")
async def message_unread_count(current: dict[str, Any] = Depends(current_session_user)) -> dict[str, int]:
    return await asyncio.to_thread(unread_count_sync, int(current["id"]), str(current["role"]))
