from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field
from fastapi import HTTPException
from sqlalchemy import text

from ..api.schemas import AISimilarPracticeRequest
from ..database.repositories.diagnosis import _recent_records_sync
from ..database.repositories.profile import _ability_map_sync
from ..database.repositories.questions import _get_question_sync
from ..database.session import SessionLocal
from ..utils.llm_client import call_llm_json
from .notification_service import _create_notification_once_sync, _preference_enabled_sync, _quiet_hours


class GeneratedPracticeQuestion(BaseModel):
    question_type: Literal["choice", "blank", "calculation", "proof", "comprehensive"]
    question_text: str = Field(min_length=2, max_length=12000)
    options: dict[str, str] = Field(default_factory=dict)
    correct_answer: str | None = Field(default=None, max_length=1000)
    standard_answer: str = Field(min_length=1, max_length=12000)
    analysis_text: str = Field(min_length=1, max_length=20000)
    knowledge_tag: str = Field(min_length=1, max_length=160)
    difficulty: int = Field(default=3, ge=1, le=5)


class GeneratedPracticeSet(BaseModel):
    questions: list[GeneratedPracticeQuestion] = Field(min_length=1, max_length=2)


class WeeklyDigest(BaseModel):
    stats: dict[str, Any]
    mistakes_top3: list[dict[str, Any]] = Field(default_factory=list, max_length=3)
    progress: str = Field(min_length=1, max_length=1200)
    next_week: list[str] = Field(min_length=1, max_length=5)


class PracticeFollowup(BaseModel):
    sentence: str = Field(min_length=1, max_length=300)


class TeacherTicketDecision(BaseModel):
    needs_teacher: bool
    reason: str = Field(min_length=1, max_length=500)


def _fallback_similar(question: dict[str, Any]) -> GeneratedPracticeQuestion:
    options = {str(key): str(value) for key, value in (question.get("options") or {}).items() if value}
    return GeneratedPracticeQuestion(
        question_type=str(question["question_type"]),
        question_text=f"变式训练：请换一种解题路径完成这道同知识点问题，并写出关键依据。\n{question['question_text']}",
        options=options,
        correct_answer=str(question.get("correct_answer") or question.get("standard_answer") or "")[:1000] or None,
        standard_answer=str(question.get("standard_answer") or question.get("correct_answer") or "请按原题知识点完成推导。"),
        analysis_text=str(question.get("analysis_text") or "先识别所用定义或定理，再逐步完成计算并检查条件。"),
        knowledge_tag=str(question.get("fine_tag") or question.get("knowledge_tag") or "综合训练"),
        difficulty=int(question.get("difficulty") or 3),
    )


def generate_ai_similar_sync(user_id: int, payload: AISimilarPracticeRequest) -> dict[str, Any]:
    question = _get_question_sync(payload.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在或当前账号无权访问。")
    fallback_item = _fallback_similar(question)
    fallback = GeneratedPracticeSet(questions=[fallback_item.model_copy() for _ in range(payload.count)])
    generated, usage = call_llm_json(
        [
            {
                "role": "system",
                "content": (
                    f"你是大学数学变式题生成器。生成 {payload.count} 道同知识点但表述、参数或推理路径不同的题。"
                    "题目必须可独立作答，选择题必须给齐 A-D 选项和正确选项；不得复制原题。"
                ),
            },
            {"role": "user", "content": json.dumps(question, ensure_ascii=False, default=str)[:24000]},
        ],
        GeneratedPracticeSet,
        fallback=fallback,
        agent_name="student_ai_similar",
        temperature=0.45,
        max_tokens=2400,
    )
    items = []
    for item in generated.questions[: payload.count]:
        if item.question_type == "choice" and len(item.options) < 4:
            item = fallback_item.model_copy(deep=True)
        normalized = item.model_dump()
        normalized.update(
            {
                "id": f"ai-{uuid.uuid4()}",
                "source_question_id": payload.question_id,
                "practice_mode": "ai_similar",
                "disclaimer": "AI 生成，仅供参考；本次作答不计入诊断统计。",
            }
        )
        items.append(normalized)
    return {
        "task_id": f"ai-similar-{uuid.uuid4()}",
        "practice_mode": "ai_similar",
        "persisted": False,
        "questions": items,
        "usage": usage.model_dump(),
    }


def generate_weekly_digest_sync(user_id: int) -> dict[str, Any]:
    week_start = date.today() - timedelta(days=6)
    records = [record for record in _recent_records_sync(user_id, 500) if str(record.get("answered_at") or "")[:10] >= week_start.isoformat()]
    graded = [record for record in records if record.get("is_correct") is not None]
    correct = sum(1 for record in graded if bool(record.get("is_correct")))
    accuracy = round(correct / len(graded) * 100, 1) if graded else 0.0
    ability = _ability_map_sync(user_id)
    top = [
        {"reason": item["reason"], "knowledge": item["knowledge"], "count": item["count"]}
        for item in ability.get("cells", [])
        if item.get("reason") != "暂未发现稳定错因"
    ][:3]
    stats = {
        "period": f"{week_start.isoformat()} 至 {date.today().isoformat()}",
        "attempts": len(records),
        "graded": len(graded),
        "correct": correct,
        "accuracy": accuracy,
        "study_minutes": round(sum(int(item.get("time_spent_seconds") or 0) for item in records) / 60, 1),
    }
    focus = ability.get("dominant_reason") or "基础巩固"
    fallback = WeeklyDigest(
        stats=stats,
        mistakes_top3=top,
        progress=f"本周完成 {len(records)} 次作答，已评分正确率 {accuracy:g}%。当前最需要处理的是“{focus}”。",
        next_week=[ability.get("advice") or "完成一组薄弱点基础题。", "复盘本周错题并独立重做。", "周末用 5 道混合题复测。"],
    )
    digest, usage = call_llm_json(
        [
            {"role": "system", "content": "你是学习周报编辑。只基于提供的数据生成一页纸摘要，建议必须具体、可执行，不夸大结论。"},
            {"role": "user", "content": json.dumps({"stats": stats, "ability_map": ability}, ensure_ascii=False, default=str)[:24000]},
        ],
        WeeklyDigest,
        fallback=fallback,
        agent_name="student_weekly_digest",
        temperature=0.2,
        max_tokens=1800,
    )
    return {"digest": digest.model_dump(), "usage": usage.model_dump(), "generated_at": datetime.now().isoformat()}


def create_practice_followup_sync(user_id: int, brief: dict[str, Any], signal: dict[str, Any]) -> dict[str, Any]:
    if not _preference_enabled_sync(user_id):
        return {"created": False, "reason": "disabled", "notification": None}
    if _quiet_hours():
        return {"created": False, "reason": "quiet_hours", "notification": None}
    fallback_sentence = str(
        signal.get("message")
        or brief.get("suggestion")
        or "这次记录已经收好，先复盘最关键的一步，再做一道同知识点变式题。"
    )
    result, _ = call_llm_json(
        [
            {"role": "system", "content": "你是陪伴型学习助手。根据做题结果追加一句不超过 60 字的话；连错时先共情，进步时具体鼓励，不使用空泛口号。"},
            {"role": "user", "content": json.dumps({"brief": brief, "signal": signal}, ensure_ascii=False, default=str)[:8000]},
        ],
        PracticeFollowup,
        fallback=PracticeFollowup(sentence=fallback_sentence[:300]),
        agent_name="student_practice_followup",
        temperature=0.35,
        max_tokens=240,
    )
    return _create_notification_once_sync(
        user_id,
        "practice_followup",
        "小逻完成了本次复盘",
        result.sentence,
        "/review",
    )


TICKET_KEYWORDS = ("请假", "延期", "截止", "作业提交", "老师", "超纲", "看不懂题意", "焦虑", "崩溃", "不想学", "情绪")


def maybe_create_teacher_ticket_sync(user_id: int, session_id: str, message: str) -> dict[str, Any]:
    if not any(keyword in message for keyword in TICKET_KEYWORDS):
        return {"created": 0, "reason": "keyword_not_matched"}
    fallback_reason = next((keyword for keyword in TICKET_KEYWORDS if keyword in message), "需要教师介入")
    decision, _ = call_llm_json(
        [
            {"role": "system", "content": "判断学生问题是否必须由任课教师介入。仅作业截止/请假/超纲争议/明显情绪求助需要教师；普通知识讲解不需要。"},
            {"role": "user", "content": message[:3000]},
        ],
        TeacherTicketDecision,
        fallback=TeacherTicketDecision(needs_teacher=True, reason=fallback_reason),
        agent_name="student_ticket_triage",
        temperature=0.0,
        max_tokens=240,
    )
    if not decision.needs_teacher:
        return {"created": 0, "reason": decision.reason}
    with SessionLocal() as db:
        student = db.execute(
            text("SELECT username,nickname FROM users WHERE id=:user_id LIMIT 1"), {"user_id": user_id}
        ).mappings().first()
        teachers = db.execute(
            text(
                """
                SELECT DISTINCT c.teacher_id,c.name AS class_name
                FROM class_members cm JOIN classes c ON c.id=cm.class_id
                WHERE cm.student_id=:user_id AND cm.status='active' AND c.status='active'
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        created = 0
        for teacher in teachers:
            duplicate = db.execute(
                text(
                    """
                    SELECT 1 FROM user_notifications
                    WHERE user_id=:teacher_id AND type='ticket_student' AND content LIKE :session_marker LIMIT 1
                    """
                ),
                {"teacher_id": teacher["teacher_id"], "session_marker": f'%"session_id": "{session_id}"%'},
            ).first()
            if duplicate:
                continue
            payload = json.dumps(
                {
                    "content": f"{student['nickname'] or student['username']}：{message}",
                    "student_id": user_id,
                    "student_name": student["nickname"] or student["username"],
                    "class_name": teacher["class_name"],
                    "session_id": session_id,
                    "reason": decision.reason,
                    "message": message,
                },
                ensure_ascii=False,
            )
            db.execute(
                text(
                    """
                    INSERT INTO user_notifications (user_id,type,title,content,action_url)
                    VALUES (:teacher_id,'ticket_student','小逻转来一条学生工单',:content,'/teacher')
                    """
                ),
                {"teacher_id": teacher["teacher_id"], "content": payload},
            )
            created += 1
        db.commit()
    return {"created": created, "reason": decision.reason}
