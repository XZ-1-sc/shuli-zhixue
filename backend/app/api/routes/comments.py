import asyncio
from typing import Any

from fastapi import APIRouter, Depends, status

from ...database.repositories.comments import (
    _best_comment_sync,
    _create_question_comment_sync,
    _hide_comment_sync,
    _question_comments_sync,
    _upvote_comment_sync,
)
from ...security import current_session_user
from ..schemas import QuestionCommentRequest


router = APIRouter(prefix="/api", tags=["question-comments"])


@router.get("/questions/{question_id}/comments")
async def question_comments(question_id: int, current: dict[str, Any] = Depends(current_session_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_question_comments_sync, current, question_id)


@router.post("/questions/{question_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_question_comment(question_id: int, payload: QuestionCommentRequest, current: dict[str, Any] = Depends(current_session_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_create_question_comment_sync, current, question_id, payload)


@router.post("/comments/{comment_id}/upvote")
async def upvote_comment(comment_id: int, current: dict[str, Any] = Depends(current_session_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_upvote_comment_sync, current, comment_id)


@router.put("/comments/{comment_id}/best")
async def best_comment(comment_id: int, current: dict[str, Any] = Depends(current_session_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_best_comment_sync, current, comment_id)


@router.put("/comments/{comment_id}/hide")
async def hide_comment(comment_id: int, current: dict[str, Any] = Depends(current_session_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_hide_comment_sync, current, comment_id)
