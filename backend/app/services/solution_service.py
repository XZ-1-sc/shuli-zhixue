import json
import re
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..api.schemas import AISelfCheckResultRequest
from ..database.session import SessionLocal
from ..database.repositories.questions import _random_questions_sync
from ..utils.llm_client import call_llm_json


class SolutionStep(BaseModel):
    step_no: int = Field(ge=1, le=30)
    title: str = Field(min_length=1, max_length=120)
    explanation: str = Field(min_length=1, max_length=3000)
    formula: str = Field(default="", max_length=2000)
    caution: str = Field(default="", max_length=1000)


class SolutionStepsPayload(BaseModel):
    steps: list[SolutionStep] = Field(min_length=1, max_length=20)
    consistency_note: str = Field(default="", max_length=500)


def _fallback_steps(question: dict[str, Any]) -> SolutionStepsPayload:
    raw = question.get("key_steps") or []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = [item.strip() for item in raw.split("|") if item.strip()]
    steps = []
    for index, value in enumerate(raw[:12], start=1):
        text_value = str(value).strip()
        if text_value:
            steps.append(SolutionStep(step_no=index, title=f"第 {index} 步", explanation=text_value))
    if not steps:
        analysis = str(question.get("analysis_text") or question.get("standard_answer") or "依据定义和已知条件逐步推导。")
        parts = [part.strip() for part in re.split(r"[。；;\n]+", analysis) if part.strip()][:6]
        steps = [SolutionStep(step_no=index, title="分析与推导" if index == 1 else f"继续推导 {index}", explanation=value) for index, value in enumerate(parts or [analysis], start=1)]
    return SolutionStepsPayload(steps=steps, consistency_note="由现有标准解析结构化，最终结论以标准答案为准。")


def _question_for_solution(question_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT id,created_by,question_text,question_type,course,knowledge_tag,fine_tag,
                       standard_answer,analysis_text,key_steps,common_errors,solution_steps,
                       steps_source,steps_review_status
                FROM questions WHERE id=:id AND deleted_at IS NULL LIMIT 1
                """
            ),
            {"id": question_id},
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="题目不存在。")
    return dict(row)


def _experience_notes(user_id: int | None, question: dict[str, Any]) -> list[str]:
    params = {"question_id": question["id"], "knowledge_tag": question.get("knowledge_tag"), "user_id": user_id or 0}
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT te.experience_text
                FROM teacher_experiences te
                WHERE te.status='active'
                  AND (te.question_id=:question_id OR (te.question_id IS NULL AND te.knowledge_tag=:knowledge_tag))
                  AND (
                    te.teacher_id=(SELECT created_by FROM questions WHERE id=:question_id)
                    OR EXISTS(
                      SELECT 1 FROM class_members cm JOIN classes c ON c.id=cm.class_id
                      WHERE cm.student_id=:user_id AND cm.status='active' AND c.teacher_id=te.teacher_id AND c.status='active'
                    )
                  )
                GROUP BY te.experience_text
                ORDER BY MAX(te.updated_at) DESC LIMIT 8
                """
            ),
            params,
        ).scalars().all()
    return [str(item) for item in rows]


def ensure_solution_steps_sync(question_id: int, user_id: int | None = None) -> dict[str, Any]:
    question = _question_for_solution(question_id)
    existing = question.get("solution_steps")
    if isinstance(existing, str):
        try:
            existing = json.loads(existing)
        except json.JSONDecodeError:
            existing = None
    if isinstance(existing, list) and existing:
        return {"question_id": question_id, "steps": existing, "source": question["steps_source"], "review_status": question["steps_review_status"]}

    fallback = _fallback_steps(question)
    experiences = _experience_notes(user_id, question)
    generated, usage = call_llm_json(
        [
            {"role": "system", "content": "你是大学数学分步解题引擎。每步必须可执行，包含为什么、公式或推导以及必要的易错提示；最终结论必须与标准答案一致，禁止只给结论。"},
            {"role": "user", "content": json.dumps({"question": question, "teacher_experience": experiences}, ensure_ascii=False, default=str)[:24000]},
        ],
        SolutionStepsPayload,
        fallback=fallback,
        agent_name="solution_steps",
        temperature=0.15,
        max_tokens=2600,
    )
    steps = [item.model_dump() for item in generated.steps]
    source = "ai" if not str(usage.status).startswith("fallback") else "legacy"
    review_status = "pending" if source == "ai" else "verified"
    with SessionLocal() as db:
        db.execute(
            text("UPDATE questions SET solution_steps=:steps,steps_source=:source,steps_review_status=:review_status WHERE id=:id AND solution_steps IS NULL"),
            {"steps": json.dumps(steps, ensure_ascii=False), "source": source, "review_status": review_status, "id": question_id},
        )
        if experiences:
            db.execute(
                text("UPDATE teacher_experiences SET usage_count=usage_count+1 WHERE status='active' AND (question_id=:id OR knowledge_tag=:tag)"),
                {"id": question_id, "tag": question.get("knowledge_tag")},
            )
        db.commit()
    return {"question_id": question_id, "steps": steps, "source": source, "review_status": review_status, "usage": usage.model_dump()}


def ensure_teacher_solution_steps_sync(teacher_id: int, question_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        allowed = db.execute(
            text(
                """
                SELECT 1 FROM questions
                WHERE id=:id AND deleted_at IS NULL
                  AND (created_by=:teacher OR (publish_status='published' AND visibility='public'))
                LIMIT 1
                """
            ),
            {"id": question_id, "teacher": teacher_id},
        ).first()
    if not allowed:
        raise HTTPException(status_code=404, detail="题目不存在或无权查看。")
    return ensure_solution_steps_sync(question_id, teacher_id)


def save_solution_steps_sync(teacher_id: int, question_id: int, steps: list[dict[str, Any]]) -> dict[str, Any]:
    validated = SolutionStepsPayload(steps=steps)
    normalized = [item.model_dump() | {"step_no": index} for index, item in enumerate(validated.steps, start=1)]
    with SessionLocal() as db:
        allowed = db.execute(
            text("SELECT 1 FROM questions WHERE id=:id AND created_by=:teacher_id AND deleted_at IS NULL"),
            {"id": question_id, "teacher_id": teacher_id},
        ).first()
        if not allowed:
            raise HTTPException(status_code=404, detail="题目不存在，或不是你创建的题目。")
        db.execute(
            text("UPDATE questions SET solution_steps=:steps,steps_source='teacher',steps_review_status='verified' WHERE id=:id"),
            {"steps": json.dumps(normalized, ensure_ascii=False), "id": question_id},
        )
        db.commit()
    return {"question_id": question_id, "steps": normalized, "source": "teacher", "review_status": "verified"}


def score_answer_steps(answer_steps: list[str], solution_steps: list[dict[str, Any]]) -> dict[str, Any]:
    if not answer_steps:
        return {"correct_steps": [], "wrong_steps": [], "summary": "未提交分步作答。"}
    correct_steps: list[int] = []
    wrong_steps: list[dict[str, Any]] = []
    for index, expected in enumerate(solution_steps, start=1):
        if index > len(answer_steps):
            wrong_steps.append({"step_no": index, "issue": "缺少该步骤。"})
            continue
        expected_text = " ".join(str(expected.get(key) or "") for key in ("title", "explanation", "formula"))
        expected_tokens = {token.lower() for token in re.findall(r"[\w\u4e00-\u9fff]{2,}", expected_text)}
        actual_tokens = {token.lower() for token in re.findall(r"[\w\u4e00-\u9fff]{2,}", answer_steps[index - 1])}
        overlap = len(expected_tokens & actual_tokens) / max(1, min(len(expected_tokens), 8))
        if actual_tokens and (overlap >= 0.12 or len(answer_steps[index - 1].strip()) >= 18):
            correct_steps.append(index)
        else:
            wrong_steps.append({"step_no": index, "issue": f"与标准步骤“{expected.get('title') or index}”的关键依据不一致或不完整。"})
    return {"correct_steps": correct_steps, "wrong_steps": wrong_steps, "summary": f"{len(correct_steps)} 步基本正确，{len(wrong_steps)} 步需要复核。"}


def save_ai_evidence_sync(user_id: int, payload: AISelfCheckResultRequest) -> dict[str, Any]:
    question = _question_for_solution(payload.source_question_id)
    actual = str(payload.selected_answer or payload.answer_text or "").strip().lower()
    expected = str(payload.expected_answer).strip().lower()
    normalized = lambda value: re.sub(r"[\s。.;；,，]+", "", value)
    is_correct = normalized(actual) == normalized(expected)
    if not is_correct and not payload.selected_answer:
        expected_tokens = {token for token in re.findall(r"[\w\u4e00-\u9fff]{2,}", expected)}
        actual_tokens = {token for token in re.findall(r"[\w\u4e00-\u9fff]{2,}", actual)}
        is_correct = bool(expected_tokens and len(expected_tokens & actual_tokens) / len(expected_tokens) >= 0.55)
    evidence = {
        "generated_question": payload.generated_question,
        "expected_answer": payload.expected_answer,
        "knowledge_tag": payload.knowledge_tag or question.get("knowledge_tag"),
        "evidence_type": payload.evidence_type,
    }
    with SessionLocal() as db:
        result = db.execute(
            text(
                """
                INSERT INTO practice_records
                  (task_id,user_id,question_id,selected_answer,answer_text,is_correct,score,mistake_tags,
                   time_spent_seconds,practice_mode,review_status,mastery_evidence,ai_evidence_json)
                VALUES
                  (:task_id,:user_id,:question_id,:selected_answer,:answer_text,:is_correct,:score,:mistakes,
                   :seconds,'ai_similar','auto_graded',:evidence_type,:evidence)
                """
            ),
            {
                "task_id": payload.task_id, "user_id": user_id, "question_id": payload.source_question_id,
                "selected_answer": payload.selected_answer, "answer_text": payload.answer_text,
                "is_correct": 1 if is_correct else 0, "score": 100 if is_correct else 0,
                "mistakes": json.dumps([] if is_correct else ["迁移验证未通过"], ensure_ascii=False),
                "seconds": payload.time_spent_seconds, "evidence_type": payload.evidence_type,
                "evidence": json.dumps(evidence, ensure_ascii=False),
            },
        )
        db.commit()
    return {"record_id": int(result.lastrowid), "is_correct": is_correct, "score": 100 if is_correct else 0, "mastery_evidence": payload.evidence_type, "counts_toward_formal_stats": False}


def chain_recovery_sync(user_id: int, record_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT pr.id,pr.is_correct,q.id AS question_id,q.course,q.knowledge_tag,q.fine_tag,
                       q.question_type,q.knowledge_node_id,kn.parent_id,parent.name AS parent_name
                FROM practice_records pr JOIN questions q ON q.id=pr.question_id
                LEFT JOIN knowledge_nodes kn ON kn.id=q.knowledge_node_id
                LEFT JOIN knowledge_nodes parent ON parent.id=kn.parent_id
                WHERE pr.id=:record_id AND pr.user_id=:user_id LIMIT 1
                """
            ),
            {"record_id": record_id, "user_id": user_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="作答记录不存在。")
        parent_accuracy = None
        if row["parent_name"]:
            parent_accuracy = db.execute(
                text(
                    """
                    SELECT ROUND(AVG(pr.is_correct)*100,1) FROM practice_records pr
                    JOIN questions q ON q.id=pr.question_id
                    WHERE pr.user_id=:user_id AND pr.is_correct IS NOT NULL AND pr.mastery_evidence='formal'
                      AND (q.knowledge_tag=:tag OR q.fine_tag=:tag)
                    """
                ),
                {"user_id": user_id, "tag": row["parent_name"]},
            ).scalar()
        course_prerequisite = db.execute(
            text("SELECT from_course,note FROM course_relations WHERE to_course=:course AND relation='prerequisite' ORDER BY id LIMIT 1"),
            {"course": row["course"]},
        ).mappings().first()
    weak_parent = bool(row["parent_name"] and (parent_accuracy is None or float(parent_accuracy) < 60))
    target_course = str(row["course"])
    target_tag = str(row["parent_name"] or row["knowledge_tag"]) if weak_parent else str(row["knowledge_tag"])
    reason = f"前置知识“{target_tag}”尚无稳定掌握证据，先补根再回到原题。" if weak_parent else f"前置基础暂无明显短板，继续用“{target_tag}”中等题和变式加固。"
    if not row["parent_name"] and course_prerequisite:
        target_course = str(course_prerequisite["from_course"])
        target_tag = ""
        reason = f"按课程先修关系，建议先从“{target_course}”选一题补基础。"
    questions = _random_questions_sync(stage=None, course=target_course, knowledge_tag=target_tag or None, question_type=None, limit=3)
    return {
        "record_id": record_id,
        "source_question_id": int(row["question_id"]),
        "strategy": "repair_prerequisite" if weak_parent or course_prerequisite and not row["parent_name"] else "reinforce_current",
        "target": {"course": target_course, "knowledge_tag": target_tag},
        "evidence": {"parent_accuracy": float(parent_accuracy) if parent_accuracy is not None else None, "source_was_wrong": row["is_correct"] == 0},
        "reason": reason,
        "questions": questions,
    }
