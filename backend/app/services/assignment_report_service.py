import json
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import text

from ..database.repositories.teacher_assignments import _owned_assignment
from ..database.session import SessionLocal
from ..utils.llm_client import call_llm_json
from .teacher_analytics_service import assignment_analytics_sync


class AssignmentReport(BaseModel):
    overall: str = Field(min_length=1, max_length=1200)
    weak_points: list[str] = Field(default_factory=list, max_length=8)
    at_risk_students: list[str] = Field(default_factory=list, max_length=12)
    suggestions: list[str] = Field(default_factory=list, min_length=1, max_length=8)


def generate_assignment_report_sync(teacher_id: int, assignment_id: int) -> dict[str, Any]:
    analytics = assignment_analytics_sync(teacher_id, assignment_id)
    with SessionLocal() as db:
        assignment = _owned_assignment(db, teacher_id, assignment_id)
        question_rows = db.execute(
            text(
                """
                SELECT aq.id,aq.sort_order,q.question_text,q.knowledge_tag,
                       COUNT(CASE WHEN aa.id IS NOT NULL THEN ans.id END) AS attempts,
                       ROUND(AVG(CASE WHEN aa.id IS NOT NULL AND ans.is_correct IS NOT NULL THEN ans.is_correct END)*100,1) AS accuracy
                FROM assignment_questions aq
                JOIN questions q ON q.id=aq.question_id
                LEFT JOIN assignment_answers ans ON ans.assignment_question_id=aq.id
                LEFT JOIN assignment_attempts aa ON aa.id=ans.attempt_id AND aa.submitted_at IS NOT NULL
                WHERE aq.assignment_id=:assignment_id
                GROUP BY aq.id,aq.sort_order,q.question_text,q.knowledge_tag
                ORDER BY aq.sort_order
                """
            ),
            {"assignment_id": assignment_id},
        ).mappings().all()
    anomalies = [
        {
            "question_id": int(row["id"]),
            "sort_order": int(row["sort_order"]),
            "question_text": str(row["question_text"])[:240],
            "knowledge_tag": str(row["knowledge_tag"]),
            "attempts": int(row["attempts"] or 0),
            "accuracy": float(row["accuracy"] or 0),
        }
        for row in question_rows
        if int(row["attempts"] or 0) > 0 and float(row["accuracy"] or 0) < 40
    ]
    active = [student for student in analytics["students"] if student["attempts"] > 0]
    overall_accuracy = round(sum(student["accuracy"] * student["attempts"] for student in active) / max(sum(student["attempts"] for student in active), 1), 1)
    weak_points = [
        f"{item['knowledge_tag']}（{item['accuracy']:g}%）"
        for item in analytics["knowledge_mastery"][:5]
        if item["attempts"] > 0
    ]
    risks = [
        f"{item['nickname']}：正确率 {item['accuracy']:g}%，薄弱点 {('、'.join(item['weak_knowledge']) or '待补充作答')}"
        for item in sorted(active, key=lambda value: (value["accuracy"], -value["attempts"]))[:8]
        if item["accuracy"] < 60
    ]
    fallback = AssignmentReport(
        overall=f"《{assignment['title']}》已有 {len(active)} 名学生提交有效作答，按题次加权正确率约 {overall_accuracy:g}%。",
        weak_points=weak_points or ["有效作答数据不足，暂不能稳定识别薄弱知识点。"],
        at_risk_students=risks,
        suggestions=["先讲解低正确率题的关键概念，再安排一道同结构变式题即时确认。", "对正确率低于 60% 的学生发送个体建议并在一周内复测。"],
    )
    report, usage = call_llm_json(
        [
            {"role": "system", "content": "你是大学数学作业分析助手。只基于给定真实统计生成结构化教学报告，结论需具体、可核验。"},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "assignment": {"id": assignment_id, "title": assignment["title"], "class_name": assignment["class_name"]},
                        "analytics": analytics,
                        "anomalous_questions": anomalies,
                    },
                    ensure_ascii=False,
                    default=str,
                )[:24000],
            },
        ],
        AssignmentReport,
        fallback=fallback,
        agent_name="teacher_assignment_report",
        temperature=0.2,
    )
    card = {
        "type": "insight",
        "title": f"{assignment['title']} · AI 作业报告",
        "summary": report.overall,
        "metrics": [
            {"label": "提交人数", "value": str(len(active))},
            {"label": "整体正确率", "value": f"{overall_accuracy:g}%"},
            {"label": "异常题", "value": f"{len(anomalies)} 道"},
        ],
        "details": [
            {"label": "薄弱知识", "value": "；".join(report.weak_points) or "暂无"},
            {"label": "重点关注", "value": "；".join(report.at_risk_students) or "暂无明显高风险学生"},
            {"label": "教学建议", "value": "；".join(report.suggestions)},
            {"label": "异常题", "value": "；".join(f"第{item['sort_order']}题 {item['accuracy']:g}%" for item in anomalies) or "暂无低于 40% 的题目"},
        ],
    }
    return {
        "assignment_id": assignment_id,
        "report": report.model_dump(),
        "analytics": analytics,
        "anomalous_questions": anomalies,
        "student_summaries": active,
        "card": card,
        "usage": usage.model_dump(),
    }
