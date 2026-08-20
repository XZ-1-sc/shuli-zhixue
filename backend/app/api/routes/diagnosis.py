import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query

from ...database.repositories.diagnosis import (
    _diagnose_sync,
    _get_goal_sync,
    _recommend_sync,
    _save_goal_sync,
    _study_roadmap_sync,
    _wrong_questions_sync,
)
from ...security import require_student_user
from ..schemas import GoalRequest


router = APIRouter(prefix="/api", tags=["diagnosis"])


@router.get("/diagnose")
async def diagnose_user(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_diagnose_sync, int(current["id"]))


@router.get("/recommend")
async def recommend(
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=5, ge=1, le=20),
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    user_id = int(current["id"])
    tasks = await asyncio.to_thread(_recommend_sync, user_id, limit, stage, course)
    return {"user_id": user_id, "tasks": tasks, "questions": tasks}


@router.get("/study-roadmap")
async def study_roadmap(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_study_roadmap_sync, int(current["id"]))


@router.get("/review/wrong-questions")
async def wrong_questions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    return await asyncio.to_thread(_wrong_questions_sync, int(current["id"]), limit, offset)


@router.get("/user-goals")
async def get_user_goal(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_get_goal_sync, int(current["id"]))


@router.post("/user-goals")
async def save_user_goal(
    payload: GoalRequest,
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    return await asyncio.to_thread(_save_goal_sync, int(current["id"]), payload)
