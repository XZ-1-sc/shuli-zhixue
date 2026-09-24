import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query

from ...database.repositories.stages import (
    _courses_sync,
    _knowledge_graph_sync,
    _question_type_counts_sync,
    _stages_sync,
)
from ...database.repositories.curriculum import (
    _all_courses_sync,
    _knowledge_graph_v2_sync,
    _save_user_courses_sync,
    _user_courses_sync,
)
from ...security import require_student_user
from ..schemas import UserCoursesRequest


router = APIRouter(prefix="/api", tags=["math-content"])


@router.get("/stages")
async def stages() -> dict[str, Any]:
    return {"stages": await asyncio.to_thread(_stages_sync)}


@router.get("/courses")
async def courses(stage: str | None = Query(default=None, max_length=16)) -> dict[str, Any]:
    # ``stage`` remains accepted for compatibility with old bookmarks, but no
    # longer limits the course catalogue.
    return {"courses": await asyncio.to_thread(_all_courses_sync)}


@router.get("/user-courses")
async def user_courses(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_user_courses_sync, int(current["id"]))


@router.put("/user-courses")
async def save_user_courses(payload: UserCoursesRequest, current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_save_user_courses_sync, int(current["id"]), payload.courses, payload.primary_course)


@router.get("/knowledge-graph")
async def knowledge_graph(
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    return await asyncio.to_thread(_knowledge_graph_sync, stage, course, int(current["id"]))


@router.get("/knowledge-graph-v2")
async def knowledge_graph_v2(
    course: str | None = Query(default=None, max_length=128),
    depth: int = Query(default=3, ge=1, le=3),
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    return await asyncio.to_thread(_knowledge_graph_v2_sync, int(current["id"]), course, depth)


@router.get("/question-types")
async def question_types() -> dict[str, Any]:
    return await asyncio.to_thread(_question_type_counts_sync)
