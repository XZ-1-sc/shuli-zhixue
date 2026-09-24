import asyncio
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...security import require_student_user, require_teacher
from ...services.solution_service import chain_recovery_sync, ensure_solution_steps_sync, ensure_teacher_solution_steps_sync, save_ai_evidence_sync, save_solution_steps_sync
from ..schemas import AISelfCheckResultRequest, ChainRecoveryRequest


class SolutionStepsUpdate(BaseModel):
    steps: list[dict[str, Any]] = Field(min_length=1, max_length=20)


router = APIRouter(prefix="/api", tags=["solution-engine"])


@router.get("/questions/{question_id}/solution-steps")
async def solution_steps(question_id: int, current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(ensure_solution_steps_sync, question_id, int(current["id"]))


@router.get("/teacher/questions/{question_id}/solution-steps")
async def teacher_solution_steps(question_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(ensure_teacher_solution_steps_sync, int(current["id"]), question_id)


@router.put("/teacher/questions/{question_id}/solution-steps")
async def update_solution_steps(question_id: int, payload: SolutionStepsUpdate, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(save_solution_steps_sync, int(current["id"]), question_id, payload.steps)


@router.post("/practice/ai-selfcheck/submit")
async def submit_ai_selfcheck(payload: AISelfCheckResultRequest, current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(save_ai_evidence_sync, int(current["id"]), payload)


@router.post("/recommend/chain-recovery")
async def chain_recovery(payload: ChainRecoveryRequest, current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(chain_recovery_sync, int(current["id"]), payload.record_id)
