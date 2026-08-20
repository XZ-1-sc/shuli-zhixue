import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from ...database.repositories.practice import _submit_answer_sync
from ...database.repositories.questions import _random_questions_sync
from ...security import require_student_user
from ..schemas import AnswerSubmissionRequest


router = APIRouter(prefix="/api", tags=["practice"])


@router.get("/practice/random")
async def random_practice(
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
    knowledge_tag: str | None = Query(default=None, max_length=160),
    question_type: str | None = Query(default=None, pattern="^(choice|blank|calculation|proof|comprehensive)$"),
    limit: int = Query(default=8, ge=1, le=50),
    mode: str = Query(default="custom", pattern="^(daily|chapter|mock|wrong_book|custom)$"),
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    questions = await asyncio.to_thread(
        _random_questions_sync,
        stage=stage,
        course=course,
        knowledge_tag=knowledge_tag,
        question_type=question_type,
        limit=limit,
    )
    return {
        "task_id": str(uuid.uuid4()),
        "mode": mode,
        "stage": stage,
        "course": course,
        "knowledge_tag": knowledge_tag,
        "question_type": question_type,
        "questions": questions,
    }


@router.get("/mock-exam")
async def mock_exam(
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=20, ge=5, le=50),
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    questions = await asyncio.to_thread(
        _random_questions_sync,
        stage=stage,
        course=course,
        knowledge_tag=None,
        question_type=None,
        limit=limit,
    )
    return {
        "task_id": str(uuid.uuid4()),
        "mode": "mock",
        "duration_minutes": max(30, round(limit * 2.5)),
        "questions": questions,
    }


@router.post("/practice/submit")
async def submit_answer(
    payload: AnswerSubmissionRequest,
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    return await asyncio.to_thread(_submit_answer_sync, int(current["id"]), payload)
