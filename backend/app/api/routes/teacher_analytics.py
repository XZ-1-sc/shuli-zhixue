import asyncio
from typing import Any

from fastapi import APIRouter, Depends

from ...security import require_teacher
from ...services.teacher_analytics_service import assignment_analytics_sync, class_analytics_sync


router = APIRouter(prefix="/api/teacher", tags=["teacher-analytics"])


@router.get("/assignments/{assignment_id}/analytics")
async def assignment_analytics(
    assignment_id: int, current: dict[str, Any] = Depends(require_teacher)
) -> dict[str, Any]:
    return await asyncio.to_thread(assignment_analytics_sync, int(current["id"]), assignment_id)


@router.get("/classes/{class_id}/analytics")
async def class_analytics(class_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(class_analytics_sync, int(current["id"]), class_id)
