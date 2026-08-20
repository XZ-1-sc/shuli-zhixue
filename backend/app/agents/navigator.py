import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..api.utils import _question_select_sql, _row_to_question
from ..database.session import SessionLocal
from ..utils.llm_client import call_llm_json
from .schemas import RecommendationQuery, WeeklyPlan


NAVIGATOR_SYSTEM_PROMPT = """
你是大学数学题目导航员。请把结构化周计划转换为题库检索条件：
course 必须沿用计划中的课程名，knowledge_tag 是最优先的具体知识点，difficulty 为 1~5。
只负责生成检索条件，不输出学习建议或自然语言说明。
""".strip()


def _fallback_query(weekly_plan: WeeklyPlan) -> RecommendationQuery:
    return RecommendationQuery(
        course=weekly_plan.focus_course,
        knowledge_tag=weekly_plan.focus_knowledge,
        difficulty=2 if "基础" in weekly_plan.focus_knowledge else 3,
    )


def _query_questions(criteria: RecommendationQuery, limit: int) -> list[dict[str, Any]]:
    attempts = [
        (criteria.course, criteria.knowledge_tag, True),
        (criteria.course, None, True),
        (criteria.course, None, False),
        (None, None, False),
    ]
    source_filter = """(
      q.source_question_no LIKE 'CURATED-%'
      OR q.source_question_no LIKE 'BACHELOR-CN-%'
      OR (q.created_by IS NOT NULL AND q.publish_status='published' AND q.visibility='public')
    )"""
    try:
        with SessionLocal() as db:
            for course, knowledge_tag, filter_difficulty in attempts:
                filters = ["q.deleted_at IS NULL", "q.question_text NOT LIKE :placeholder", source_filter]
                params: dict[str, Any] = {"placeholder": "%□%", "limit": limit}
                if course:
                    filters.append("q.course = :course")
                    params["course"] = course
                if knowledge_tag:
                    filters.append("(q.knowledge_tag = :knowledge OR q.fine_tag = :knowledge)")
                    params["knowledge"] = knowledge_tag
                if filter_difficulty:
                    filters.append("q.difficulty BETWEEN :difficulty_min AND :difficulty_max")
                    params["difficulty_min"] = max(1, criteria.difficulty - 1)
                    params["difficulty_max"] = min(5, criteria.difficulty + 1)
                rows = db.execute(
                    text(
                        f"""
                        SELECT {_question_select_sql()}
                        FROM questions AS q
                        JOIN source_attributions AS s ON s.id=q.source_id
                        WHERE {' AND '.join(filters)}
                        ORDER BY ABS(q.difficulty - :target_difficulty), RAND()
                        LIMIT :limit
                        """
                    ),
                    {**params, "target_difficulty": criteria.difficulty},
                ).mappings().all()
                if rows:
                    return [_row_to_question(row) for row in rows]
    except SQLAlchemyError:
        return []
    return []


def recommend(
    weekly_plan: WeeklyPlan,
    limit: int = 10,
    *,
    conversation_id: str | None = None,
) -> list[dict[str, Any]]:
    messages = [
        {"role": "system", "content": NAVIGATOR_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(weekly_plan.model_dump(), ensure_ascii=False, indent=2)},
    ]
    criteria, _ = call_llm_json(
        messages,
        RecommendationQuery,
        fallback=_fallback_query(weekly_plan),
        conversation_id=conversation_id,
        agent_name="navigator",
        temperature=0.1,
        max_tokens=300,
    )
    return _query_questions(criteria, max(1, min(50, limit)))
