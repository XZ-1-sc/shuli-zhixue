import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query

from ...database.repositories.teacher_students import _student_detail_sync, _student_list_sync
from ...security import require_teacher


router = APIRouter(prefix="/api/teacher", tags=["teacher-workflow"])


@router.get("/students")
async def students(
    class_id: int | None = Query(default=None, ge=1),
    search: str | None = Query(default=None, max_length=64),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(_student_list_sync, int(current["id"]), class_id, search)


@router.get("/students/{student_id}")
async def student_detail(student_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_student_detail_sync, int(current["id"]), student_id)


@router.get("/students/{student_id}/preview")
async def student_preview(student_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    data = await asyncio.to_thread(_student_detail_sync, int(current["id"]), student_id)
    return data | {"read_only": True, "notice": "当前为教师只读预览，不会修改学生数据。"}
