import asyncio
import json
import math
import re
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...database.session import SessionLocal
from ...security import current_session_user
from ...utils.llm_client import call_llm


router = APIRouter(prefix="/api", tags=["math-learning"])

TYPE_LABELS = {
    "choice": "选择题",
    "blank": "填空题",
    "calculation": "计算题",
    "proof": "证明题",
    "comprehensive": "综合题",
}

KNOWLEDGE_NAME_MAP = {
    "Limits": "极限",
    "Limits and continuity": "极限与连续",
    "Differentiation": "导数",
    "Applications of differentiation": "导数应用",
    "Integrals": "积分",
    "Techniques of integration": "积分方法",
    "Matrices": "矩阵",
    "Systems of linear equations": "线性方程组",
    "Abstract vector spaces": "向量空间",
    "Inner products": "内积",
    "Determinants": "行列式",
    "Eigenvalues": "特征值",
    "Discrete distributions": "离散分布",
    "Continuous distributions": "连续分布",
    "Confidence intervals": "置信区间",
    "Experimental design": "试验设计",
    "Exploratory data analysis/descriptive statistics": "描述统计",
    "Hypothesis tests": "假设检验",
    "Laws, theory": "概率定理",
    "Arithmetic": "复数运算",
    "Limits and accumulation points": "极限点",
    "Abstract algebra": "抽象代数",
    "Fields and polynomials": "域与多项式",
    "Groups": "群",
    "Counting": "计数方法",
    "Linear programming": "线性规划",
    "Recurrence relations": "递推关系",
    "Terminology": "建模术语",
    "Walks": "路径与图",
    "First order logic": "一阶逻辑",
    "Operations on sets": "集合运算",
    "Propositional logic": "命题逻辑",
    "Relations between sets": "集合关系",
}


def _display_knowledge_name(value: Any) -> str:
    raw = re.sub(r"\s+", " ", str(value or "").strip())
    if not raw:
        return "待整理知识点"
    if raw in KNOWLEDGE_NAME_MAP:
        return KNOWLEDGE_NAME_MAP[raw]
    if re.search(r"[A-Za-z]", raw) and not re.search(r"[\u4e00-\u9fff]", raw):
        return "待整理知识点"
    return raw


def _is_unmapped_english_label(value: Any) -> bool:
    raw = re.sub(r"\s+", " ", str(value or "").strip())
    return bool(raw and raw not in KNOWLEDGE_NAME_MAP and re.search(r"[A-Za-z]", raw) and not re.search(r"[\u4e00-\u9fff]", raw))


def _mastery_status(score: int | float | None) -> str:
    if score is None:
        return "untested"
    if score >= 80:
        return "good"
    if score >= 50:
        return "medium"
    return "weak"

CHAT_SYSTEM_PROMPT = """
你是“数理智学”里的小逻，一名大学数学学习助教。
你的任务是帮助本科阶段学生诊断薄弱点、解释错题、规划学习顺序和安排复习节奏。
回答要具体、简洁、可执行。遇到证明题时优先给思路和关键步骤，不直接堆长篇答案。
如果用户问学习规划，要结合阶段、课程、薄弱知识点和最近做题记录。
""".strip()


class ChatRequest(BaseModel):
    user_id: int = Field(default=1, ge=1)
    message: str = Field(min_length=1, max_length=3000)
    session_id: str | None = Field(default=None, max_length=64)


class GoalRequest(BaseModel):
    user_id: int = Field(ge=1)
    target_course: str = Field(default="高等数学上", min_length=1, max_length=128)
    target_stage: str = Field(default="大一", min_length=1, max_length=16)
    weekly_hours: float = Field(default=8.0, ge=0.5, le=80)
    exam_date: date | None = None


class NoteRequest(BaseModel):
    user_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(default="", max_length=6000)
    course: str | None = Field(default=None, max_length=128)
    knowledge_tag: str | None = Field(default=None, max_length=160)
    attachment_ids: list[int] = Field(default_factory=list, max_length=10)


class NoteUpdateRequest(BaseModel):
    user_id: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    content: str | None = Field(default=None, max_length=6000)
    course: str | None = Field(default=None, max_length=128)
    knowledge_tag: str | None = Field(default=None, max_length=160)
    attachment_ids: list[int] | None = Field(default=None, max_length=10)


class AnswerSubmissionRequest(BaseModel):
    user_id: int = Field(ge=1)
    task_id: str = Field(min_length=1, max_length=64)
    question_id: int = Field(ge=1)
    selected_answer: str | None = Field(default=None, max_length=16)
    answer_text: str | None = Field(default=None, max_length=6000)
    attachment_ids: list[int] = Field(default_factory=list, max_length=5)
    time_spent_seconds: int = Field(default=0, ge=0)
    practice_mode: str = Field(default="custom", pattern="^(daily|chapter|mock|wrong_book|custom|assessment)$")


class AssessmentStartRequest(BaseModel):
    user_id: int = Field(ge=1)
    stage: str | None = Field(default=None, max_length=16)
    limit: int = Field(default=12, ge=5, le=30)
    restart: bool = False


def _json_safe(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _parse_json_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [part.strip() for part in str(value).split(",") if part.strip()]
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return [str(parsed)]


def _parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _row_to_question(row: Any, include_answer: bool = False) -> dict[str, Any]:
    item = dict(row)
    options = {
        "A": item.pop("option_a", None),
        "B": item.pop("option_b", None),
        "C": item.pop("option_c", None),
        "D": item.pop("option_d", None),
    }
    item["type_label"] = TYPE_LABELS.get(str(item.get("question_type")), str(item.get("question_type")))
    item["options"] = {key: value for key, value in options.items() if value}
    item["key_steps"] = _parse_json_list(item.get("key_steps"))
    item["common_errors"] = _parse_json_list(item.get("common_errors"))
    item["mistake_tags"] = _parse_json_list(item.get("mistake_tags"))
    item["attachments"] = _parse_json_object(item.pop("question_attachments", None))
    item["attachments"].setdefault("question", [])
    item["attachments"].setdefault("analysis", [])
    item["created_at"] = _json_safe(item.get("created_at"))
    item["updated_at"] = _json_safe(item.get("updated_at"))
    if not include_answer:
        for answer_key in ("correct_answer", "standard_answer", "analysis_text"):
            item.pop(answer_key, None)
    return item


def _question_select_sql() -> str:
    return """
      q.id,
      q.source_question_no,
      q.source_path,
      q.question_type,
      q.stage,
      q.course,
      q.knowledge_node_id,
      q.knowledge_tag,
      q.fine_tag,
      q.difficulty,
      q.question_text,
      q.option_a,
      q.option_b,
      q.option_c,
      q.option_d,
      q.correct_answer,
      q.standard_answer,
      q.analysis_text,
      q.key_steps,
      q.common_errors,
      q.mistake_tags,
      (
        SELECT JSON_OBJECT(
          'question', COALESCE((
            SELECT JSON_ARRAYAGG(JSON_OBJECT('id',uf1.id,'name',uf1.original_name,'url',CONCAT('/api/files/',uf1.id)))
            FROM question_attachments qa1 JOIN uploaded_files uf1 ON uf1.id=qa1.uploaded_file_id
            WHERE qa1.question_id=q.id AND qa1.attachment_type='question'
          ), JSON_ARRAY()),
          'analysis', COALESCE((
            SELECT JSON_ARRAYAGG(JSON_OBJECT('id',uf2.id,'name',uf2.original_name,'url',CONCAT('/api/files/',uf2.id)))
            FROM question_attachments qa2 JOIN uploaded_files uf2 ON uf2.id=qa2.uploaded_file_id
            WHERE qa2.question_id=q.id AND qa2.attachment_type='analysis'
          ), JSON_ARRAY())
        )
      ) AS question_attachments,
      s.source_name,
      s.source_url,
      s.license_name
    """


def _get_user_exists(db: Any, user_id: int) -> bool:
    return bool(
        db.execute(text("SELECT 1 FROM users WHERE id = :user_id LIMIT 1"), {"user_id": user_id}).first()
    )


def _stages_sync() -> list[dict[str, Any]]:
    query = text(
        """
        SELECT
          s.id AS stage_id,
          s.stage_name,
          s.stage_order,
          s.title,
          s.goal_text,
          c.id AS course_id,
          c.course_name,
          c.course_group,
          c.course_order,
          c.description
        FROM math_stages AS s
        LEFT JOIN math_courses AS c ON c.stage_id = s.id
        ORDER BY s.stage_order, c.course_order, c.id
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query).mappings().all()

    stages: dict[str, dict[str, Any]] = {}
    for row in rows:
        stage = stages.setdefault(
            str(row["stage_name"]),
            {
                "id": int(row["stage_id"]),
                "stage_name": str(row["stage_name"]),
                "stage_order": int(row["stage_order"]),
                "title": str(row["title"]),
                "goal_text": str(row["goal_text"]),
                "courses": [],
            },
        )
        if row["course_id"] is not None:
            stage["courses"].append(
                {
                    "id": int(row["course_id"]),
                    "course_name": str(row["course_name"]),
                    "course_group": str(row["course_group"]),
                    "course_order": int(row["course_order"]),
                    "description": str(row["description"] or ""),
                }
            )
    return list(stages.values())


def _courses_sync(stage: str | None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    where_clause = ""
    if stage:
        where_clause = "WHERE s.stage_name = :stage"
        params["stage"] = stage

    query = text(
        f"""
        SELECT
          c.id,
          s.stage_name,
          s.stage_order,
          c.course_name,
          c.course_group,
          c.course_order,
          c.description
        FROM math_courses AS c
        JOIN math_stages AS s ON s.id = c.stage_id
        {where_clause}
        ORDER BY s.stage_order, c.course_order, c.id
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query, params).mappings().all()
    return [
        {
            "id": int(row["id"]),
            "stage": str(row["stage_name"]),
            "course_name": str(row["course_name"]),
            "course_group": str(row["course_group"]),
            "course_order": int(row["course_order"]),
            "description": str(row["description"] or ""),
        }
        for row in rows
    ]


def _knowledge_graph_sync(stage: str | None, course: str | None, user_id: int | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    filters = []
    if stage:
        filters.append("stage_name = :stage")
        params["stage"] = stage
    if course:
        filters.append("course_name = :course")
        params["course"] = course
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    query = text(
        f"""
        SELECT id, node_code, parent_id, stage_name, course_name, name, level, sort_order, description
        FROM knowledge_nodes
        {where_clause}
        ORDER BY stage_name, course_name, level, sort_order, id
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query, params).mappings().all()
        mastery_rows = []
        if user_id:
            mastery_rows = db.execute(
                text(
                    """
                    SELECT
                      q.course,
                      q.knowledge_tag,
                      q.fine_tag,
                      COUNT(*) AS total,
                      SUM(CASE WHEN pr.is_correct = 1 THEN 1 ELSE 0 END) AS correct
                    FROM practice_records AS pr
                    JOIN questions AS q ON q.id = pr.question_id
                    WHERE pr.user_id = :user_id AND pr.is_correct IS NOT NULL
                    GROUP BY q.course, q.knowledge_tag, q.fine_tag
                    """
                ),
                {"user_id": user_id},
            ).mappings().all()

    mastery_by_key: dict[tuple[str, str], int] = {}
    course_scores: dict[str, list[int]] = {}
    for item in mastery_rows:
        total = int(item["total"] or 0)
        if not total:
            continue
        score = round(int(item["correct"] or 0) / total * 100)
        course_name = str(item["course"])
        for label in (item["knowledge_tag"], item["fine_tag"]):
            display_label = _display_knowledge_name(label)
            mastery_by_key[(course_name, display_label)] = score
            mastery_by_key[(course_name, str(label))] = score
        course_scores.setdefault(course_name, []).append(score)

    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    stage_ids: set[str] = set()
    course_ids: set[str] = set()
    visible_knowledge_ids: set[int] = set()

    for row in rows:
        stage_id = f"stage:{row['stage_name']}"
        course_id = f"course:{row['stage_name']}:{row['course_name']}"
        if stage_id not in stage_ids:
            nodes.append(
                {
                    "id": stage_id,
                    "name": str(row["stage_name"]),
                    "category": "stage",
                    "stage": str(row["stage_name"]),
                    "symbolSize": 52,
                    "mastery": 0,
                    "mastery_status": "untested",
                }
            )
            stage_ids.add(stage_id)
        if course_id not in course_ids:
            course_score = None
            if row["course_name"] in course_scores:
                course_score = round(sum(course_scores[str(row["course_name"])]) / len(course_scores[str(row["course_name"])]))
            nodes.append(
                {
                    "id": course_id,
                    "name": str(row["course_name"]),
                    "category": "course",
                    "stage": str(row["stage_name"]),
                    "course": str(row["course_name"]),
                    "symbolSize": 46,
                    "mastery": course_score or 0,
                    "mastery_status": _mastery_status(course_score),
                }
            )
            links.append({"source": stage_id, "target": course_id, "relation": "包含"})
            course_ids.add(course_id)

        node_id = f"node:{row['id']}"
        level = int(row["level"])
        if _is_unmapped_english_label(row["name"]):
            continue
        display_name = _display_knowledge_name(row["name"])
        mastery_score = mastery_by_key.get((str(row["course_name"]), display_name)) or mastery_by_key.get(
            (str(row["course_name"]), str(row["name"]))
        )
        visible_knowledge_ids.add(int(row["id"]))
        nodes.append(
            {
                "id": node_id,
                "name": display_name,
                "category": "knowledge",
                "stage": str(row["stage_name"]),
                "course": str(row["course_name"]),
                "level": level,
                "symbolSize": max(24, 42 - level * 4),
                "mastery": mastery_score or 0,
                "mastery_status": _mastery_status(mastery_score),
                "description": f"{row['course_name']}：{display_name}",
            }
        )
        parent_id = row["parent_id"]
        parent_source = f"node:{parent_id}" if parent_id and int(parent_id) in visible_knowledge_ids else course_id
        links.append(
            {
                "source": parent_source,
                "target": node_id,
                "relation": "先修关系" if parent_id else "知识点",
            }
        )

    return {"nodes": nodes, "links": links, "total": len(nodes)}


def _question_type_counts_sync() -> dict[str, Any]:
    query = text(
        """
        SELECT stage, course, question_type, knowledge_tag, COUNT(*) AS total
        FROM questions
        WHERE deleted_at IS NULL
          AND (created_by IS NULL OR (publish_status='published' AND visibility='public'))
        GROUP BY stage, course, question_type, knowledge_tag
        ORDER BY stage, course, question_type, total DESC
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query).mappings().all()
    counts = [
        {
            "stage": str(row["stage"]),
            "course": str(row["course"]),
            "question_type": str(row["question_type"]),
            "type_label": TYPE_LABELS.get(str(row["question_type"]), str(row["question_type"])),
            "knowledge_tag": str(row["knowledge_tag"]),
            "total": int(row["total"]),
        }
        for row in rows
    ]
    return {"types": TYPE_LABELS, "counts": counts}


def _build_question_filters(
    *,
    stage: str | None,
    course: str | None,
    knowledge_tag: str | None,
    question_type: str | None,
    exclude_ids: list[int] | None = None,
) -> tuple[str, dict[str, Any]]:
    filters: list[str] = ["q.deleted_at IS NULL"]
    params: dict[str, Any] = {}
    if stage:
        filters.append("q.stage = :stage")
        params["stage"] = stage
    if course:
        filters.append("q.course = :course")
        params["course"] = course
    if knowledge_tag:
        filters.append("(q.knowledge_tag = :knowledge_tag OR q.fine_tag = :knowledge_tag)")
        params["knowledge_tag"] = knowledge_tag
    if question_type:
        filters.append("q.question_type = :question_type")
        params["question_type"] = question_type
    filters.append("q.question_text NOT LIKE :template_placeholder")
    params["template_placeholder"] = "%□%"
    if exclude_ids:
        placeholders = []
        for index, question_id in enumerate(exclude_ids):
            key = f"exclude_{index}"
            placeholders.append(f":{key}")
            params[key] = question_id
        filters.append(f"q.id NOT IN ({', '.join(placeholders)})")
    return ("WHERE " + " AND ".join(filters)) if filters else "", params


def _random_questions_sync(
    *,
    stage: str | None,
    course: str | None,
    knowledge_tag: str | None,
    question_type: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    attempts = [
        {"stage": stage, "course": course, "knowledge_tag": knowledge_tag, "question_type": question_type},
        {"stage": stage, "course": course, "knowledge_tag": None, "question_type": question_type},
        {"stage": stage, "course": course, "knowledge_tag": None, "question_type": None},
        {"stage": stage, "course": None, "knowledge_tag": None, "question_type": question_type},
        {"stage": None, "course": None, "knowledge_tag": None, "question_type": question_type},
        {"stage": None, "course": None, "knowledge_tag": None, "question_type": None},
    ]
    seen: set[tuple[Any, ...]] = set()
    with SessionLocal() as db:
        for attempt in attempts:
            key = tuple(attempt.items())
            if key in seen:
                continue
            seen.add(key)
            where_clause, params = _build_question_filters(**attempt)
            params["limit"] = limit
            source_filter = """(
              q.source_question_no LIKE 'CURATED-%'
              OR q.source_question_no LIKE 'BACHELOR-CN-%'
              OR (q.created_by IS NOT NULL AND q.publish_status='published' AND q.visibility='public')
            )"""
            if where_clause:
                where_clause = f"{where_clause} AND {source_filter}"
            else:
                where_clause = f"WHERE {source_filter}"
            query = text(
                f"""
                SELECT {_question_select_sql()}
                FROM questions AS q
                JOIN source_attributions AS s ON s.id = q.source_id
                {where_clause}
                ORDER BY RAND()
                LIMIT :limit
                """
            )
            rows = db.execute(query, params).mappings().all()
            if rows:
                return [_row_to_question(row) for row in rows]
    return []


def _get_question_sync(question_id: int, *, allow_private: bool = False) -> dict[str, Any] | None:
    query = text(
        f"""
        SELECT {_question_select_sql()}
        FROM questions AS q
        JOIN source_attributions AS s ON s.id = q.source_id
        WHERE q.id = :question_id
          AND q.deleted_at IS NULL
          AND (
            q.created_by IS NULL
            OR :allow_private=1
            OR (q.publish_status='published' AND q.visibility='public')
          )
        LIMIT 1
        """
    )
    with SessionLocal() as db:
        row = db.execute(
            query,
            {"question_id": question_id, "allow_private": 1 if allow_private else 0},
        ).mappings().first()
    return _row_to_question(row, include_answer=True) if row else None


def _assessment_question_rows(db: Any, assessment_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            f"""
            SELECT {_question_select_sql()}, aq.sort_order, aq.practice_record_id,
                   pr.selected_answer AS attempt_selected_answer,
                   pr.answer_text AS attempt_answer_text,
                   pr.is_correct AS attempt_is_correct,
                   pr.score AS attempt_score,
                   pr.review_status AS attempt_review_status
            FROM assessment_session_questions AS aq
            JOIN questions AS q ON q.id = aq.question_id
            JOIN source_attributions AS s ON s.id = q.source_id
            LEFT JOIN practice_records AS pr ON pr.id = aq.practice_record_id
            WHERE aq.assessment_id = :assessment_id
            ORDER BY aq.sort_order
            """
        ),
        {"assessment_id": assessment_id},
    ).mappings().all()
    return [dict(row) for row in rows]


def _assessment_payload(db: Any, session: Any) -> dict[str, Any]:
    session_data = dict(session)
    rows = _assessment_question_rows(db, int(session_data["id"]))
    answered = sum(1 for row in rows if row.get("practice_record_id") is not None)
    questions = []
    for row in rows:
        sort_order = int(row.pop("sort_order"))
        practice_record_id = row.pop("practice_record_id", None)
        attempt = None
        if practice_record_id is not None:
            attempt_score = row.pop("attempt_score", None)
            attempt = {
                "selected_answer": row.pop("attempt_selected_answer", None),
                "answer_text": row.pop("attempt_answer_text", None),
                "is_correct": row.pop("attempt_is_correct", None),
                "score": float(attempt_score) if attempt_score is not None else None,
                "review_status": row.pop("attempt_review_status", None),
                "correct_answer": row.get("correct_answer"),
                "standard_answer": row.get("standard_answer"),
                "analysis_text": row.get("analysis_text"),
                "key_steps": _parse_json_list(row.get("key_steps")),
                "common_errors": _parse_json_list(row.get("common_errors")),
            }
        else:
            for key in (
                "attempt_selected_answer",
                "attempt_answer_text",
                "attempt_is_correct",
                "attempt_score",
                "attempt_review_status",
            ):
                row.pop(key, None)
        question = _row_to_question(row)
        question["sort_order"] = sort_order
        question["answered"] = practice_record_id is not None
        question["attempt"] = attempt
        questions.append(question)
    return {
        "task_id": str(session_data["task_id"]),
        "mode": "assessment",
        "title": "数学基础首测",
        "stage": str(session_data["stage"]),
        "status": str(session_data["status"]),
        "question_count": int(session_data["question_count"]),
        "answered_count": answered,
        "started_at": _json_safe(session_data.get("started_at")),
        "completed_at": _json_safe(session_data.get("completed_at")),
        "questions": questions,
        "report": {
            **_parse_json_object(session_data.get("summary_json")),
            "plan": _parse_json_object(session_data.get("plan_json")),
        }
        if session_data.get("summary_json")
        else None,
    }


def _pick_balanced_assessment_questions(db: Any, stage: str, limit: int) -> list[int]:
    type_cycle = ["choice", "blank", "calculation", "proof", "comprehensive"]
    type_weights: list[str] = []
    while len(type_weights) < limit:
        type_weights.extend(type_cycle)
    if limit >= 10:
        # A second choice/calculation pass keeps larger tests practical without dropping proof coverage.
        type_weights = [
            "choice", "blank", "calculation", "proof", "comprehensive",
            "choice", "calculation", "blank", "proof", "comprehensive",
        ] + type_weights
    selected: list[int] = []

    for question_type in type_weights[:limit]:
        row = db.execute(
            text(
                """
                SELECT q.id
                FROM questions AS q
                WHERE q.stage = :stage
                  AND q.question_type = :question_type
                  AND (q.source_question_no LIKE 'CURATED-%' OR q.source_question_no LIKE 'BACHELOR-CN-%')
                  AND q.question_text NOT LIKE :placeholder
                  AND q.id NOT IN (
                    SELECT aq.question_id
                    FROM assessment_session_questions AS aq
                    JOIN assessment_sessions AS a ON a.id = aq.assessment_id
                    WHERE a.stage = :stage
                  )
                ORDER BY RAND()
                LIMIT 1
                """
            ),
            {"stage": stage, "question_type": question_type, "placeholder": "%□%"},
        ).first()
        if not row:
            row = db.execute(
                text(
                    """
                    SELECT q.id
                    FROM questions AS q
                    WHERE q.stage = :stage
                      AND q.question_type = :question_type
                      AND (q.source_question_no LIKE 'CURATED-%' OR q.source_question_no LIKE 'BACHELOR-CN-%')
                      AND q.question_text NOT LIKE :placeholder
                    ORDER BY RAND()
                    LIMIT 1
                    """
                ),
                {"stage": stage, "question_type": question_type, "placeholder": "%□%"},
            ).first()
        if row and int(row[0]) not in selected:
            selected.append(int(row[0]))

    if len(selected) < limit:
        params: dict[str, Any] = {"stage": stage, "limit": limit - len(selected), "placeholder": "%□%"}
        exclusion = ""
        if selected:
            keys = []
            for index, question_id in enumerate(selected):
                key = f"selected_{index}"
                params[key] = question_id
                keys.append(f":{key}")
            exclusion = f"AND q.id NOT IN ({', '.join(keys)})"
        rows = db.execute(
            text(
                f"""
                SELECT q.id
                FROM questions AS q
                WHERE q.stage = :stage
                  AND (q.source_question_no LIKE 'CURATED-%' OR q.source_question_no LIKE 'BACHELOR-CN-%')
                  AND q.question_text NOT LIKE :placeholder
                  {exclusion}
                ORDER BY RAND()
                LIMIT :limit
                """
            ),
            params,
        ).all()
        selected.extend(int(row[0]) for row in rows)
    return selected[:limit]


def _start_assessment_sync(payload: AssessmentStartRequest) -> dict[str, Any]:
    with SessionLocal() as db:
        if not _get_user_exists(db, payload.user_id):
            raise HTTPException(status_code=404, detail="请先注册或登录后再开始首测。")
        if payload.restart:
            db.execute(
                text("UPDATE assessment_sessions SET status = 'abandoned' WHERE user_id = :user_id AND status = 'in_progress'"),
                {"user_id": payload.user_id},
            )
        else:
            existing = db.execute(
                text(
                    """
                    SELECT * FROM assessment_sessions
                    WHERE user_id = :user_id AND status = 'in_progress'
                    ORDER BY started_at DESC LIMIT 1
                    """
                ),
                {"user_id": payload.user_id},
            ).mappings().first()
            if existing:
                return _assessment_payload(db, existing)

        stage = payload.stage or db.execute(
            text("SELECT current_stage FROM users WHERE id = :user_id"), {"user_id": payload.user_id}
        ).scalar() or "大一"
        question_ids = _pick_balanced_assessment_questions(db, str(stage), payload.limit)
        if len(question_ids) < payload.limit:
            raise HTTPException(status_code=409, detail=f"{stage}中文首测题暂时不足，请先补充题库。")

        task_id = str(uuid.uuid4())
        result = db.execute(
            text(
                """
                INSERT INTO assessment_sessions (task_id, user_id, stage, question_count)
                VALUES (:task_id, :user_id, :stage, :question_count)
                """
            ),
            {"task_id": task_id, "user_id": payload.user_id, "stage": stage, "question_count": len(question_ids)},
        )
        assessment_id = int(result.lastrowid)
        for sort_order, question_id in enumerate(question_ids, start=1):
            db.execute(
                text(
                    """
                    INSERT INTO assessment_session_questions (assessment_id, question_id, sort_order)
                    VALUES (:assessment_id, :question_id, :sort_order)
                    """
                ),
                {"assessment_id": assessment_id, "question_id": question_id, "sort_order": sort_order},
            )
        db.commit()
        session = db.execute(
            text("SELECT * FROM assessment_sessions WHERE id = :assessment_id"), {"assessment_id": assessment_id}
        ).mappings().one()
        return _assessment_payload(db, session)


def _tokenize_answer(text_value: str) -> set[str]:
    return {
        token.lower()
        for token in re.split(r"[\s,.;:，。；：、()（）\\[\\]{}<>《》\"'“”]+", text_value)
        if len(token.strip()) >= 2
    }


def _normalize_math_answer(text_value: str) -> str:
    normalized = str(text_value or "").strip().lower()
    normalized = re.sub(r"^(?:答案|答)\s*[:：]\s*", "", normalized)
    replacements = {
        "，": ",",
        "；": ";",
        "（": "(",
        "）": ")",
        "−": "-",
        "－": "-",
        "×": "*",
        "π": "pi",
        "√": "sqrt",
        "\\left": "",
        "\\right": "",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return re.sub(r"[\s。.;；]+", "", normalized)


def _score_subjective(
    answer_text: str,
    question: dict[str, Any],
    question_type: str,
) -> tuple[bool, float]:
    answer_text = answer_text.strip()
    if not answer_text:
        return False, 0.0

    normalized_answer = _normalize_math_answer(answer_text)
    normalized_standard = _normalize_math_answer(question.get("standard_answer") or "")
    if normalized_answer and normalized_standard and normalized_answer == normalized_standard:
        return True, 100.0

    if question_type == "blank":
        return False, 0.0

    key_text = " ".join(
        [
            question.get("standard_answer") or "",
            " ".join(question.get("key_steps") or []),
            question.get("knowledge_tag") or "",
            question.get("fine_tag") or "",
        ]
    )
    expected = _tokenize_answer(key_text)
    actual = _tokenize_answer(answer_text)
    if not expected:
        score = 70.0 if len(answer_text) >= 20 else 0.0
        return score >= 60, score

    overlap = len(expected & actual)
    ratio = overlap / max(len(expected), 1)
    length_bonus = min(len(answer_text) / 180, 0.25)
    score = max(30.0, min(100.0, (ratio * 90) + (length_bonus * 100)))
    return score >= 60, round(score, 2)


def _validate_attachment_ids(db: Any, user_id: int, attachment_ids: list[int]) -> list[int]:
    unique_ids = list(dict.fromkeys(int(item) for item in attachment_ids))
    if len(unique_ids) != len(attachment_ids) or len(unique_ids) > 5:
        raise HTTPException(status_code=422, detail="作答图片无效，每题最多绑定 5 张不同图片。")
    if not unique_ids:
        return []

    placeholders = ", ".join(f":attachment_{index}" for index in range(len(unique_ids)))
    params = {f"attachment_{index}": file_id for index, file_id in enumerate(unique_ids)}
    params["user_id"] = user_id
    rows = db.execute(
        text(
            f"""
            SELECT uf.id
            FROM uploaded_files AS uf
            LEFT JOIN answer_attachments AS aa ON aa.uploaded_file_id = uf.id
            WHERE uf.user_id = :user_id
              AND uf.id IN ({placeholders})
              AND aa.id IS NULL
            """
        ),
        params,
    ).all()
    valid_ids = {int(row[0]) for row in rows}
    if valid_ids != set(unique_ids):
        raise HTTPException(status_code=409, detail="部分图片不存在、并非当前用户上传，或已经提交过。")
    return unique_ids


def _validate_assessment_question(db: Any, payload: AnswerSubmissionRequest) -> int | None:
    if payload.practice_mode != "assessment":
        return None
    row = db.execute(
        text(
            """
            SELECT aq.id
            FROM assessment_sessions AS a
            JOIN assessment_session_questions AS aq ON aq.assessment_id = a.id
            WHERE a.task_id = :task_id
              AND a.user_id = :user_id
              AND a.status = 'in_progress'
              AND aq.question_id = :question_id
              AND aq.practice_record_id IS NULL
            LIMIT 1
            """
        ),
        {"task_id": payload.task_id, "user_id": payload.user_id, "question_id": payload.question_id},
    ).first()
    if not row:
        raise HTTPException(status_code=409, detail="该首测题目已提交，或首测任务已经结束。")
    return int(row[0])


def _submit_answer_sync(payload: AnswerSubmissionRequest) -> dict[str, Any]:
    question = _get_question_sync(payload.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在。")

    question_type = str(question["question_type"])
    selected = (payload.selected_answer or "").strip().upper()
    answer_text = (payload.answer_text or "").strip()
    if question_type == "choice" and not selected:
        raise HTTPException(status_code=422, detail="请选择一个答案后再提交。")
    if question_type != "choice" and not answer_text and not payload.attachment_ids:
        raise HTTPException(status_code=422, detail="请填写答案，或上传作答图片后再提交。")

    has_images = bool(payload.attachment_ids)
    pending_review = has_images and question_type != "choice"
    if pending_review:
        is_correct = None
        score = None
    elif question_type == "choice":
        correct_answer = str(question.get("correct_answer") or "").strip().upper()
        is_correct = bool(selected and selected == correct_answer)
        score = 100.0 if is_correct else 0.0
    else:
        is_correct, score = _score_subjective(answer_text, question, question_type)

    mistake_tags = [] if is_correct is not False else (question.get("mistake_tags") or question.get("common_errors") or ["概念未掌握"])

    insert_query = text(
        """
        INSERT INTO practice_records (
          task_id, user_id, question_id, selected_answer, answer_text, is_correct,
          score, mistake_tags, time_spent_seconds, practice_mode, review_status
        )
        VALUES (
          :task_id, :user_id, :question_id, :selected_answer, :answer_text, :is_correct,
          :score, :mistake_tags, :time_spent_seconds, :practice_mode, :review_status
        )
        """
    )
    try:
        with SessionLocal() as db:
            if not _get_user_exists(db, payload.user_id):
                raise HTTPException(status_code=404, detail="请先注册或登录后再提交做题记录。")
            attachment_ids = _validate_attachment_ids(db, payload.user_id, payload.attachment_ids)
            assessment_question_id = _validate_assessment_question(db, payload)
            insert_result = db.execute(
                insert_query,
                {
                    "task_id": payload.task_id,
                    "user_id": payload.user_id,
                    "question_id": payload.question_id,
                    "selected_answer": selected or None,
                    "answer_text": answer_text or None,
                    "is_correct": None if is_correct is None else (1 if is_correct else 0),
                    "score": score,
                    "mistake_tags": json.dumps(mistake_tags, ensure_ascii=False),
                    "time_spent_seconds": payload.time_spent_seconds,
                    "practice_mode": payload.practice_mode,
                    "review_status": "pending" if pending_review else "auto_graded",
                },
            )
            record_id = int(insert_result.lastrowid)
            for sort_order, file_id in enumerate(attachment_ids, start=1):
                db.execute(
                    text(
                        """
                        INSERT INTO answer_attachments (practice_record_id, uploaded_file_id, sort_order)
                        VALUES (:record_id, :file_id, :sort_order)
                        """
                    ),
                    {"record_id": record_id, "file_id": file_id, "sort_order": sort_order},
                )
            if assessment_question_id is not None:
                db.execute(
                    text(
                        """
                        UPDATE assessment_session_questions
                        SET practice_record_id = :record_id, answered_at = CURRENT_TIMESTAMP
                        WHERE id = :assessment_question_id
                        """
                    ),
                    {"record_id": record_id, "assessment_question_id": assessment_question_id},
                )
            db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="做题记录保存失败，请检查数据库连接。") from exc

    next_items = _random_questions_sync(
        stage=question.get("stage"),
        course=question.get("course"),
        knowledge_tag=question.get("knowledge_tag"),
        question_type=None,
        limit=3,
    )
    response = {
        "task_id": payload.task_id,
        "question_id": payload.question_id,
        "is_correct": is_correct,
        "score": score,
        "review_status": "pending" if pending_review else "auto_graded",
        "pending_review": pending_review,
        "attachment_count": len(payload.attachment_ids),
        "correct_answer": question.get("correct_answer"),
        "standard_answer": question.get("standard_answer"),
        "analysis_text": question.get("analysis_text"),
        "key_steps": question.get("key_steps"),
        "common_errors": question.get("common_errors"),
        "mistake_tags": mistake_tags,
        "next_recommendation": {
            "title": f"{question.get('fine_tag') or question.get('knowledge_tag')} 巩固练习",
            "stage": question.get("stage"),
            "course": question.get("course"),
            "knowledge_tag": question.get("knowledge_tag"),
            "questions": next_items,
        },
    }
    if payload.practice_mode == "assessment":
        assessment_state = _assessment_after_submit_sync(payload.user_id, payload.task_id)
        response.update(assessment_state)
    return response


def _build_assessment_report_sync(user_id: int, task_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        session = db.execute(
            text(
                """
                SELECT id, stage, question_count
                FROM assessment_sessions
                WHERE task_id = :task_id AND user_id = :user_id
                LIMIT 1
                """
            ),
            {"task_id": task_id, "user_id": user_id},
        ).mappings().first()
        if not session:
            raise HTTPException(status_code=404, detail="首测任务不存在。")
        rows = db.execute(
            text(
                """
                SELECT
                  q.course, q.knowledge_tag, q.fine_tag, q.question_type,
                  pr.is_correct, pr.score, pr.review_status, pr.time_spent_seconds
                FROM assessment_session_questions AS aq
                JOIN questions AS q ON q.id = aq.question_id
                LEFT JOIN practice_records AS pr ON pr.id = aq.practice_record_id
                WHERE aq.assessment_id = :assessment_id
                ORDER BY aq.sort_order
                """
            ),
            {"assessment_id": int(session["id"])},
        ).mappings().all()

    graded = [row for row in rows if row["is_correct"] is not None]
    correct_count = sum(1 for row in graded if bool(row["is_correct"]))
    pending_count = sum(1 for row in rows if str(row.get("review_status") or "") == "pending")
    accuracy = round(correct_count / len(graded) * 100) if graded else 0
    total_seconds = sum(int(row.get("time_spent_seconds") or 0) for row in rows)

    knowledge: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in graded:
        key = (str(row["course"]), str(row["knowledge_tag"]), str(row["fine_tag"]))
        item = knowledge.setdefault(
            key,
            {
                "course": key[0],
                "knowledge_tag": key[1],
                "fine_tag": key[2],
                "total": 0,
                "correct": 0,
                "time_spent_seconds": 0,
            },
        )
        item["total"] += 1
        item["correct"] += int(bool(row["is_correct"]))
        item["time_spent_seconds"] += int(row.get("time_spent_seconds") or 0)

    scored_points = []
    for item in knowledge.values():
        point_score = round(item["correct"] / max(item["total"], 1) * 100)
        scored_points.append(
            {
                **item,
                "score": point_score,
                "avg_time_seconds": round(item["time_spent_seconds"] / max(item["total"], 1)),
            }
        )
    weak_points = sorted(scored_points, key=lambda item: (item["score"], -item["total"]))[:3]
    strengths = sorted(scored_points, key=lambda item: (-item["score"], -item["total"]))[:2]
    focus = weak_points[0] if weak_points else {
        "course": "高等数学上",
        "knowledge_tag": "基础概念",
        "fine_tag": "基础概念",
        "score": accuracy,
    }

    second_focus = weak_points[1] if len(weak_points) > 1 else focus
    weekly_plan = [
        {"day": "第 1 天", "task": f"回顾「{focus['fine_tag']}」定义与例题", "minutes": 45},
        {"day": "第 2 天", "task": f"完成「{focus['fine_tag']}」基础题 8 题", "minutes": 50},
        {"day": "第 3 天", "task": f"整理「{focus['knowledge_tag']}」错因笔记", "minutes": 35},
        {"day": "第 4 天", "task": f"学习「{second_focus['fine_tag']}」关键方法", "minutes": 45},
        {"day": "第 5 天", "task": "完成一组计算与证明混合练习", "minutes": 60},
        {"day": "第 6 天", "task": "回炉本次首测错题", "minutes": 40},
        {"day": "第 7 天", "task": "完成 10 题阶段复测并复盘", "minutes": 50},
    ]

    pending_note = f"，另有 {pending_count} 道图片作答待教师复核" if pending_count else ""
    summary = (
        f"本次首测完成 {len(rows)} 题，已自动评分 {len(graded)} 题，正确 {correct_count} 题，"
        f"自动评分正确率 {accuracy}%{pending_note}。"
    )
    xiaoluo_message = (
        f"首测完成，我已经看过你的作答。{summary}\n\n"
        f"当前优先补强：{focus['course']} · {focus['fine_tag']}（掌握度约 {focus['score']}%）。\n"
        f"接下来 7 天先走“概念回顾 → 基础题 → 错因整理 → 混合复测”这条路线。"
        + (" 图片题我先标成待复核，教师评分后再更新你的诊断。" if pending_count else "")
    )
    return {
        "task_id": task_id,
        "title": "基础首测分析",
        "stage": str(session["stage"]),
        "question_count": int(session["question_count"]),
        "graded_count": len(graded),
        "correct_count": correct_count,
        "pending_review_count": pending_count,
        "accuracy": accuracy,
        "duration_seconds": total_seconds,
        "summary": summary,
        "weak_points": weak_points,
        "strengths": strengths,
        "plan": {
            "headline": f"先补强 {focus['fine_tag']}，再进行阶段复测",
            "focus_course": focus["course"],
            "focus_knowledge": focus["knowledge_tag"],
            "weekly_plan": weekly_plan,
            "next_action": {
                "label": f"练习 {focus['fine_tag']}",
                "path": "/practice",
                "query": {
                    "mode": "daily",
                    "course": focus["course"],
                    "knowledge_tag": focus["knowledge_tag"],
                    "limit": 8,
                },
            },
        },
        "xiaoluo_message": xiaoluo_message,
    }


def _assessment_after_submit_sync(user_id: int, task_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        state = db.execute(
            text(
                """
                SELECT
                  a.id, a.status, a.question_count, a.summary_json, a.plan_json,
                  SUM(CASE WHEN aq.practice_record_id IS NOT NULL THEN 1 ELSE 0 END) AS answered_count
                FROM assessment_sessions AS a
                JOIN assessment_session_questions AS aq ON aq.assessment_id = a.id
                WHERE a.task_id = :task_id AND a.user_id = :user_id
                GROUP BY a.id, a.status, a.question_count, a.summary_json, a.plan_json
                LIMIT 1
                """
            ),
            {"task_id": task_id, "user_id": user_id},
        ).mappings().first()
    if not state:
        raise HTTPException(status_code=404, detail="首测任务不存在。")

    answered_count = int(state["answered_count"] or 0)
    question_count = int(state["question_count"])
    if answered_count < question_count:
        return {
            "assessment_complete": False,
            "assessment_progress": {"answered": answered_count, "total": question_count},
        }

    if str(state["status"]) == "completed" and state.get("summary_json"):
        report = _parse_json_object(state["summary_json"])
        report["plan"] = _parse_json_object(state["plan_json"])
        return {
            "assessment_complete": True,
            "assessment_progress": {"answered": answered_count, "total": question_count},
            "assessment_report": report,
        }

    report = _build_assessment_report_sync(user_id, task_id)
    session_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.execute(
            text(
                """
                UPDATE assessment_sessions
                SET status = 'completed', summary_json = :summary_json, plan_json = :plan_json,
                    completed_at = CURRENT_TIMESTAMP
                WHERE task_id = :task_id AND user_id = :user_id
                """
            ),
            {
                "summary_json": json.dumps({key: value for key, value in report.items() if key != "plan"}, ensure_ascii=False),
                "plan_json": json.dumps(report["plan"], ensure_ascii=False),
                "task_id": task_id,
                "user_id": user_id,
            },
        )
        db.execute(
            text(
                """
                INSERT INTO learning_plans (user_id, stage, course, plan_name, plan_json)
                VALUES (:user_id, :stage, :course, :plan_name, :plan_json)
                """
            ),
            {
                "user_id": user_id,
                "stage": report["stage"],
                "course": report["plan"]["focus_course"],
                "plan_name": "首测后 7 天学习计划",
                "plan_json": json.dumps(report["plan"], ensure_ascii=False),
            },
        )
        db.execute(
            text(
                """
                INSERT INTO chat_messages (session_id, user_id, role, content)
                VALUES (:session_id, :user_id, 'assistant', :content)
                """
            ),
            {"session_id": session_id, "user_id": user_id, "content": report["xiaoluo_message"]},
        )
        db.commit()
    report["chat_session_id"] = session_id
    return {
        "assessment_complete": True,
        "assessment_progress": {"answered": answered_count, "total": question_count},
        "assessment_report": report,
    }


def _recent_records_sync(user_id: int, limit: int = 50) -> list[dict[str, Any]]:
    query = text(
        """
        SELECT
          pr.id,
          pr.task_id,
          pr.question_id,
          pr.selected_answer,
          pr.answer_text,
          pr.is_correct,
          pr.score,
          pr.mistake_tags AS record_mistake_tags,
          pr.time_spent_seconds,
          pr.practice_mode,
          pr.answered_at,
          q.stage,
          q.course,
          q.knowledge_tag,
          q.fine_tag,
          q.question_type,
          q.difficulty
        FROM practice_records AS pr
        JOIN questions AS q ON q.id = pr.question_id
        WHERE pr.user_id = :user_id
        ORDER BY pr.answered_at DESC, pr.id DESC
        LIMIT :limit
        """
    )
    try:
        with SessionLocal() as db:
            rows = db.execute(query, {"user_id": user_id, "limit": limit}).mappings().all()
    except SQLAlchemyError:
        return []

    records = []
    for row in rows:
        item = dict(row)
        item["answered_at"] = _json_safe(item.get("answered_at"))
        item["mistake_tags"] = _parse_json_list(item.pop("record_mistake_tags", None))
        records.append(item)
    return records


def _diagnose_sync(user_id: int) -> dict[str, Any]:
    all_records = _recent_records_sync(user_id, 200)
    records = [record for record in all_records if record.get("is_correct") is not None]
    if not all_records:
        return {
            "user_id": user_id,
            "recent_record_count": 0,
            "summary": "暂无做题记录。建议先完成一次首测，系统会根据课程和知识点正确率生成个性化规划。",
            "course_scores": [],
            "weak_points": [],
            "radar": [],
        }
    if not records:
        return {
            "user_id": user_id,
            "recent_record_count": len(all_records),
            "graded_record_count": 0,
            "pending_review_count": len(all_records),
            "summary": "作答图片已提交，正在等待教师复核。复核完成后系统会生成薄弱点和学习计划。",
            "course_scores": [],
            "weak_points": [],
            "radar": [],
        }

    stats: dict[str, dict[str, Any]] = {}
    knowledge_stats: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in records:
        course = str(record["course"])
        stats.setdefault(course, {"course": course, "stage": record["stage"], "total": 0, "correct": 0})
        stats[course]["total"] += 1
        stats[course]["correct"] += int(bool(record["is_correct"]))

        key = (str(record["stage"]), course, str(record["knowledge_tag"]))
        knowledge_stats.setdefault(
            key,
            {
                "stage": str(record["stage"]),
                "course": course,
                "knowledge_tag": str(record["knowledge_tag"]),
                "fine_tag": str(record["fine_tag"]),
                "total": 0,
                "correct": 0,
                "time_spent_seconds": 0,
            },
        )
        knowledge_stats[key]["total"] += 1
        knowledge_stats[key]["correct"] += int(bool(record["is_correct"]))
        knowledge_stats[key]["time_spent_seconds"] += int(record.get("time_spent_seconds") or 0)

    course_scores = []
    for item in stats.values():
        score = round(item["correct"] / item["total"] * 100)
        course_scores.append({**item, "score": score, "accuracy": score, "weak": score < 65})
    course_scores.sort(key=lambda item: (item["score"], -item["total"]))

    weak_points = []
    for item in knowledge_stats.values():
        score = round(item["correct"] / item["total"] * 100)
        weak_points.append(
            {
                "stage": item["stage"],
                "course": item["course"],
                "knowledge_tag": item["knowledge_tag"],
                "fine_tag": item["fine_tag"],
                "score": score,
                "total": item["total"],
                "avg_time_seconds": round(item["time_spent_seconds"] / max(item["total"], 1)),
                "reason": "正确率偏低" if score < 60 else "耗时较长或需要继续巩固",
            }
        )
    weak_points.sort(key=lambda item: (item["score"], -item["total"]))
    weakest = weak_points[:3]

    radar_groups = {
        "高等数学": ["高等数学上", "高等数学下", "数学分析选讲"],
        "线性代数": ["线性代数上", "线性代数下", "高等代数"],
        "概率统计": ["概率论与数理统计"],
        "方程与分析": ["级数与常微分方程", "实变函数", "复变函数"],
        "综合建模": ["数学建模与综合专题", "证明方法入门"],
    }
    radar = []
    for label, courses in radar_groups.items():
        matched = [item for item in course_scores if item["course"] in courses]
        if matched:
            score = round(sum(item["score"] for item in matched) / len(matched))
            radar.append({"name": label, "score": score})

    return {
        "user_id": user_id,
        "recent_record_count": len(records),
        "graded_record_count": len(records),
        "pending_review_count": len(all_records) - len(records),
        "summary": (
            f"已分析最近 {len(records)} 条记录，当前最需要补强：{weakest[0]['course']} - {weakest[0]['knowledge_tag']}。"
            if weakest
            else f"已分析最近 {len(records)} 条记录，暂未发现明显薄弱点。"
        ),
        "course_scores": course_scores,
        "weak_points": weakest,
        "radar": radar,
    }


def _recommend_sync(user_id: int, limit: int, stage: str | None, course: str | None) -> list[dict[str, Any]]:
    diagnosis = _diagnose_sync(user_id)
    if int(diagnosis.get("recent_record_count") or 0) == 0:
        return []
    weak_points = diagnosis.get("weak_points") or []
    tasks = []
    for weak in weak_points[:5]:
        task_stage = stage or weak.get("stage")
        task_course = course or weak.get("course")
        tag = weak.get("knowledge_tag")
        questions = _random_questions_sync(
            stage=task_stage,
            course=task_course,
            knowledge_tag=tag,
            question_type=None,
            limit=min(10, max(3, math.ceil(limit / 2))),
        )
        if not questions:
            continue
        tasks.append(
            {
                "title": f"{weak.get('fine_tag') or tag} 巩固训练",
                "stage": task_stage,
                "course": task_course,
                "knowledge_tag": tag,
                "difficulty": round(sum(int(q["difficulty"]) for q in questions) / len(questions), 1),
                "question_count": len(questions),
                "reason": weak.get("reason", "根据薄弱点推荐"),
                "questions": questions,
            }
        )
    return tasks[:limit]


def _study_roadmap_sync(user_id: int) -> dict[str, Any]:
    stages = _stages_sync()
    diagnosis = _diagnose_sync(user_id)
    weak_points = diagnosis.get("weak_points") or []
    try:
        with SessionLocal() as db:
            saved_plan = db.execute(
                text(
                    """
                    SELECT plan_name, plan_json, updated_at
                    FROM learning_plans
                    WHERE user_id = :user_id
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """
                ),
                {"user_id": user_id},
            ).mappings().first()
    except SQLAlchemyError:
        saved_plan = None
    if saved_plan:
        plan_data = _parse_json_object(saved_plan["plan_json"])
        if plan_data.get("weekly_plan"):
            return {
                "user_id": user_id,
                "stages": stages,
                "priority": weak_points[:3],
                "weekly_plan": plan_data["weekly_plan"],
                "summary": plan_data.get("headline") or str(saved_plan["plan_name"]),
                "source": "assessment",
                "updated_at": _json_safe(saved_plan.get("updated_at")),
            }
    if int(diagnosis.get("recent_record_count") or 0) == 0 or not weak_points:
        return {
            "user_id": user_id,
            "stages": stages,
            "priority": [],
            "weekly_plan": [],
            "summary": "暂无做题记录。完成首测后，系统会按薄弱课程生成一周学习计划。",
        }
    focus = weak_points[0]
    weekly_plan = [
        {"day": "周一", "course": focus["course"], "task": f"{focus['knowledge_tag']} 概念回顾", "minutes": 90},
        {"day": "周二", "course": focus["course"], "task": "基础题组 + 错因标注", "minutes": 90},
        {"day": "周三", "course": focus["course"], "task": "计算题/证明题拆解", "minutes": 90},
        {"day": "周四", "course": "线性代数上", "task": "矩阵与向量空间复习", "minutes": 75},
        {"day": "周五", "course": "高等数学上", "task": "混合小测", "minutes": 90},
        {"day": "周六", "course": "综合", "task": "错题回炉与笔记整理", "minutes": 60},
        {"day": "周日", "course": "综合", "task": "休整或轻量复盘", "minutes": 30},
    ]
    return {
        "user_id": user_id,
        "stages": stages,
        "priority": weak_points[:3],
        "weekly_plan": weekly_plan,
        "summary": "学习路线按先修关系推进：基础概念先打牢，再进入计算技巧、证明方法和综合应用。",
    }


def _wrong_questions_sync(user_id: int, limit: int, offset: int) -> dict[str, Any]:
    query = text(
        f"""
        SELECT
          pr.id AS record_id,
          pr.task_id,
          pr.selected_answer,
          pr.answer_text,
          pr.score,
          pr.mistake_tags AS record_mistake_tags,
          pr.time_spent_seconds,
          pr.practice_mode,
          pr.answered_at,
          {_question_select_sql()}
        FROM practice_records AS pr
        JOIN questions AS q ON q.id = pr.question_id
        JOIN source_attributions AS s ON s.id = q.source_id
        WHERE pr.user_id = :user_id AND pr.is_correct = 0
        ORDER BY pr.answered_at DESC, pr.id DESC
        LIMIT :limit OFFSET :offset
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query, {"user_id": user_id, "limit": limit, "offset": offset}).mappings().all()
    items = []
    for row in rows:
        question = _row_to_question(row, include_answer=True)
        question.update(
            {
                "record_id": int(row["record_id"]),
                "task_id": str(row["task_id"]),
                "score": float(row["score"] or 0),
                "answered_at": _json_safe(row["answered_at"]),
                "record_mistake_tags": _parse_json_list(row["record_mistake_tags"]),
            }
        )
        items.append(question)
    return {"user_id": user_id, "items": items, "limit": limit, "offset": offset}


def _get_goal_sync(user_id: int) -> dict[str, Any]:
    query = text(
        """
        SELECT user_id, target_course, target_stage, weekly_hours, exam_date
        FROM user_goal_settings
        WHERE user_id = :user_id
        LIMIT 1
        """
    )
    with SessionLocal() as db:
        row = db.execute(query, {"user_id": user_id}).mappings().first()
    if not row:
        return {
            "user_id": user_id,
            "target_course": "高等数学上",
            "target_stage": "大一",
            "weekly_hours": 8.0,
            "exam_date": None,
            "remaining_days": None,
        }
    exam_date = row["exam_date"]
    remaining_days = max((exam_date - date.today()).days, 0) if exam_date else None
    return {
        "user_id": int(row["user_id"]),
        "target_course": str(row["target_course"]),
        "target_stage": str(row["target_stage"]),
        "weekly_hours": float(row["weekly_hours"]),
        "exam_date": exam_date.isoformat() if exam_date else None,
        "remaining_days": remaining_days,
    }


def _save_goal_sync(payload: GoalRequest) -> dict[str, Any]:
    query = text(
        """
        INSERT INTO user_goal_settings (user_id, target_course, target_stage, weekly_hours, exam_date)
        VALUES (:user_id, :target_course, :target_stage, :weekly_hours, :exam_date)
        ON DUPLICATE KEY UPDATE
          target_course = VALUES(target_course),
          target_stage = VALUES(target_stage),
          weekly_hours = VALUES(weekly_hours),
          exam_date = VALUES(exam_date),
          updated_at = CURRENT_TIMESTAMP
        """
    )
    try:
        with SessionLocal() as db:
            if not _get_user_exists(db, payload.user_id):
                raise HTTPException(status_code=404, detail="请先注册或登录后再设置学习目标。")
            db.execute(query, payload.model_dump())
            db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="学习目标保存失败，请检查数据库连接。") from exc
    return _get_goal_sync(payload.user_id)


def _ensure_side_feature_tables_sync() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS user_notes (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          user_id BIGINT UNSIGNED NOT NULL,
          title VARCHAR(160) NOT NULL,
          content TEXT NOT NULL,
          course VARCHAR(128) NULL,
          knowledge_tag VARCHAR(160) NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (id),
          KEY idx_user_notes_user_time (user_id, updated_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS user_notifications (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          user_id BIGINT UNSIGNED NULL,
          type VARCHAR(40) NOT NULL DEFAULT 'system',
          title VARCHAR(160) NOT NULL,
          content TEXT NOT NULL,
          is_read TINYINT(1) NOT NULL DEFAULT 0,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (id),
          KEY idx_user_notifications_user_time (user_id, is_read, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS learning_resources (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          stage VARCHAR(16) NOT NULL,
          course VARCHAR(128) NOT NULL,
          title VARCHAR(180) NOT NULL,
          resource_type VARCHAR(40) NOT NULL,
          description TEXT NOT NULL,
          url VARCHAR(512) NULL,
          difficulty TINYINT UNSIGNED NOT NULL DEFAULT 2,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (id),
          KEY idx_learning_resources_stage_course (stage, course),
          KEY idx_learning_resources_type (resource_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS note_attachments (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          note_id BIGINT UNSIGNED NOT NULL,
          uploaded_file_id BIGINT UNSIGNED NOT NULL,
          sort_order TINYINT UNSIGNED NOT NULL DEFAULT 1,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (id),
          UNIQUE KEY uk_note_attachments_file (uploaded_file_id),
          KEY idx_note_attachments_note (note_id, sort_order),
          CONSTRAINT fk_note_attachments_note
            FOREIGN KEY (note_id) REFERENCES user_notes (id)
            ON DELETE CASCADE ON UPDATE CASCADE,
          CONSTRAINT fk_note_attachments_file
            FOREIGN KEY (uploaded_file_id) REFERENCES uploaded_files (id)
            ON DELETE CASCADE ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
        """,
    ]
    try:
        with SessionLocal() as db:
            for statement in statements:
                db.execute(text(statement))
            db.commit()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="侧边功能数据表初始化失败，请检查 MySQL。") from exc


def _seed_side_feature_data_sync(user_id: int) -> None:
    _ensure_side_feature_tables_sync()
    resources = [
        ("大一", "高等数学上", "极限与连续速记讲义", "lecture", "梳理极限运算、等价无穷小、函数连续与间断点判断。", "/practice?course=高等数学上&knowledge_tag=极限与连续", 2),
        ("大一", "高等数学上", "导数应用专项练习", "practice", "覆盖切线、单调性、极值、微分中值定理的基础题组。", "/practice?course=高等数学上&knowledge_tag=导数", 2),
        ("大一", "线性代数上", "矩阵运算与逆矩阵", "lecture", "从矩阵乘法维度、行列式到逆矩阵条件的短讲义。", "/practice?course=线性代数上", 2),
        ("大二", "高等数学下", "多元函数微分路线", "roadmap", "偏导数、梯度、方向导数与条件极值的学习顺序。", "/roadmap", 3),
        ("大二", "概率论与数理统计", "随机变量与期望练习", "practice", "用离散分布和常见连续分布训练期望、方差与独立性。", "/practice?course=概率论与数理统计", 2),
        ("大二", "级数与常微分方程", "级数判别法清单", "lecture", "比较、比值、根值、交错级数和幂级数收敛半径。", "/practice?course=级数与常微分方程", 3),
        ("大三", "复变函数", "解析函数入门", "lecture", "复数运算、柯西-黎曼方程、解析函数与积分初步。", "/practice?course=复变函数", 3),
        ("大三", "数值分析", "误差与迭代方法", "practice", "训练舍入误差、二分法、牛顿法和线性方程组数值解法。", "/practice?course=数值分析", 3),
        ("大四", "数学建模与综合专题", "建模问题拆解模板", "project", "从变量、目标函数、约束条件到模型检验的完整框架。", "/practice?course=数学建模与综合专题", 3),
    ]
    try:
        with SessionLocal() as db:
            resource_count = db.execute(text("SELECT COUNT(*) FROM learning_resources")).scalar_one()
            if not resource_count:
                for stage, course, title, resource_type, description, url, difficulty in resources:
                    db.execute(
                        text(
                            """
                            INSERT INTO learning_resources
                              (stage, course, title, resource_type, description, url, difficulty)
                            VALUES
                              (:stage, :course, :title, :resource_type, :description, :url, :difficulty)
                            """
                        ),
                        {
                            "stage": stage,
                            "course": course,
                            "title": title,
                            "resource_type": resource_type,
                            "description": description,
                            "url": url,
                            "difficulty": difficulty,
                        },
                    )
            db.commit()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="侧边功能默认数据写入失败，请检查 MySQL。") from exc


def _messages_sync(user_id: int) -> dict[str, Any]:
    _ensure_side_feature_tables_sync()
    query = text(
        """
        SELECT id, type, title, content, is_read, created_at
        FROM user_notifications
        WHERE user_id = :user_id OR user_id IS NULL
        ORDER BY is_read ASC, created_at DESC, id DESC
        LIMIT 80
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query, {"user_id": user_id}).mappings().all()
    items = [
        {
            "id": int(row["id"]),
            "type": str(row["type"]),
            "title": str(row["title"]),
            "content": str(row["content"]),
            "is_read": bool(row["is_read"]),
            "created_at": _json_safe(row["created_at"]),
        }
        for row in rows
    ]
    return {"user_id": user_id, "unread_count": sum(1 for item in items if not item["is_read"]), "items": items}


def _profile_summary_sync(user_id: int) -> dict[str, Any]:
    _ensure_side_feature_tables_sync()
    with SessionLocal() as db:
        user_row = db.execute(
            text(
                """
                SELECT id, username, nickname, current_stage, created_at, last_login_at
                FROM users
                WHERE id = :user_id
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
    if not user_row:
        raise HTTPException(status_code=404, detail="用户不存在，请先登录。")

    records = _recent_records_sync(user_id, 200)
    answered = [record for record in records if record.get("is_correct") is not None]
    correct_count = sum(1 for record in answered if bool(record.get("is_correct")))
    accuracy = round(correct_count / len(answered) * 100, 1) if answered else 0.0
    total_seconds = sum(int(record.get("time_spent_seconds") or 0) for record in records)
    diagnosis = _diagnose_sync(user_id)
    goal = _get_goal_sync(user_id)
    recent_records = [
        {
            "question_id": int(record["question_id"]),
            "course": record["course"],
            "knowledge_tag": record["knowledge_tag"],
            "question_type": record["question_type"],
            "score": float(record.get("score") or 0),
            "is_correct": bool(record.get("is_correct")),
            "answered_at": record.get("answered_at"),
        }
        for record in records[:8]
    ]
    return {
        "user": {
            "id": int(user_row["id"]),
            "username": str(user_row["username"]),
            "nickname": user_row["nickname"] or user_row["username"],
            "current_stage": user_row["current_stage"] or goal["target_stage"],
            "created_at": _json_safe(user_row["created_at"]),
            "last_login_at": _json_safe(user_row["last_login_at"]),
        },
        "goal": goal,
        "stats": {
            "practice_count": len(records),
            "answered_count": len(answered),
            "correct_count": correct_count,
            "accuracy": accuracy,
            "study_hours": round(total_seconds / 3600, 1),
        },
        "weak_points": diagnosis.get("weak_points", [])[:5],
        "recent_records": recent_records,
    }


def _achievements_sync(user_id: int) -> dict[str, Any]:
    _ensure_side_feature_tables_sync()
    records = _recent_records_sync(user_id, 300)
    answered = [record for record in records if record.get("is_correct") is not None]
    correct_count = sum(1 for record in answered if bool(record.get("is_correct")))
    accuracy = round(correct_count / len(answered) * 100, 1) if answered else 0.0
    wrong_book_count = sum(1 for record in records if record.get("practice_mode") == "wrong_book")
    proof_count = sum(1 for record in records if record.get("question_type") == "proof")
    mock_count = sum(1 for record in records if record.get("practice_mode") == "mock")
    badges = [
        {"code": "first_step", "title": "启程", "description": "完成首道练习题。", "unlocked": len(records) >= 1, "progress": min(len(records), 1), "target": 1},
        {"code": "steady_learner", "title": "稳定推进", "description": "累计完成 3 道练习题。", "unlocked": len(records) >= 3, "progress": min(len(records), 3), "target": 3},
        {"code": "question_builder", "title": "题感建立", "description": "累计完成 20 道练习题。", "unlocked": len(records) >= 20, "progress": min(len(records), 20), "target": 20},
        {"code": "accurate_solver", "title": "准确解题", "description": "至少 10 题且正确率达到 80%。", "unlocked": len(answered) >= 10 and accuracy >= 80, "progress": int(accuracy), "target": 80},
        {"code": "wrong_book", "title": "错题回炉", "description": "完成一次错题本回炉练习。", "unlocked": wrong_book_count > 0, "progress": min(wrong_book_count, 1), "target": 1},
        {"code": "proof_beginner", "title": "证明入门", "description": "完成至少 1 道证明题。", "unlocked": proof_count > 0, "progress": min(proof_count, 1), "target": 1},
        {"code": "mock_exam", "title": "模拟演练", "description": "完成至少 1 次模拟考试题目。", "unlocked": mock_count > 0, "progress": min(mock_count, 1), "target": 1},
    ]
    return {
        "user_id": user_id,
        "stats": {"practice_count": len(records), "accuracy": accuracy, "correct_count": correct_count},
        "badges": badges,
    }


def _resources_sync(stage: str | None, course: str | None) -> dict[str, Any]:
    _seed_side_feature_data_sync(1)
    filters = []
    params: dict[str, Any] = {"limit": 80}
    if stage:
        filters.append("stage = :stage")
        params["stage"] = stage
    if course:
        filters.append("course = :course")
        params["course"] = course
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""
    query = text(
        f"""
        SELECT id, stage, course, title, resource_type, description, url, difficulty, created_at
        FROM learning_resources
        {where_clause}
        ORDER BY FIELD(stage, '大一', '大二', '大三', '大四'), course, difficulty, id
        LIMIT :limit
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query, params).mappings().all()
    return {
        "stage": stage,
        "course": course,
        "items": [
            {
                "id": int(row["id"]),
                "stage": row["stage"],
                "course": row["course"],
                "title": row["title"],
                "resource_type": row["resource_type"],
                "description": row["description"],
                "url": row["url"],
                "difficulty": int(row["difficulty"] or 1),
                "created_at": _json_safe(row["created_at"]),
            }
            for row in rows
        ],
    }


def _notes_sync(user_id: int) -> dict[str, Any]:
    _ensure_side_feature_tables_sync()
    query = text(
        """
        SELECT id, title, content, course, knowledge_tag, created_at, updated_at
        FROM user_notes
        WHERE user_id = :user_id
        ORDER BY updated_at DESC, id DESC
        LIMIT 100
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query, {"user_id": user_id}).mappings().all()
        note_ids = [int(row["id"]) for row in rows]
        attachment_rows = []
        if note_ids:
            placeholders = ", ".join(f":note_{index}" for index in range(len(note_ids)))
            params = {f"note_{index}": note_id for index, note_id in enumerate(note_ids)}
            attachment_rows = db.execute(
                text(
                    f"""
                    SELECT na.note_id, uf.id, uf.original_name, uf.mime_type, uf.size_bytes,
                           uf.width, uf.height, na.sort_order
                    FROM note_attachments AS na
                    JOIN uploaded_files AS uf ON uf.id = na.uploaded_file_id
                    WHERE na.note_id IN ({placeholders})
                    ORDER BY na.note_id, na.sort_order, na.id
                    """
                ),
                params,
            ).mappings().all()
    attachments_by_note: dict[int, list[dict[str, Any]]] = {note_id: [] for note_id in note_ids}
    for attachment in attachment_rows:
        file_id = int(attachment["id"])
        mime_type = str(attachment["mime_type"])
        attachments_by_note[int(attachment["note_id"])].append(
            {
                "id": file_id,
                "name": str(attachment["original_name"]),
                "mime_type": mime_type,
                "size_bytes": int(attachment["size_bytes"] or 0),
                "width": int(attachment["width"] or 0),
                "height": int(attachment["height"] or 0),
                "is_image": mime_type.startswith("image/"),
                "url": f"/api/files/{file_id}",
            }
        )
    return {
        "user_id": user_id,
        "items": [
            {
                "id": int(row["id"]),
                "title": row["title"],
                "content": row["content"],
                "course": row["course"],
                "knowledge_tag": row["knowledge_tag"],
                "attachments": attachments_by_note.get(int(row["id"]), []),
                "created_at": _json_safe(row["created_at"]),
                "updated_at": _json_safe(row["updated_at"]),
            }
            for row in rows
        ],
    }


def _validate_note_attachment_ids(
    db: Any,
    user_id: int,
    attachment_ids: list[int],
    note_id: int | None = None,
) -> list[int]:
    unique_ids = list(dict.fromkeys(int(file_id) for file_id in attachment_ids))
    if len(unique_ids) != len(attachment_ids) or len(unique_ids) > 10:
        raise HTTPException(status_code=422, detail="笔记附件不能重复，且最多保留 10 个。")
    if not unique_ids:
        return []
    placeholders = ", ".join(f":file_{index}" for index in range(len(unique_ids)))
    params: dict[str, Any] = {f"file_{index}": file_id for index, file_id in enumerate(unique_ids)}
    params.update({"user_id": user_id, "note_id": note_id or 0})
    rows = db.execute(
        text(
            f"""
            SELECT uf.id
            FROM uploaded_files AS uf
            LEFT JOIN answer_attachments AS aa ON aa.uploaded_file_id = uf.id
            LEFT JOIN question_attachments AS qa ON qa.uploaded_file_id = uf.id
            LEFT JOIN note_attachments AS na ON na.uploaded_file_id = uf.id
            WHERE uf.id IN ({placeholders}) AND uf.user_id = :user_id
              AND aa.id IS NULL AND qa.id IS NULL
              AND (na.id IS NULL OR na.note_id = :note_id)
            """
        ),
        params,
    ).scalars().all()
    if {int(file_id) for file_id in rows} != set(unique_ids):
        raise HTTPException(status_code=422, detail="部分附件不存在、已被使用，或不属于当前账号。")
    return unique_ids


def _sync_note_attachments(
    db: Any,
    note_id: int,
    user_id: int,
    attachment_ids: list[int],
) -> list[str]:
    requested = _validate_note_attachment_ids(db, user_id, attachment_ids, note_id)
    existing_rows = db.execute(
        text(
            """
            SELECT na.uploaded_file_id, uf.storage_key
            FROM note_attachments AS na
            JOIN uploaded_files AS uf ON uf.id = na.uploaded_file_id
            WHERE na.note_id = :note_id
            """
        ),
        {"note_id": note_id},
    ).mappings().all()
    existing = {int(row["uploaded_file_id"]): str(row["storage_key"]) for row in existing_rows}
    removed_ids = set(existing) - set(requested)
    removed_keys = [existing[file_id] for file_id in removed_ids]

    for file_id in removed_ids:
        db.execute(
            text("DELETE FROM note_attachments WHERE note_id = :note_id AND uploaded_file_id = :file_id"),
            {"note_id": note_id, "file_id": file_id},
        )
        db.execute(text("DELETE FROM uploaded_files WHERE id = :file_id"), {"file_id": file_id})
    for sort_order, file_id in enumerate(requested, start=1):
        if file_id in existing:
            db.execute(
                text(
                    """
                    UPDATE note_attachments SET sort_order = :sort_order
                    WHERE note_id = :note_id AND uploaded_file_id = :file_id
                    """
                ),
                {"note_id": note_id, "file_id": file_id, "sort_order": sort_order},
            )
        else:
            db.execute(
                text(
                    """
                    INSERT INTO note_attachments (note_id, uploaded_file_id, sort_order)
                    VALUES (:note_id, :file_id, :sort_order)
                    """
                ),
                {"note_id": note_id, "file_id": file_id, "sort_order": sort_order},
            )
    return removed_keys


def _remove_note_files(storage_keys: list[str]) -> None:
    if not storage_keys:
        return
    from .uploads import _upload_root

    root = _upload_root()
    for storage_key in storage_keys:
        path = (root / storage_key).resolve()
        if root in path.parents:
            path.unlink(missing_ok=True)


def _create_note_sync(payload: NoteRequest) -> dict[str, Any]:
    _ensure_side_feature_tables_sync()
    if not payload.content.strip() and not payload.attachment_ids:
        raise HTTPException(status_code=422, detail="请填写笔记内容或至少上传一个附件。")
    storage_keys: list[str] = []
    with SessionLocal() as db:
        if not _get_user_exists(db, payload.user_id):
            raise HTTPException(status_code=404, detail="用户不存在，请先登录。")
        result = db.execute(
            text(
                """
                INSERT INTO user_notes (user_id, title, content, course, knowledge_tag)
                VALUES (:user_id, :title, :content, :course, :knowledge_tag)
                """
            ),
            payload.model_dump(exclude={"attachment_ids"}),
        )
        note_id = int(result.lastrowid)
        storage_keys = _sync_note_attachments(db, note_id, payload.user_id, payload.attachment_ids)
        db.commit()
    _remove_note_files(storage_keys)
    notes = _notes_sync(payload.user_id)["items"]
    return next(item for item in notes if item["id"] == note_id)


def _update_note_sync(note_id: int, payload: NoteUpdateRequest) -> dict[str, Any]:
    _ensure_side_feature_tables_sync()
    update_data = payload.model_dump(exclude_none=True)
    update_data["note_id"] = note_id
    fields = [key for key in ("title", "content", "course", "knowledge_tag") if key in update_data]
    has_attachment_update = payload.attachment_ids is not None
    if not fields and not has_attachment_update:
        raise HTTPException(status_code=400, detail="没有可更新的笔记内容。")
    storage_keys: list[str] = []
    with SessionLocal() as db:
        current_note = db.execute(
            text("SELECT content FROM user_notes WHERE id = :note_id AND user_id = :user_id LIMIT 1"),
            {"note_id": note_id, "user_id": payload.user_id},
        ).mappings().first()
        if not current_note:
            raise HTTPException(status_code=404, detail="没有找到这条笔记。")
        existing_ids = [
            int(file_id)
            for file_id in db.execute(
                text("SELECT uploaded_file_id FROM note_attachments WHERE note_id = :note_id ORDER BY sort_order, id"),
                {"note_id": note_id},
            ).scalars().all()
        ]
        next_content = payload.content if payload.content is not None else str(current_note["content"] or "")
        next_attachments = payload.attachment_ids if payload.attachment_ids is not None else existing_ids
        if not next_content.strip() and not next_attachments:
            raise HTTPException(status_code=422, detail="请填写笔记内容或至少保留一个附件。")
        if fields:
            assignments = ", ".join(f"{field} = :{field}" for field in fields)
            db.execute(
                text(
                    f"""
                    UPDATE user_notes
                    SET {assignments}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :note_id AND user_id = :user_id
                    """
                ),
                update_data,
            )
        if has_attachment_update:
            storage_keys = _sync_note_attachments(db, note_id, payload.user_id, payload.attachment_ids or [])
        db.commit()
    _remove_note_files(storage_keys)
    notes = _notes_sync(payload.user_id)["items"]
    return next(item for item in notes if item["id"] == note_id)


def _delete_note_sync(note_id: int, user_id: int) -> dict[str, Any]:
    _ensure_side_feature_tables_sync()
    storage_keys: list[str] = []
    with SessionLocal() as db:
        attachment_rows = db.execute(
            text(
                """
                SELECT uf.id, uf.storage_key
                FROM note_attachments AS na
                JOIN uploaded_files AS uf ON uf.id = na.uploaded_file_id
                JOIN user_notes AS un ON un.id = na.note_id
                WHERE na.note_id = :note_id AND un.user_id = :user_id
                """
            ),
            {"note_id": note_id, "user_id": user_id},
        ).mappings().all()
        result = db.execute(
            text("DELETE FROM user_notes WHERE id = :note_id AND user_id = :user_id"),
            {"note_id": note_id, "user_id": user_id},
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="没有找到这条笔记。")
        for row in attachment_rows:
            db.execute(text("DELETE FROM uploaded_files WHERE id = :file_id"), {"file_id": int(row["id"])})
            storage_keys.append(str(row["storage_key"]))
        db.commit()
    _remove_note_files(storage_keys)
    return {"deleted": True, "id": note_id}


def _normalize_session_id(session_id: str | None) -> str:
    if not session_id:
        return str(uuid.uuid4())
    try:
        return str(uuid.UUID(str(session_id)))
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, str(session_id)))


def _save_chat_message(user_id: int, session_id: str, role: str, content: str) -> None:
    query = text(
        """
        INSERT INTO chat_messages (session_id, user_id, role, content)
        VALUES (:session_id, :user_id, :role, :content)
        """
    )
    try:
        with SessionLocal() as db:
            if not _get_user_exists(db, user_id):
                return
            db.execute(query, {"session_id": session_id, "user_id": user_id, "role": role, "content": content})
            db.commit()
    except SQLAlchemyError:
        return


def _load_chat_context(user_id: int, session_id: str, limit: int = 12) -> list[dict[str, str]]:
    query = text(
        """
        SELECT role, content
        FROM (
          SELECT id, role, content, created_at
          FROM chat_messages
          WHERE user_id = :user_id AND session_id = :session_id
          ORDER BY created_at DESC, id DESC
          LIMIT :limit
        ) AS recent_messages
        ORDER BY created_at ASC, id ASC
        """
    )
    try:
        with SessionLocal() as db:
            rows = db.execute(query, {"user_id": user_id, "session_id": session_id, "limit": limit}).mappings().all()
    except SQLAlchemyError:
        return []
    return [{"role": str(row["role"]), "content": str(row["content"])} for row in rows]


def _chat_history_sync(user_id: int, session_id: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"user_id": user_id, "limit": limit, "offset": offset}
    where_clause = "WHERE user_id = :user_id"
    if session_id:
        where_clause += " AND session_id = :session_id"
        params["session_id"] = session_id
    query = text(
        f"""
        SELECT id, session_id, user_id, role, content, created_at
        FROM chat_messages
        {where_clause}
        ORDER BY created_at DESC, id DESC
        LIMIT :limit OFFSET :offset
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query, params).mappings().all()
    return [
        {
            "id": int(row["id"]),
            "session_id": str(row["session_id"]),
            "user_id": int(row["user_id"]),
            "role": str(row["role"]),
            "content": str(row["content"]),
            "created_at": _json_safe(row["created_at"]),
        }
        for row in rows
    ]


def _chat_sessions_sync(user_id: int, limit: int) -> list[dict[str, Any]]:
    query = text(
        """
        SELECT session_id, MAX(created_at) AS last_message_at, COUNT(*) AS message_count
        FROM chat_messages
        WHERE user_id = :user_id
        GROUP BY session_id
        ORDER BY last_message_at DESC
        LIMIT :limit
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query, {"user_id": user_id, "limit": limit}).mappings().all()
    return [
        {
            "session_id": str(row["session_id"]),
            "last_message_at": _json_safe(row["last_message_at"]),
            "message_count": int(row["message_count"]),
        }
        for row in rows
    ]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "domain": "math_brain"}


@router.get("/stages")
async def stages() -> dict[str, Any]:
    return {"stages": await asyncio.to_thread(_stages_sync)}


@router.get("/courses")
async def courses(stage: str | None = Query(default=None, max_length=16)) -> dict[str, Any]:
    return {"courses": await asyncio.to_thread(_courses_sync, stage)}


@router.get("/knowledge-graph")
async def knowledge_graph(
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
    user_id: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    return await asyncio.to_thread(_knowledge_graph_sync, stage, course, user_id)


@router.get("/question-types")
async def question_types() -> dict[str, Any]:
    return await asyncio.to_thread(_question_type_counts_sync)


@router.get("/practice/random")
async def random_practice(
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
    knowledge_tag: str | None = Query(default=None, max_length=160),
    question_type: str | None = Query(default=None, pattern="^(choice|blank|calculation|proof|comprehensive)$"),
    limit: int = Query(default=8, ge=1, le=50),
    mode: str = Query(default="custom", pattern="^(daily|chapter|mock|wrong_book|custom)$"),
) -> dict[str, Any]:
    questions = await asyncio.to_thread(
        _random_questions_sync,
        stage=stage,
        course=course,
        knowledge_tag=knowledge_tag,
        question_type=question_type,
        limit=limit,
    )
    return {
        "task_id": str(uuid.uuid4()),
        "mode": mode,
        "stage": stage,
        "course": course,
        "knowledge_tag": knowledge_tag,
        "question_type": question_type,
        "questions": questions,
    }


@router.post("/assessment/start")
async def start_assessment(payload: AssessmentStartRequest) -> dict[str, Any]:
    return await asyncio.to_thread(_start_assessment_sync, payload)


@router.get("/assessment/{task_id}/report")
async def assessment_report(
    task_id: str,
    user_id: int = Query(ge=1),
) -> dict[str, Any]:
    state = await asyncio.to_thread(_assessment_after_submit_sync, user_id, task_id)
    if not state.get("assessment_complete"):
        raise HTTPException(status_code=409, detail="首测尚未完成。")
    return state["assessment_report"]


@router.get("/mock-exam")
async def mock_exam(
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=20, ge=5, le=50),
) -> dict[str, Any]:
    questions = await asyncio.to_thread(
        _random_questions_sync,
        stage=stage,
        course=course,
        knowledge_tag=None,
        question_type=None,
        limit=limit,
    )
    return {
        "task_id": str(uuid.uuid4()),
        "mode": "mock",
        "duration_minutes": max(30, round(limit * 2.5)),
        "questions": questions,
    }


@router.post("/practice/submit")
async def submit_answer(
    payload: AnswerSubmissionRequest,
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    if current["role"] != "student" or int(current["id"]) != payload.user_id:
        raise HTTPException(status_code=403, detail="只能提交当前登录学生自己的作答。")
    return await asyncio.to_thread(_submit_answer_sync, payload)


@router.get("/diagnose")
async def diagnose_user(user_id: int = Query(default=1, ge=1)) -> dict[str, Any]:
    return await asyncio.to_thread(_diagnose_sync, user_id)


@router.get("/recommend")
async def recommend(
    user_id: int = Query(default=1, ge=1),
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    tasks = await asyncio.to_thread(_recommend_sync, user_id, limit, stage, course)
    return {"user_id": user_id, "tasks": tasks, "questions": tasks}


@router.get("/study-roadmap")
async def study_roadmap(user_id: int = Query(default=1, ge=1)) -> dict[str, Any]:
    return await asyncio.to_thread(_study_roadmap_sync, user_id)


@router.get("/review/wrong-questions")
async def wrong_questions(
    user_id: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return await asyncio.to_thread(_wrong_questions_sync, user_id, limit, offset)


@router.get("/user-goals")
async def get_user_goal(user_id: int = Query(default=1, ge=1)) -> dict[str, Any]:
    return await asyncio.to_thread(_get_goal_sync, user_id)


@router.post("/user-goals")
async def save_user_goal(payload: GoalRequest) -> dict[str, Any]:
    return await asyncio.to_thread(_save_goal_sync, payload)


@router.get("/messages")
async def messages(user_id: int = Query(default=1, ge=1)) -> dict[str, Any]:
    return await asyncio.to_thread(_messages_sync, user_id)


@router.get("/profile/summary")
async def profile_summary(user_id: int = Query(default=1, ge=1)) -> dict[str, Any]:
    return await asyncio.to_thread(_profile_summary_sync, user_id)


@router.get("/achievements")
async def achievements(user_id: int = Query(default=1, ge=1)) -> dict[str, Any]:
    return await asyncio.to_thread(_achievements_sync, user_id)


@router.get("/resources")
async def resources(
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
) -> dict[str, Any]:
    return await asyncio.to_thread(_resources_sync, stage, course)


@router.get("/notes")
async def notes(
    user_id: int = Query(default=1, ge=1),
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    if int(current["id"]) != user_id:
        raise HTTPException(status_code=403, detail="只能查看当前账号的笔记。")
    return await asyncio.to_thread(_notes_sync, user_id)


@router.post("/notes", status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteRequest,
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    if int(current["id"]) != payload.user_id:
        raise HTTPException(status_code=403, detail="只能为当前账号创建笔记。")
    return await asyncio.to_thread(_create_note_sync, payload)


@router.put("/notes/{note_id}")
async def update_note(
    note_id: int,
    payload: NoteUpdateRequest,
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    if int(current["id"]) != payload.user_id:
        raise HTTPException(status_code=403, detail="只能修改当前账号的笔记。")
    return await asyncio.to_thread(_update_note_sync, note_id, payload)


@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: int,
    user_id: int = Query(ge=1),
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    if int(current["id"]) != user_id:
        raise HTTPException(status_code=403, detail="只能删除当前账号的笔记。")
    return await asyncio.to_thread(_delete_note_sync, note_id, user_id)


async def _chat_event_stream(request: ChatRequest):
    session_id = _normalize_session_id(request.session_id)
    previous_messages = await asyncio.to_thread(_load_chat_context, request.user_id, session_id)
    diagnosis = await asyncio.to_thread(_diagnose_sync, request.user_id)
    messages = [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"当前诊断摘要：{diagnosis.get('summary')}；薄弱点：{json.dumps(diagnosis.get('weak_points'), ensure_ascii=False)}",
        },
        *previous_messages,
        {"role": "user", "content": request.message},
    ]
    reply = await asyncio.to_thread(call_llm, messages)
    if not reply:
        reply = "我建议先做一组极限与连续的基础题，再把错误按“概念混淆 / 计算失误 / 思路断点”三类标注。"

    await asyncio.to_thread(_save_chat_message, request.user_id, session_id, "user", request.message)
    await asyncio.to_thread(_save_chat_message, request.user_id, session_id, "assistant", reply)

    yield f"data: {json.dumps({'session_id': session_id}, ensure_ascii=False)}\n\n"
    for char in reply:
        yield f"data: {json.dumps({'delta': char}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.025)
    yield "data: [DONE]\n\n"


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _chat_event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/history")
async def chat_history(
    user_id: int = Query(default=1, ge=1),
    session_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    normalized_session = _normalize_session_id(session_id) if session_id else None
    messages = await asyncio.to_thread(_chat_history_sync, user_id, normalized_session, limit, offset)
    return {"user_id": user_id, "session_id": normalized_session, "messages": messages}


@router.get("/chat/sessions")
async def chat_sessions(
    user_id: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    sessions = await asyncio.to_thread(_chat_sessions_sync, user_id, limit)
    return {"user_id": user_id, "sessions": sessions}
