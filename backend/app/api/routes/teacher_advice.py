import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ...security import require_teacher
from ...services.advice_service import (
    advice_drafts_sync,
    batch_send_advice_drafts_sync,
    generate_advice_drafts_sync,
    send_advice_draft_sync,
    update_advice_draft_sync,
)


router = APIRouter(prefix="/api/teacher/advice", tags=["teacher-advice"])


class AdviceGenerateRequest(BaseModel):
    class_id: int = Field(ge=1)


class AdviceUpdateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class AdviceBatchSendRequest(BaseModel):
    draft_ids: list[int] = Field(min_length=1, max_length=200)


@router.post("/generate")
async def generate_advice(
    payload: AdviceGenerateRequest, current: dict[str, Any] = Depends(require_teacher)
) -> dict[str, Any]:
    return await asyncio.to_thread(generate_advice_drafts_sync, int(current["id"]), payload.class_id)


@router.get("/drafts")
async def advice_drafts(
    class_id: int = Query(ge=1), current: dict[str, Any] = Depends(require_teacher)
) -> dict[str, Any]:
    return await asyncio.to_thread(advice_drafts_sync, int(current["id"]), class_id)


@router.put("/drafts/{draft_id}")
async def update_advice_draft(
    draft_id: int, payload: AdviceUpdateRequest, current: dict[str, Any] = Depends(require_teacher)
) -> dict[str, Any]:
    return await asyncio.to_thread(update_advice_draft_sync, int(current["id"]), draft_id, payload.content)


@router.post("/drafts/{draft_id}/send")
async def send_advice_draft(
    draft_id: int, current: dict[str, Any] = Depends(require_teacher)
) -> dict[str, Any]:
    return await asyncio.to_thread(send_advice_draft_sync, int(current["id"]), draft_id)


@router.post("/drafts/batch-send")
async def batch_send_advice_drafts(
    payload: AdviceBatchSendRequest, current: dict[str, Any] = Depends(require_teacher)
) -> dict[str, Any]:
    return await asyncio.to_thread(batch_send_advice_drafts_sync, int(current["id"]), payload.draft_ids)
