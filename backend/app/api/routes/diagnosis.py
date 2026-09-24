import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query

from ...database.repositories.diagnosis import (
    _diagnose_sync,
    _get_goal_sync,
    _learning_insights_sync,
    _recent_negotiation_sync,
    _recommend_sync,
    _review_analysis_sync,
    _save_goal_sync,
    _study_roadmap_sync,
    _wrong_questions_sync,
)
from ...orchestrator import run_pipeline
from ...security import require_student_user
from ...services.student_ai_service import generate_weekly_digest_sync
from ...services.ai_profile_service import persist_ai_profile_sync
from ..schemas import GoalRequest


router = APIRouter(prefix="/api", tags=["diagnosis"])


@router.get("/diagnose")
async def diagnose_user(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    user_id = int(current["id"])
    local_diagnosis = await asyncio.to_thread(_diagnose_sync, user_id)
    pipeline = await run_pipeline(user_id)
    local_points = {
        (str(item.get("stage")), str(item.get("course")), str(item.get("knowledge_tag"))): item
        for item in local_diagnosis.get("weak_points") or []
    }
    structured_points = []
    for point in pipeline["diagnosis"]["weak_points"]:
        local = local_points.get((point["stage"], point["course"], point["knowledge"]), {})
        structured_points.append(
            {
                **point,
                "knowledge_tag": point["knowledge"],
                "fine_tag": local.get("fine_tag") or point["knowledge"],
                "reason": point["reason_type"],
                "score": local.get("score"),
                "total": local.get("total", 0),
                "avg_time_seconds": local.get("avg_time_seconds", 0),
            }
        )
    result = {
        **local_diagnosis,
        "weak_points": structured_points,
        "confidence": pipeline["diagnosis"]["confidence"],
        "needs_first_test": pipeline["diagnosis"]["needs_first_test"],
        "strategy": pipeline["strategy"],
        "recommended_question_ids": pipeline["recommended_question_ids"],
        "negotiation": pipeline["negotiation"],
    }
    profile = await asyncio.to_thread(persist_ai_profile_sync, user_id, result)
    result["trend"] = profile["trend"]
    return result


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


@router.get("/review/analysis")
async def review_analysis(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_review_analysis_sync, int(current["id"]))


@router.post("/review/weekly-digest")
async def weekly_digest(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(generate_weekly_digest_sync, int(current["id"]))


@router.get("/learning-insights")
async def learning_insights(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_learning_insights_sync, int(current["id"]))


@router.get("/negotiation/recent")
async def recent_negotiation(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_recent_negotiation_sync, int(current["id"]))


@router.get("/user-goals")
async def get_user_goal(current: dict[str, Any] = Depends(require_student_user)) -> dict[str, Any]:
    return await asyncio.to_thread(_get_goal_sync, int(current["id"]))


@router.post("/user-goals")
async def save_user_goal(
    payload: GoalRequest,
    current: dict[str, Any] = Depends(require_student_user),
) -> dict[str, Any]:
    return await asyncio.to_thread(_save_goal_sync, int(current["id"]), payload)
