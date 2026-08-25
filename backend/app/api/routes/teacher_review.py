import asyncio
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query

from ...database.repositories.teacher_assignments import _grade_sync, _review_queue_sync
from ...security import require_teacher
from ...services.teacher_ai_service import review_flags_sync
from ..teacher_schemas import ReviewRequest


router = APIRouter(prefix="/api/teacher", tags=["teacher-workflow"])


@router.get("/review/flag")
async def review_flags(current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(review_flags_sync, int(current["id"]))


@router.get("/review-queue")
async def review_queue(
    assignment_id: int | None = Query(default=None, ge=1),
    review_status: Literal["pending", "graded"] = "pending",
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(_review_queue_sync, int(current["id"]), assignment_id, review_status)


@router.post("/submissions/{record_id}/grade")
async def grade_submission(record_id: int, payload: ReviewRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_grade_sync, int(current["id"]), record_id, payload)
