from typing import Any

from fastapi import HTTPException
from sqlalchemy import text

from ..session import SessionLocal
from ...api.utils import _question_select_sql, _row_to_question


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

