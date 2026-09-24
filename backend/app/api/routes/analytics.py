import asyncio
from typing import Any

from fastapi import APIRouter, Depends

from ...security import require_student_user, require_teacher
from ...services.analytics_service import (
    assignment_question_stats_sync,
    class_dashboard_sync,
    common_issues_sync,
    profile_analytics_sync,
    question_insight_sync,
)


router = APIRouter(prefix="/api", tags=["teaching-analytics"])


@router.get("/profile/analytics")
async def profile_analytics(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(profile_analytics_sync, int(current["id"]))


@router.get("/teacher/classes/{class_id}/dashboard")
async def class_dashboard(class_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(class_dashboard_sync, int(current["id"]), class_id)


@router.get("/teacher/assignments/{assignment_id}/question-stats")
async def assignment_question_stats(assignment_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(assignment_question_stats_sync, int(current["id"]), assignment_id)


@router.get("/teacher/questions/{question_id}/insight")
async def question_insight(question_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(question_insight_sync, int(current["id"]), question_id)


@router.get("/teacher/classes/{class_id}/common-issues")
async def common_issues(class_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(common_issues_sync, int(current["id"]), class_id)
