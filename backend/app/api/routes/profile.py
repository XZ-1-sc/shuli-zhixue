import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from ...database.repositories.profile import (
    _ability_map_sync,
    _achievements_sync,
    _create_note_sync,
    _delete_note_sync,
    _messages_sync,
    _notes_sync,
    _profile_summary_sync,
    _resources_sync,
    _update_note_sync,
)
from ...security import current_session_user, require_student_user, require_teacher
from ...services.notification_service import (
    _daily_greeting_sync,
    _mark_notification_read_sync,
    _notification_summary_sync,
    _preferences_sync,
    _reply_ticket_sync,
    _save_preferences_sync,
    _teacher_tickets_sync,
)
from ..schemas import NoteRequest, NoteUpdateRequest, NotificationPreferenceRequest, TicketReplyRequest


router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/messages")
async def messages(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_messages_sync, int(current["id"]), ensure_weekly=True)


@router.get("/notifications/summary")
async def notification_summary(current: dict[str, Any] = Depends(current_session_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_notification_summary_sync, int(current["id"]))


@router.post("/notifications/greeting")
async def daily_greeting(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_daily_greeting_sync, int(current["id"]))


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    return await asyncio.to_thread(_mark_notification_read_sync, int(current["id"]), notification_id)


@router.get("/preferences")
async def preferences(current: dict[str, Any] = Depends(current_session_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_preferences_sync, int(current["id"]))


@router.put("/preferences")
async def save_preferences(
    payload: NotificationPreferenceRequest,
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    return await asyncio.to_thread(_save_preferences_sync, int(current["id"]), payload.notify_xiaoluo)


@router.get("/teacher/tickets")
async def teacher_tickets(current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_teacher_tickets_sync, int(current["id"]))


@router.post("/teacher/tickets/{ticket_id}/reply")
async def reply_teacher_ticket(
    ticket_id: int,
    payload: TicketReplyRequest,
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(_reply_ticket_sync, int(current["id"]), ticket_id, payload.content)


@router.get("/profile/summary")
async def profile_summary(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_profile_summary_sync, int(current["id"]))


@router.get("/profile/ability-map")
async def ability_map(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_ability_map_sync, int(current["id"]))


@router.get("/achievements")
async def achievements(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_achievements_sync, int(current["id"]))


@router.get("/resources")
async def resources(
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    return await asyncio.to_thread(_resources_sync, stage, course)


@router.get("/notes")
async def notes(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_notes_sync, int(current["id"]))


@router.post("/notes", status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteRequest,
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    return await asyncio.to_thread(_create_note_sync, int(current["id"]), payload)


@router.put("/notes/{note_id}")
async def update_note(
    note_id: int,
    payload: NoteUpdateRequest,
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    return await asyncio.to_thread(_update_note_sync, note_id, int(current["id"]), payload)


@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: int,
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    return await asyncio.to_thread(_delete_note_sync, note_id, int(current["id"]))
