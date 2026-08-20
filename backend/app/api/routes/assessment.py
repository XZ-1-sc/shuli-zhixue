import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...database.repositories.assessment import _assessment_after_submit_sync, _start_assessment_sync
from ...security import require_student_user
from ..schemas import AssessmentStartRequest


router = APIRouter(prefix="/api", tags=["assessment"])


@router.post("/assessment/start")
async def start_assessment(
    payload: AssessmentStartRequest,
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    return await asyncio.to_thread(_start_assessment_sync, int(current["id"]), payload)


@router.get("/assessment/{task_id}/report")
async def assessment_report(
    task_id: str,
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    state = await asyncio.to_thread(_assessment_after_submit_sync, int(current["id"]), task_id)
    if not state.get("assessment_complete"):
        raise HTTPException(status_code=409, detail="首测尚未完成。")
    return state["assessment_report"]
