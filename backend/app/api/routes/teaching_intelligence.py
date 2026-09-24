import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from ...security import require_teacher
from ...services.paper_service import (
    assignment_similarity_sync,
    create_assignment_draft_sync,
    generate_lecture_draft_sync,
    parse_paper_intent_sync,
    review_assignment_sync,
)
from ...services.risk_service import help_signals_sync, risks_sync, scan_teacher_risks_sync, update_help_signal_sync, update_risk_sync
from ...services.teacher_experience_service import archive_experience_sync, create_experience_sync, experiences_sync, preference_sync, save_preference_sync
from ...services.teaching_intelligence_service import artifacts_sync, confirm_artifact_sync, decide_pregrade_sync, generate_artifact_sync, generate_pregrade_sync
from ..teacher_schemas import (
    ArtifactGenerateRequest,
    AssignmentReportAIRequest,
    HelpSignalStatusRequest,
    PaperIntentRequest,
    PaperTextRequest,
    PregradeDecisionRequest,
    RiskStatusRequest,
    TeacherExperienceRequest,
    TeacherPreferenceRequest,
)


router = APIRouter(prefix="/api/teacher", tags=["teaching-intelligence"])


@router.post("/ai/assignment-intent")
async def paper_intent(payload: PaperTextRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(parse_paper_intent_sync, int(current["id"]), payload)


@router.post("/ai/assignment-draft", status_code=status.HTTP_201_CREATED)
async def assignment_draft(payload: PaperIntentRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(create_assignment_draft_sync, int(current["id"]), payload)


@router.post("/ai/assignment-review")
async def assignment_review(payload: AssignmentReportAIRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(review_assignment_sync, int(current["id"]), payload.assignment_id)


@router.post("/ai/assignment-commentary")
async def assignment_commentary(payload: AssignmentReportAIRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(generate_lecture_draft_sync, int(current["id"]), payload.assignment_id)


@router.get("/assignments/{assignment_id}/similarity-hints")
async def similarity_hints(assignment_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(assignment_similarity_sync, int(current["id"]), assignment_id)


@router.get("/experiences")
async def experiences(
    knowledge_tag: str | None = Query(default=None, max_length=160),
    question_id: int | None = Query(default=None, ge=1),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(experiences_sync, int(current["id"]), knowledge_tag, question_id)


@router.post("/experiences", status_code=status.HTTP_201_CREATED)
async def create_experience(payload: TeacherExperienceRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(create_experience_sync, int(current["id"]), payload)


@router.delete("/experiences/{experience_id}")
async def archive_experience(experience_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(archive_experience_sync, int(current["id"]), experience_id)


@router.get("/ai/preferences")
async def teacher_ai_preferences(current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(preference_sync, int(current["id"]))


@router.put("/ai/preferences")
async def update_teacher_ai_preferences(payload: TeacherPreferenceRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(save_preference_sync, int(current["id"]), payload)


@router.post("/intelligence/artifacts", status_code=status.HTTP_201_CREATED)
async def generate_artifact(payload: ArtifactGenerateRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(generate_artifact_sync, int(current["id"]), payload)


@router.get("/intelligence/artifacts")
async def teaching_artifacts(
    artifact_type: str | None = Query(default=None, max_length=64),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(artifacts_sync, int(current["id"]), artifact_type)


@router.post("/intelligence/artifacts/{artifact_id}/confirm")
async def confirm_artifact(artifact_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(confirm_artifact_sync, int(current["id"]), artifact_id)


@router.post("/review/{record_id}/ai-pregrade", status_code=status.HTTP_201_CREATED)
async def ai_pregrade(record_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(generate_pregrade_sync, int(current["id"]), record_id)


@router.post("/review/ai-pregrades/{pregrade_id}/decision")
async def decide_pregrade(pregrade_id: int, payload: PregradeDecisionRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(decide_pregrade_sync, int(current["id"]), pregrade_id, payload)


@router.post("/intelligence/risks/scan")
async def scan_risks(current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(scan_teacher_risks_sync, int(current["id"]))


@router.get("/intelligence/risks")
async def teaching_risks(
    risk_status: str = Query(default="open", alias="status", pattern="^(open|acknowledged|resolved)$"),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(risks_sync, int(current["id"]), risk_status)


@router.put("/intelligence/risks/{risk_id}")
async def update_risk(risk_id: int, payload: RiskStatusRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(update_risk_sync, int(current["id"]), risk_id, payload.status)


@router.get("/intelligence/help-signals")
async def help_signals(current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(help_signals_sync, int(current["id"]))


@router.put("/intelligence/help-signals/{signal_id}")
async def update_help_signal(signal_id: int, payload: HelpSignalStatusRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(update_help_signal_sync, int(current["id"]), signal_id, payload.status)
