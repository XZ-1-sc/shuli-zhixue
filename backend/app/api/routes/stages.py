import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query

from ...database.repositories.stages import (
    _courses_sync,
    _knowledge_graph_sync,
    _question_type_counts_sync,
    _stages_sync,
)
from ...security import require_student_user


router = APIRouter(prefix="/api", tags=["math-content"])


@router.get("/stages")
async def stages() -> dict[str, Any]:
    return {"stages": await asyncio.to_thread(_stages_sync)}


@router.get("/courses")
async def courses(stage: str | None = Query(default=None, max_length=16)) -> dict[str, Any]:
    return {"courses": await asyncio.to_thread(_courses_sync, stage)}


@router.get("/knowledge-graph")
async def knowledge_graph(
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    return await asyncio.to_thread(_knowledge_graph_sync, stage, course, int(current["id"]))


@router.get("/question-types")
async def question_types() -> dict[str, Any]:
    return await asyncio.to_thread(_question_type_counts_sync)
