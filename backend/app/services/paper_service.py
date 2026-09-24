import json
import random
import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..api.routes.teacher import _audit, _owned_class
from ..api.teacher_schemas import PaperIntentRequest, PaperTextRequest, TeacherQuestionAIRequest
from ..database.repositories.teacher_assignments import _assignment_detail_sync, _owned_assignment
from ..database.session import SessionLocal
from ..utils.llm_client import call_llm_json
from .analytics_service import assignment_question_stats_sync, common_issues_sync
from .teacher_ai_service import generate_teacher_questions_sync
from .teacher_experience_service import teacher_memory_context_sync


class ParsedPaperIntent(BaseModel):
    knowledge_tags: list[str] = Field(default_factory=list, max_length=20)
    difficulty_mix: dict[str, float] = Field(default_factory=lambda: {"easy": 0.2, "medium": 0.5, "hard": 0.3})
    count: int = Field(default=10, ge=1, le=100)
    types: list[Literal["choice", "blank", "calculation", "proof", "comprehensive"]] = Field(default_factory=list, max_length=5)
    timed_minutes: int | None = Field(default=None, ge=5, le=600)
    title: str = Field(default="AI 组卷草稿", max_length=160)


class ReviewIssue(BaseModel):
    severity: Literal["low", "medium", "high"]
    message: str = Field(min_length=1, max_length=1000)
    question_id: int | None = None


class PaperReview(BaseModel):
    passed: bool
    summary: str = Field(min_length=1, max_length=1200)
    issues: list[ReviewIssue] = Field(default_factory=list, max_length=30)


class LectureDraft(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    objectives: list[str] = Field(default_factory=list, max_length=8)
    common_issues: list[str] = Field(default_factory=list, max_length=10)
    teaching_flow: list[str] = Field(default_factory=list, max_length=12)
    quick_checks: list[str] = Field(default_factory=list, max_length=6)
    teacher_notes: str = Field(default="", max_length=3000)


def parse_paper_intent_sync(teacher_id: int, payload: PaperTextRequest) -> dict[str, Any]:
    if payload.class_id:
        with SessionLocal() as db:
            class_row = _owned_class(db, teacher_id, payload.class_id)
    else:
        class_row = None
    count_match = re.search(r"(\d{1,3})\s*题", payload.message)
    minute_match = re.search(r"(\d{1,3})\s*分钟", payload.message)
    known_tags = ["极限", "连续", "导数", "积分", "矩阵", "行列式", "概率", "微分方程", "解析几何", "复变函数"]
    tags = [tag for tag in known_tags if tag in payload.message]
    types = [value for word, value in (("选择", "choice"), ("填空", "blank"), ("计算", "calculation"), ("证明", "proof"), ("综合", "comprehensive")) if word in payload.message]
    fallback = ParsedPaperIntent(
        knowledge_tags=tags,
        difficulty_mix={"easy": 0.15, "medium": 0.5, "hard": 0.35} if "偏难" in payload.message else {"easy": 0.3, "medium": 0.5, "hard": 0.2},
        count=min(100, int(count_match.group(1))) if count_match else 10,
        types=types,
        timed_minutes=min(600, int(minute_match.group(1))) if minute_match else None,
        title=f"{tags[0] if tags else (class_row['course'] if class_row else '课程')}练习",
    )
    parsed, usage = call_llm_json(
        [
            {"role": "system", "content": "从教师一句话中提取组卷意图。没有明确给出的字段保留合理默认，不能虚构班级。"},
            {"role": "user", "content": json.dumps({"message": payload.message, "class": dict(class_row) if class_row else None}, ensure_ascii=False, default=str)},
        ],
        ParsedPaperIntent,
        fallback=fallback,
        agent_name="paper_intent_parser",
        temperature=0.0,
        max_tokens=800,
    )
    result = parsed.model_dump()
    mix = result.get("difficulty_mix") or {}
    if not any(float(value or 0) > 0 for value in mix.values()):
        result["difficulty_mix"] = fallback.difficulty_mix
    result["class_id"] = payload.class_id
    missing = [] if payload.class_id else ["class_id"]
    if not result["knowledge_tags"]:
        missing.append("knowledge_tags")
    return {"intent": result, "missing_fields": missing, "ready": not missing, "usage": usage.model_dump()}


def _difficulty_group(value: int) -> str:
    return "easy" if value <= 2 else "medium" if value == 3 else "hard"


def create_assignment_draft_sync(teacher_id: int, payload: PaperIntentRequest) -> dict[str, Any]:
    with SessionLocal() as db:
        class_row = _owned_class(db, teacher_id, payload.class_id)
        clauses = ["q.deleted_at IS NULL", "q.publish_status='published'", "(q.created_by=:teacher_id OR q.visibility='public')"]
        params: dict[str, Any] = {"teacher_id": teacher_id}
        if payload.knowledge_tags:
            placeholders = []
            for index, tag in enumerate(payload.knowledge_tags):
                params[f"tag{index}"] = tag
                placeholders.append(f":tag{index}")
            clauses.append(f"(q.knowledge_tag IN ({','.join(placeholders)}) OR q.fine_tag IN ({','.join(placeholders)}))")
        else:
            clauses.append("q.course=:course")
            params["course"] = class_row["course"]
        if payload.types:
            type_keys = []
            for index, value in enumerate(payload.types):
                params[f"type{index}"] = value
                type_keys.append(f":type{index}")
            clauses.append(f"q.question_type IN ({','.join(type_keys)})")
        rows = db.execute(
            text(f"SELECT q.id,q.question_type,q.difficulty,q.knowledge_tag,q.fine_tag,q.question_text FROM questions q WHERE {' AND '.join(clauses)} ORDER BY q.updated_at DESC LIMIT 1000"),
            params,
        ).mappings().all()

        mix_total = sum(payload.difficulty_mix.values()) or 1
        target_by_group = {key: round(payload.count * payload.difficulty_mix.get(key, 0) / mix_total) for key in ("easy", "medium", "hard")}
        while sum(target_by_group.values()) < payload.count:
            target_by_group["medium"] += 1
        while sum(target_by_group.values()) > payload.count:
            key = max(target_by_group, key=target_by_group.get)
            target_by_group[key] -= 1
        pools: dict[str, list[Any]] = {"easy": [], "medium": [], "hard": []}
        for row in rows:
            pools[_difficulty_group(int(row["difficulty"] or 3))].append(row)
        rng = random.Random(f"{teacher_id}:{payload.class_id}:{payload.title}:{payload.count}")
        selected: list[Any] = []
        for key in pools:
            rng.shuffle(pools[key])
            selected.extend(pools[key][:target_by_group[key]])
        selected_ids = {int(row["id"]) for row in selected}
        overflow = [row for row in rows if int(row["id"]) not in selected_ids]
        rng.shuffle(overflow)
        selected.extend(overflow[: max(0, payload.count - len(selected))])
        selected = selected[:payload.count]
        if not selected:
            raise HTTPException(status_code=422, detail="当前筛选下没有已审核发布且可用的题目。")
        title = (payload.title or f"{payload.knowledge_tags[0] if payload.knowledge_tags else class_row['course']} · AI 组卷草稿").strip()
        result = db.execute(
            text(
                """
                INSERT INTO assignments
                  (teacher_id,class_id,title,description,status,time_limit_minutes,max_attempts,
                   show_analysis_after_submit,total_score,ai_intent_json,ai_generated)
                VALUES (:teacher_id,:class_id,:title,:description,'draft',:minutes,1,1,100,:intent,1)
                """
            ),
            {"teacher_id": teacher_id, "class_id": payload.class_id, "title": title, "description": payload.note or "由小逻按教师确认的组卷意图生成，发布前请逐题审核。", "minutes": payload.timed_minutes, "intent": json.dumps(payload.model_dump(), ensure_ascii=False)},
        )
        assignment_id = int(result.lastrowid)
        points = round(100 / len(selected), 2)
        for index, row in enumerate(selected, start=1):
            db.execute(text("INSERT INTO assignment_questions (assignment_id,question_id,sort_order,points) VALUES (:a,:q,:n,:p)"), {"a": assignment_id, "q": int(row["id"]), "n": index, "p": points})
        db.execute(text("UPDATE assignments SET total_score=(SELECT SUM(points) FROM assignment_questions WHERE assignment_id=:id) WHERE id=:id"), {"id": assignment_id})
        _audit(db, teacher_id, "assignment.ai_draft_created", "assignment", assignment_id, {"intent": payload.model_dump(), "selected": len(selected)})
        db.commit()

    shortage = max(0, payload.count - len(selected))
    supplement_drafts: list[dict[str, Any]] = []
    if shortage and payload.allow_ai_supplement:
        generated = generate_teacher_questions_sync(teacher_id, TeacherQuestionAIRequest(
            course=str(class_row["course"]), knowledge_tag=payload.knowledge_tags[0] if payload.knowledge_tags else str(class_row["course"]),
            question_type=payload.types[0] if payload.types else "choice", difficulty=3, count=min(5, shortage),
            requirements="用于当前试卷补题；只保存为待审核草稿，教师发布后才能加入试卷。",
        ))
        supplement_drafts = [{"id": item["id"], "question_text": item["question_text"]} for item in generated.get("items", [])]
    detail = _assignment_detail_sync(teacher_id, assignment_id)
    return {
        **detail,
        "card": {"title": title, "question_count": len(selected), "requested_count": payload.count, "difficulty": dict(Counter(_difficulty_group(int(row["difficulty"] or 3)) for row in selected)), "knowledge_tags": list(dict.fromkeys(str(row["knowledge_tag"]) for row in selected))},
        "shortage": shortage,
        "supplement_drafts": supplement_drafts,
        "notice": "草稿尚未发布；AI 补题必须先逐题审核发布，再由教师加入试卷。" if shortage else "草稿尚未发布，请编辑与质检后再发布。",
    }


def review_assignment_sync(teacher_id: int, assignment_id: int) -> dict[str, Any]:
    detail = _assignment_detail_sync(teacher_id, assignment_id)
    assignment = detail["assignment"]
    questions = detail["questions"]
    issues: list[ReviewIssue] = []
    fingerprints: dict[str, int] = {}
    for item in questions:
        fingerprint = re.sub(r"\W+", "", item["question_text"]).lower()
        if fingerprint in fingerprints:
            issues.append(ReviewIssue(severity="high", message=f"与第 {fingerprints[fingerprint]} 题题干重复。", question_id=item["id"]))
        fingerprints[fingerprint] = item["sort_order"]
    coverage = Counter(item["knowledge_tag"] for item in questions)
    if len(questions) >= 6 and len(coverage) == 1:
        issues.append(ReviewIssue(severity="medium", message="知识点覆盖过于集中，建议加入相邻知识点验证迁移能力。"))
    if assignment.get("time_limit_minutes") and assignment["time_limit_minutes"] < max(5, round(len(questions) * 1.5)):
        issues.append(ReviewIssue(severity="high", message="限时相对题量偏短，可能无法完成。"))
    fallback = PaperReview(passed=not any(item.severity == "high" for item in issues), summary=f"已检查 {len(questions)} 道题的重复、覆盖、题量与限时。", issues=issues)
    memory = teacher_memory_context_sync(teacher_id)
    review, usage = call_llm_json(
        [
            {"role": "system", "content": "你是试卷质检助手。检查难度一致性、超纲风险和题干歧义；不得把不确定推测写成事实。规则检查结果不得删除。"},
            {"role": "user", "content": json.dumps({"assignment": assignment, "questions": questions, "rule_issues": [item.model_dump() for item in issues], "teacher_memory": memory}, ensure_ascii=False, default=str)[:24000]},
        ],
        PaperReview,
        fallback=fallback,
        agent_name="assignment_quality_review",
        temperature=0.1,
        max_tokens=1800,
    )
    merged = [item.model_dump() for item in issues]
    seen = {(item["severity"], item["message"], item.get("question_id")) for item in merged}
    for item in review.issues:
        value = item.model_dump()
        key = (value["severity"], value["message"], value.get("question_id"))
        if key not in seen:
            merged.append(value)
    passed = not any(item["severity"] == "high" for item in merged)
    report = {"passed": passed, "summary": review.summary, "issues": merged, "reviewed_question_count": len(questions)}
    with SessionLocal() as db:
        _owned_assignment(db, teacher_id, assignment_id)
        db.execute(text("UPDATE assignments SET review_report_json=:report WHERE id=:id"), {"report": json.dumps(report, ensure_ascii=False), "id": assignment_id})
        db.commit()
    return {"assignment_id": assignment_id, **report, "usage": usage.model_dump(), "advisory_only": True}


def generate_lecture_draft_sync(teacher_id: int, assignment_id: int) -> dict[str, Any]:
    stats = assignment_question_stats_sync(teacher_id, assignment_id)
    with SessionLocal() as db:
        assignment = _owned_assignment(db, teacher_id, assignment_id)
    weak = sorted(stats["items"], key=lambda item: (item["correct_rate"], -item["answered_count"]))[:5]
    fallback = LectureDraft(
        title=f"《{assignment['title']}》讲评与下堂课建议",
        objectives=[f"讲清{item['knowledge_tag']}中导致第 {item['sort_order']} 题失分的关键边界" for item in weak[:3]] or ["根据提交数据完成针对性讲评"],
        common_issues=[f"第 {item['sort_order']} 题正确率 {item['correct_rate']:g}%" for item in weak if item["answered_count"]],
        teaching_flow=["先展示匿名错误分布，让学生判断第一处偏差。", "用共错题复盘标准步骤与易错提示。", "安排 1 分钟变式自测验证是否听懂。"],
        quick_checks=["能否说出该方法的适用条件？", "换一个参数后第一步是否仍相同？"],
        teacher_notes="该内容是 AI 草稿，教师确认后使用。",
    )
    draft, usage = call_llm_json(
        [{"role": "system", "content": "只依据真实作答统计生成可执行讲评稿，包含课堂顺序和即时自测，不得虚构学生表现。"}, {"role": "user", "content": json.dumps({"assignment": assignment, "question_stats": stats, "teacher_memory": teacher_memory_context_sync(teacher_id)}, ensure_ascii=False, default=str)[:24000]}],
        LectureDraft, fallback=fallback, agent_name="assignment_lecture_draft", temperature=0.2, max_tokens=2200,
    )
    content = draft.model_dump()
    with SessionLocal() as db:
        db.execute(text("UPDATE assignments SET lecture_draft=:draft WHERE id=:id AND teacher_id=:teacher"), {"draft": json.dumps(content, ensure_ascii=False), "id": assignment_id, "teacher": teacher_id})
        result = db.execute(text("INSERT INTO teaching_artifacts (teacher_id,artifact_type,class_id,assignment_id,title,content_json,source_snapshot_json) VALUES (:teacher,'lecture_draft',:class_id,:assignment_id,:title,:content,:snapshot)"), {"teacher": teacher_id, "class_id": int(assignment["class_id"]), "assignment_id": assignment_id, "title": content["title"], "content": json.dumps(content, ensure_ascii=False), "snapshot": json.dumps(stats, ensure_ascii=False)})
        db.commit()
    return {"artifact_id": int(result.lastrowid), "assignment_id": assignment_id, "draft": content, "usage": usage.model_dump(), "status": "draft"}


def assignment_similarity_sync(teacher_id: int, assignment_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        _owned_assignment(db, teacher_id, assignment_id)
        rows = db.execute(text("SELECT aa.user_id,u.username,ans.assignment_question_id,COALESCE(ans.answer_text,ans.selected_answer,'') answer FROM assignment_attempts aa JOIN users u ON u.id=aa.user_id JOIN assignment_answers ans ON ans.attempt_id=aa.id WHERE aa.assignment_id=:id AND aa.submitted_at IS NOT NULL"), {"id": assignment_id}).mappings().all()
    grouped: dict[int, list[Any]] = {}
    for row in rows:
        grouped.setdefault(int(row["assignment_question_id"]), []).append(row)
    hints = []
    for question_id, answers in grouped.items():
        for index, left in enumerate(answers):
            for right in answers[index + 1:]:
                if len(str(left["answer"])) < 20 or len(str(right["answer"])) < 20:
                    continue
                ratio = SequenceMatcher(None, re.sub(r"\s+", "", str(left["answer"])), re.sub(r"\s+", "", str(right["answer"]))).ratio()
                if ratio >= 0.9:
                    hints.append({"assignment_question_id": question_id, "students": [left["username"], right["username"]], "similarity": round(ratio, 3), "notice": "仅为文本相似提示，不构成抄袭判定。"})
    return {"assignment_id": assignment_id, "hints": hints, "total": len(hints), "advisory_only": True}
