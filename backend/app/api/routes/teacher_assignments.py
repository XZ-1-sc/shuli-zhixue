import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from ...database.repositories.teacher_assignments import (
    _archive_assignment_sync,
    _assignment_detail_sync,
    _assignments_sync,
    _close_assignment_sync,
    _create_assignment_sync,
    _publish_assignment_sync,
    _update_assignment_sync,
)
from ...security import require_teacher
from ..teacher_schemas import AssignmentWriteRequest


router = APIRouter(prefix="/api/teacher", tags=["teacher-workflow"])


@router.get("/assignments")
async def assignments(
    class_id: int | None = Query(default=None, ge=1),
    assignment_status: str | None = Query(default=None, alias="status", max_length=32),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(_assignments_sync, int(current["id"]), class_id, assignment_status)


@router.post("/assignments", status_code=status.HTTP_201_CREATED)
async def create_assignment(payload: AssignmentWriteRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_create_assignment_sync, int(current["id"]), payload)


@router.get("/assignments/{assignment_id}")
async def assignment_detail(assignment_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_assignment_detail_sync, int(current["id"]), assignment_id)


@router.put("/assignments/{assignment_id}")
async def update_assignment(assignment_id: int, payload: AssignmentWriteRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_update_assignment_sync, int(current["id"]), assignment_id, payload)


@router.post("/assignments/{assignment_id}/publish")
async def publish_assignment(assignment_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_publish_assignment_sync, int(current["id"]), assignment_id)


@router.post("/assignments/{assignment_id}/close")
async def close_assignment(assignment_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_close_assignment_sync, int(current["id"]), assignment_id)


@router.post("/assignments/{assignment_id}/archive")
async def archive_assignment(assignment_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, bool]:
    return await asyncio.to_thread(_archive_assignment_sync, int(current["id"]), assignment_id)
