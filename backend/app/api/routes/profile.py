import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from ...database.repositories.profile import (
    _achievements_sync,
    _create_note_sync,
    _delete_note_sync,
    _messages_sync,
    _notes_sync,
    _profile_summary_sync,
    _resources_sync,
    _update_note_sync,
)
from ...security import require_student_user
from ..schemas import NoteRequest, NoteUpdateRequest


router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/messages")
async def messages(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_messages_sync, int(current["id"]))


@router.get("/profile/summary")
async def profile_summary(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_profile_summary_sync, int(current["id"]))


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
