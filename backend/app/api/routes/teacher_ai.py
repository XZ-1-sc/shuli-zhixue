import asyncio
from typing import Any

from fastapi import APIRouter, Depends

from ...security import require_teacher
from ...services.teacher_ai_service import (
    generate_assignment_suggestion_sync,
    generate_class_insight_sync,
    generate_grade_comments_sync,
    generate_grade_comment_sync,
    generate_teacher_questions_sync,
)
from ...services.assignment_report_service import generate_assignment_report_sync
from ..teacher_schemas import AssignmentReportAIRequest, AssignmentSuggestionAIRequest, ClassInsightAIRequest, GradeCommentAIRequest, TeacherQuestionAIRequest


router = APIRouter(prefix="/api/teacher/ai", tags=["teacher-ai"])


@router.post("/generate-question")
async def generate_question(payload: TeacherQuestionAIRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(generate_teacher_questions_sync, int(current["id"]), payload)


@router.post("/grade-comment")
async def grade_comment(payload: GradeCommentAIRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    if payload.record_ids:
        return await asyncio.to_thread(generate_grade_comments_sync, int(current["id"]), payload)
    return await asyncio.to_thread(generate_grade_comment_sync, int(current["id"]), payload)


@router.post("/class-insight")
async def class_insight(payload: ClassInsightAIRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(generate_class_insight_sync, int(current["id"]), payload)


@router.post("/assignment-suggestion")
async def assignment_suggestion(payload: AssignmentSuggestionAIRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(generate_assignment_suggestion_sync, int(current["id"]), payload)


@router.post("/assignment-report")
async def assignment_report(
    payload: AssignmentReportAIRequest, current: dict[str, Any] = Depends(require_teacher)
) -> dict[str, Any]:
    return await asyncio.to_thread(generate_assignment_report_sync, int(current["id"]), payload.assignment_id)
