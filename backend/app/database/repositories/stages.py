from typing import Any

from sqlalchemy import text

from ..session import SessionLocal
from ...api.utils import _display_knowledge_name, _is_unmapped_english_label, _mastery_status


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

