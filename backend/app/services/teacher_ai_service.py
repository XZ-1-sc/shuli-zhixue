import json
from difflib import SequenceMatcher
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..api.routes.teacher import _owned_class
from ..api.teacher_schemas import AssignmentSuggestionAIRequest, ClassInsightAIRequest, GradeCommentAIRequest
from ..api.utils import _parse_json_list
from ..database.repositories.teacher_common import _managed_student
from ..database.repositories.teacher_students import _student_detail_sync
from ..database.session import SessionLocal
from ..utils.llm_client import call_llm_json


class GradeCommentDraft(BaseModel):
    encouragement: str = Field(min_length=1, max_length=500)
    issues: list[str] = Field(default_factory=list, max_length=5)
    suggestions: list[str] = Field(default_factory=list, max_length=5)
    draft: str = Field(min_length=1, max_length=3000)


class TeachingInsight(BaseModel):
    summary: str = Field(min_length=1, max_length=1000)
    highlights: list[str] = Field(default_factory=list, max_length=5)
    risks: list[str] = Field(default_factory=list, max_length=5)
    suggestions: list[str] = Field(default_factory=list, min_length=1, max_length=5)


class KnowledgeSuggestion(BaseModel):
    tag: str = Field(min_length=1, max_length=160)
    count: int = Field(ge=1, le=100)
    difficulty: int = Field(ge=1, le=5)


class AssignmentSuggestion(BaseModel):
    knowledge_tags: list[KnowledgeSuggestion] = Field(min_length=1, max_length=8)
    rationale: str = Field(min_length=1, max_length=1200)


def teaching_insight_to_card(insight: TeachingInsight, scope: str) -> dict[str, Any]:
    return {
        "type": "insight",
        "title": "班级学情解读" if scope == "class" else "学生学情解读",
        "summary": insight.summary,
        "details": [
            {"label": "亮点", "value": "；".join(insight.highlights) or "暂无明确亮点"},
            {"label": "风险点", "value": "；".join(insight.risks) or "暂无明显风险"},
            {"label": "建议", "value": "；".join(insight.suggestions)},
        ],
    }


def _grade_context(teacher_id: int, record_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        exists = db.execute(text("SELECT 1 FROM practice_records WHERE id = :record_id"), {"record_id": record_id}).first()
        row = db.execute(
            text(
                """
                SELECT DISTINCT pr.id, pr.user_id, u.username, pr.answer_text, pr.selected_answer,
                       pr.score, pr.review_status, q.question_text, q.question_type, q.course,
                       q.knowledge_tag, q.standard_answer, q.analysis_text, q.key_steps,
                       (SELECT COUNT(*) FROM answer_attachments aa WHERE aa.practice_record_id = pr.id) AS image_count
                FROM practice_records AS pr
                JOIN users AS u ON u.id = pr.user_id
                JOIN questions AS q ON q.id = pr.question_id
                JOIN class_members AS cm ON cm.student_id = pr.user_id AND cm.status = 'active'
                JOIN classes AS c ON c.id = cm.class_id AND c.teacher_id = :teacher_id AND c.status = 'active'
                LEFT JOIN assignments AS a ON a.id = pr.assignment_id
                WHERE pr.id = :record_id AND (pr.assignment_id IS NULL OR a.teacher_id = :teacher_id)
                LIMIT 1
                """
            ),
            {"teacher_id": teacher_id, "record_id": record_id},
        ).mappings().first()
    if not row:
        if exists:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该作答不属于当前教师管理范围。")
        raise HTTPException(status_code=404, detail="作答不存在。")
    return {
        "record_id": int(row["id"]),
        "student": str(row["username"]),
        "question": str(row["question_text"]),
        "question_type": str(row["question_type"]),
        "course": str(row["course"]),
        "knowledge_tag": str(row["knowledge_tag"]),
        "student_answer": row["selected_answer"] or row["answer_text"] or "仅提交图片作答",
        "image_count": int(row["image_count"] or 0),
        "standard_answer": str(row["standard_answer"] or ""),
        "analysis": str(row["analysis_text"] or ""),
        "key_steps": _parse_json_list(row["key_steps"]),
        "current_score": float(row["score"]) if row["score"] is not None else None,
        "review_status": str(row["review_status"]),
    }


def generate_grade_comment_sync(teacher_id: int, payload: GradeCommentAIRequest) -> dict[str, Any]:
    if not payload.record_id:
        raise HTTPException(status_code=422, detail="单条评语生成缺少 record_id。")
    context = _grade_context(teacher_id, payload.record_id)
    score = payload.draft_score if payload.draft_score is not None else context.get("current_score")
    encouragement = "已提交完整作答，能看出你在主动组织解题过程。" if context["student_answer"] else "已按要求完成本题作答。"
    issues = ["请核对关键步骤是否与所用定理的条件一致。"]
    if context["image_count"]:
        issues = ["图片作答需要重点核对关键推导、符号和结论是否连贯。"]
    suggestions = ["对照标准答案逐步标出差异，并独立完成一道同知识点变式题。"]
    score_phrase = f"建议分数 {score:g} 分。" if score is not None else "请教师结合关键步骤确定最终分数。"
    fallback = GradeCommentDraft(
        encouragement=encouragement,
        issues=issues,
        suggestions=suggestions,
        draft=f"{encouragement}{issues[0]}{suggestions[0]}{score_phrase}",
    )
    draft, usage = call_llm_json(
        [
            {"role": "system", "content": "你是大学数学教师的批改助手。生成可编辑评语草稿，不得宣称已完成批改，也不要直接修改成绩。"},
            {"role": "user", "content": json.dumps({**context, "draft_score": score}, ensure_ascii=False)},
        ],
        GradeCommentDraft,
        fallback=fallback,
        agent_name="teacher_grade_comment",
        temperature=0.2,
    )
    return {"record_id": payload.record_id, "draft_score": score, "comment": draft.model_dump(), "usage": usage.model_dump()}


def generate_grade_comments_sync(teacher_id: int, payload: GradeCommentAIRequest) -> dict[str, Any]:
    items = []
    for record_id in payload.record_ids or []:
        items.append(
            generate_grade_comment_sync(
                teacher_id,
                GradeCommentAIRequest(record_id=record_id, draft_score=payload.draft_score),
            )
        )
    return {"items": items, "count": len(items), "persisted": False}


def review_flags_sync(teacher_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT pr.id,pr.answer_text,pr.selected_answer,pr.review_status,
                       q.question_type,q.standard_answer,q.stage,q.course,
                       assignment_class.stage AS class_stage,assignment_class.course AS class_course,
                       COUNT(DISTINCT aa.id) AS image_count,
                       MIN(uf.width) AS min_width,MIN(uf.height) AS min_height
                FROM practice_records pr
                JOIN questions q ON q.id=pr.question_id
                LEFT JOIN assignments a ON a.id=pr.assignment_id
                LEFT JOIN classes assignment_class ON assignment_class.id=a.class_id
                LEFT JOIN answer_attachments aa ON aa.practice_record_id=pr.id
                LEFT JOIN uploaded_files uf ON uf.id=aa.uploaded_file_id
                WHERE pr.review_status='pending'
                  AND EXISTS (
                    SELECT 1 FROM class_members cm JOIN classes c ON c.id=cm.class_id
                    WHERE cm.student_id=pr.user_id AND cm.status='active'
                      AND c.teacher_id=:teacher_id AND c.status='active'
                  )
                  AND (pr.assignment_id IS NULL OR a.teacher_id=:teacher_id)
                GROUP BY pr.id,pr.answer_text,pr.selected_answer,pr.review_status,
                         q.question_type,q.standard_answer,q.stage,q.course,
                         assignment_class.stage,assignment_class.course
                ORDER BY pr.answered_at,pr.id
                """
            ),
            {"teacher_id": teacher_id},
        ).mappings().all()
    items = []
    for row in rows:
        reasons: list[str] = []
        answer = str(row["answer_text"] or row["selected_answer"] or "").strip()
        image_count = int(row["image_count"] or 0)
        if not answer and not image_count:
            reasons.append("答案为空")
        if image_count and (
            (row["min_width"] is not None and int(row["min_width"]) < 640)
            or (row["min_height"] is not None and int(row["min_height"]) < 480)
        ):
            reasons.append("作答图片分辨率偏低")
        standard = str(row["standard_answer"] or "").strip()
        similarity = SequenceMatcher(None, answer, standard).ratio() if len(answer) >= 20 and len(standard) >= 20 else 0
        if similarity >= 0.92:
            reasons.append("答案与参考文本高度相似，建议核对过程")
        if row["class_stage"] and (
            str(row["class_stage"]) != str(row["stage"])
            or str(row["class_course"]) != str(row["course"])
        ):
            reasons.append("题目阶段或课程与作业班级不一致")
        priority = 3 if "答案为空" in reasons else 2 if reasons else 0
        items.append(
            {
                "record_id": int(row["id"]),
                "priority": priority,
                "reasons": reasons,
                "needs_attention": bool(reasons),
                "image_count": image_count,
                "text_similarity": round(similarity, 3),
            }
        )
    items.sort(key=lambda item: (-item["priority"], -len(item["reasons"]), item["record_id"]))
    return {
        "items": items,
        "flagged_count": sum(1 for item in items if item["needs_attention"]),
        "total": len(items),
    }


def _class_insight_context(teacher_id: int, class_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        class_row = _owned_class(db, teacher_id, class_id)
        summary = db.execute(
            text(
                """
                SELECT COUNT(DISTINCT cm.student_id) AS student_count, COUNT(pr.id) AS attempts,
                       ROUND(AVG(CASE WHEN pr.is_correct IS NOT NULL THEN pr.is_correct END) * 100, 1) AS accuracy,
                       SUM(CASE WHEN pr.review_status = 'pending' THEN 1 ELSE 0 END) AS pending_review,
                       COUNT(DISTINCT CASE WHEN pr.answered_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) THEN pr.user_id END) AS active_7d
                FROM class_members AS cm
                LEFT JOIN practice_records AS pr ON pr.user_id = cm.student_id
                WHERE cm.class_id = :class_id AND cm.status = 'active'
                """
            ),
            {"class_id": class_id},
        ).mappings().one()
        weak = db.execute(
            text(
                """
                SELECT q.knowledge_tag, q.fine_tag, COUNT(*) AS attempts,
                       ROUND(AVG(CASE WHEN pr.is_correct IS NOT NULL THEN pr.is_correct END) * 100, 1) AS mastery
                FROM class_members AS cm
                JOIN practice_records AS pr ON pr.user_id = cm.student_id
                JOIN questions AS q ON q.id = pr.question_id
                WHERE cm.class_id = :class_id AND cm.status = 'active'
                GROUP BY q.knowledge_tag, q.fine_tag ORDER BY mastery ASC, attempts DESC LIMIT 5
                """
            ),
            {"class_id": class_id},
        ).mappings().all()
    return {
        "scope": "class",
        "class": {"id": int(class_row["id"]), "name": str(class_row["name"]), "stage": str(class_row["stage"]), "course": str(class_row["course"])},
        "summary": {key: float(value) if key == "accuracy" and value is not None else int(value or 0) for key, value in dict(summary).items()},
        "weak_points": [
            {"knowledge_tag": str(row["knowledge_tag"]), "fine_tag": str(row["fine_tag"]), "attempts": int(row["attempts"]), "mastery": float(row["mastery"] or 0)}
            for row in weak
        ],
    }


def _student_insight_context(teacher_id: int, student_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        _managed_student(db, teacher_id, student_id)
    data = _student_detail_sync(teacher_id, student_id)
    return {
        "scope": "student",
        "profile": data["profile"],
        "courses": data["courses"][:6],
        "weak_points": data["weak_points"][:5],
        "recent_records": data["recent_records"][:10],
        "assignments": data["assignments"][:8],
    }


def generate_class_insight_sync(teacher_id: int, payload: ClassInsightAIRequest) -> dict[str, Any]:
    context = _class_insight_context(teacher_id, int(payload.class_id)) if payload.scope == "class" else _student_insight_context(teacher_id, int(payload.student_id))
    if payload.scope == "class":
        summary_data = context["summary"]
        subject = context["class"]["name"]
        summary = f"{subject} 当前有 {summary_data['student_count']} 名学生，累计 {summary_data['attempts']} 次作答，正确率 {summary_data['accuracy']:g}%。"
        weak = context["weak_points"]
        risks = [f"{item['fine_tag']} 掌握度 {item['mastery']:g}%" for item in weak[:3]] or ["当前练习数据不足，暂不能稳定识别薄弱点。"]
        highlights = [f"近 7 天有 {summary_data['active_7d']} 名学生参与学习。"]
    else:
        profile = context["profile"]
        summary = f"{profile['nickname']} 已完成 {profile['practice_count']} 题，当前正确率 {profile['accuracy']:g}%。"
        weak = context["weak_points"]
        risks = [f"{item['fine_tag']} 掌握度 {item['mastery']:g}%" for item in weak[:3]] or ["练习数据不足，建议先完成基础测评。"]
        highlights = [f"累计学习 {profile['study_hours']:g} 小时。"]
    fallback = TeachingInsight(
        summary=summary,
        highlights=highlights,
        risks=risks,
        suggestions=["用 5—8 道同知识点基础题确认概念缺口。", "一周后复测并比较正确率与耗时变化。", "待批改题优先人工复核，避免诊断被延迟。"],
    )
    insight, usage = call_llm_json(
        [
            {"role": "system", "content": "你是大学数学教学分析助手。只基于授权统计给出结构化、可验证的学情解读；结果是教师决策草稿。"},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False, default=str)[:24000]},
        ],
        TeachingInsight,
        fallback=fallback,
        agent_name=f"teacher_{payload.scope}_insight",
        temperature=0.2,
    )
    return {
        "scope": payload.scope,
        "context_id": payload.class_id or payload.student_id,
        "insight": insight.model_dump(),
        "card": teaching_insight_to_card(insight, payload.scope),
        "usage": usage.model_dump(),
    }


def generate_assignment_suggestion_sync(teacher_id: int, payload: AssignmentSuggestionAIRequest) -> dict[str, Any]:
    context = _class_insight_context(teacher_id, payload.class_id)
    class_data = context["class"]
    with SessionLocal() as db:
        pool = db.execute(
            text(
                """
                SELECT knowledge_tag, difficulty, COUNT(*) AS question_count
                FROM questions
                WHERE publish_status = 'published' AND stage = :stage AND course = :course
                GROUP BY knowledge_tag, difficulty ORDER BY question_count DESC
                """
            ),
            {"stage": class_data["stage"], "course": class_data["course"]},
        ).mappings().all()
    pool_counts: dict[str, int] = {}
    for row in pool:
        pool_counts[str(row["knowledge_tag"])] = pool_counts.get(str(row["knowledge_tag"]), 0) + int(row["question_count"])
    weak = [item for item in context["weak_points"] if pool_counts.get(item["knowledge_tag"], 0) > 0]
    source = weak[:3] or [{"knowledge_tag": next(iter(pool_counts), class_data["course"]), "mastery": 60}]
    remaining = payload.question_count
    allocations = []
    for index, item in enumerate(source):
        slots = len(source) - index
        count = remaining if slots == 1 else max(1, round(payload.question_count / len(source)))
        count = min(count, remaining)
        mastery = float(item.get("mastery") or 0)
        allocations.append(KnowledgeSuggestion(tag=str(item["knowledge_tag"]), count=count, difficulty=2 if mastery < 50 else 3))
        remaining -= count
    fallback = AssignmentSuggestion(
        knowledge_tags=allocations,
        rationale="按班级掌握度从低到高分配题量，以基础和中等难度题确认概念缺口；建议教师预览题目后再加入作业。",
    )
    suggestion, usage = call_llm_json(
        [
            {"role": "system", "content": f"你是大学数学组卷助手。总题量必须为 {payload.question_count}，优先覆盖班级薄弱点，结果仅是草稿。"},
            {"role": "user", "content": json.dumps({"class": class_data, "weak_points": weak, "question_pool": [dict(row) for row in pool]}, ensure_ascii=False, default=str)},
        ],
        AssignmentSuggestion,
        fallback=fallback,
        agent_name="teacher_assignment_suggestion",
        temperature=0.2,
    )
    items = suggestion.knowledge_tags
    total = sum(item.count for item in items)
    allowed_tags = set(pool_counts)
    if total != payload.question_count or any(item.tag not in allowed_tags for item in items):
        normalized = fallback
    else:
        normalized = suggestion
    return {
        "class_id": payload.class_id,
        "question_count": payload.question_count,
        "suggestion": normalized.model_dump(),
        "pool_counts": pool_counts,
        "usage": usage.model_dump(),
    }
