"""curriculum repositories: 用户课程 + 课程根知识图谱（教学大纲版）。

图谱课程白名单 = 真实学科课程；知识节点按 章(1) → 节(2) → 知识点(3) 三层组织。
掌握度 = 题目标签经「精确/包含」匹配落到叶子/节点后，自下而上聚合上卷。
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text

from ..session import SessionLocal
from ...api.utils import _display_knowledge_name, _is_unmapped_english_label, _mastery_status

# 图谱课程白名单（与 scripts/gen_syllabus.py 保持一致）：真实学科课程
GRAPH_COURSES: list[str] = [
    "高等数学上", "高等数学下", "线性代数基础", "线性代数进阶",
    "级数与常微分方程", "概率论与数理统计", "复变函数", "实变函数",
    "抽象代数", "数值分析", "偏微分方程基础", "微分几何基础",
]

# 题库 course 别名 → 图谱课程名
COURSE_ALIASES: dict[str, str] = {
    "线性代数上": "线性代数基础",
    "线性代数下": "线性代数进阶",
    "高等数学（上）": "高等数学上",
    "高等数学（下）": "高等数学下",
}


def _canonical_course(name: Any) -> str:
    value = str(name or "").strip()
    return COURSE_ALIASES.get(value, value)


def _all_courses_sync() -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(text("""
            SELECT MIN(c.id) AS id,c.course_name,MIN(c.course_group) AS course_group,
                   MIN(c.course_order) AS course_order,MAX(COALESCE(c.description,'')) AS description
            FROM math_courses c
            GROUP BY c.course_name
            ORDER BY MIN(c.course_order),c.course_name
        """)).mappings().all()
    return [{"id": int(row["id"]), "course_name": str(row["course_name"]), "course_group": str(row["course_group"]),
             "course_order": int(row["course_order"]), "description": str(row["description"] or "")} for row in rows]


def _user_courses_sync(user_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(text("""
            SELECT course_name,is_primary,course_order FROM user_courses
            WHERE user_id=:user_id ORDER BY is_primary DESC,course_order,id
        """), {"user_id": user_id}).mappings().all()
        if not rows:
            fallback = db.execute(text("SELECT target_course FROM user_goal_settings WHERE user_id=:user_id"), {"user_id": user_id}).scalar()
            if fallback:
                rows = [{"course_name": fallback, "is_primary": 1, "course_order": 0}]
    courses = [str(row["course_name"]) for row in rows]
    primary = next((str(row["course_name"]) for row in rows if int(row["is_primary"] or 0)), courses[0] if courses else None)
    return {"courses": courses, "primary_course": primary}


def _save_user_courses_sync(user_id: int, courses: list[str], primary_course: str | None) -> dict[str, Any]:
    ordered = list(dict.fromkeys(item.strip() for item in courses if item.strip()))
    if not ordered:
        raise HTTPException(status_code=422, detail="请至少选择一门课程。")
    primary = primary_course if primary_course in ordered else ordered[0]
    with SessionLocal.begin() as db:
        known = set(db.execute(text("SELECT DISTINCT course_name FROM math_courses")).scalars().all())
        unknown = [name for name in ordered if name not in known]
        if unknown:
            raise HTTPException(status_code=422, detail=f"课程不存在：{'、'.join(unknown)}")
        db.execute(text("DELETE FROM user_courses WHERE user_id=:user_id"), {"user_id": user_id})
        for index, name in enumerate(ordered):
            db.execute(text("""
                INSERT INTO user_courses(user_id,course_name,is_primary,course_order)
                VALUES(:user_id,:course_name,:is_primary,:course_order)
            """), {"user_id": user_id, "course_name": name, "is_primary": 1 if name == primary else 0, "course_order": index})
        db.execute(text("""
            INSERT INTO user_goal_settings(user_id,target_course,target_stage,weekly_hours)
            VALUES(:user_id,:course,'大一',8.0)
            ON DUPLICATE KEY UPDATE target_course=VALUES(target_course)
        """), {"user_id": user_id, "course": primary})
    return {"courses": ordered, "primary_course": primary}


# ---------------------------------------------------------------- 图谱 v2

def _match_node_id(label: str, name_index: dict[str, int], levels: dict[int, int]) -> int | None:
    """标签 → 节点：1) 精确命中（叶子优先）2) 双向包含，取名称最长匹配。"""
    exact = name_index.get(label)
    if exact:
        return exact
    best: tuple[int, int] | None = None  # (name长度, node_id)
    for node_name, node_id in name_index.items():
        if not node_name:
            continue
        if label in node_name or node_name in label:
            length = len(node_name)
            if best is None or length > best[0]:
                best = (length, node_id)
    return best[1] if best else None


def _knowledge_graph_v2_sync(user_id: int, course: str | None = None, depth: int = 3) -> dict[str, Any]:
    with SessionLocal() as db:
        courses = [item for item in _all_courses_sync() if item["course_name"] in GRAPH_COURSES]
        graph_course_set = {item["course_name"] for item in courses}
        focus = course if course in graph_course_set else None
        relations = db.execute(text("SELECT from_course,to_course,relation,note FROM course_relations ORDER BY id")).mappings().all()
        node_rows: list[Any] = []
        if focus:
            node_rows = db.execute(text("""
                SELECT id,node_code,parent_id,course_name,name,level,sort_order,description
                FROM knowledge_nodes WHERE course_name=:course ORDER BY level,sort_order,id
            """), {"course": focus}).mappings().all()
        mastery_rows = db.execute(text("""
            SELECT q.course AS q_course,q.knowledge_tag,q.fine_tag,COUNT(*) AS total,
                   SUM(CASE WHEN pr.is_correct=1 THEN 1 ELSE 0 END) AS correct
            FROM practice_records pr JOIN questions q ON q.id=pr.question_id
            WHERE pr.user_id=:user_id AND pr.is_correct IS NOT NULL
            GROUP BY q.course,q.knowledge_tag,q.fine_tag
        """), {"user_id": user_id}).mappings().all()

    # 图谱课程卡 + 课程级掌握度（该用户在该图谱课的全部作答）
    course_records: dict[str, list[tuple[int, int]]] = defaultdict(list)
    label_records: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in mastery_rows:
        canon = _canonical_course(row["q_course"])
        pair = (int(row["correct"] or 0), int(row["total"] or 0))
        course_records[canon].append(pair)
        for label in (row["knowledge_tag"], row["fine_tag"]):
            clean = _display_knowledge_name(label)
            if not clean or _is_unmapped_english_label(label):
                continue
            label_records[clean].append(pair)

    nodes: list[dict[str, Any]] = []
    for item in courses:
        name = item["course_name"]
        values = course_records.get(name, [])
        course_mastery = round(sum(c[0] for c in values) / sum(c[1] for c in values) * 100) if values and sum(c[1] for c in values) else None
        nodes.append({"id": f"course:{name}", "name": name, "category": "course", "course": name,
                      "mastery": course_mastery or 0, "mastery_status": _mastery_status(course_mastery),
                      "description": item["description"], "symbolSize": 48})
    links: list[dict[str, Any]] = []
    for row in relations:
        if row["from_course"] not in graph_course_set or row["to_course"] not in graph_course_set:
            continue
        links.append({"source": f"course:{row['from_course']}", "target": f"course:{row['to_course']}",
                      "relation": str(row["relation"]), "label": "先修" if row["relation"] == "prerequisite" else "关联",
                      "note": str(row["note"] or "")})

    if focus and node_rows:
        # 按 depth 截取（depth>=1 章；>=2 节；>=3 知识点）
        max_level = 1 if depth < 2 else (2 if depth < 3 else 3)
        node_map = [dict(r) for r in node_rows if int(r["level"]) <= max_level]
        by_id = {int(r["id"]): r for r in node_map}
        id_to_parent = {int(r["id"]): (int(r["parent_id"]) if r["parent_id"] else None) for r in node_map}
        # label → node_id 精确索引（叶子优先）
        name_index: dict[str, int] = {}
        for r in sorted(node_map, key=lambda r: -int(r["level"])):
            name_index.setdefault(str(r["name"]), int(r["id"]))
        # 直接命中
        acc: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for label, pairs in label_records.items():
            target = _match_node_id(label, name_index, {})
            if target:
                acc[target].extend(pairs)
        # 自下而上聚合（按 level 降序，把自身与子聚合结果上卷给父）
        direct: dict[int, tuple[int, int]] = {
            node_id: (sum(p[0] for p in pairs), sum(p[1] for p in pairs))
            for node_id, pairs in acc.items()
        }
        order = sorted(by_id.keys(), key=lambda nid: -int(by_id[nid]["level"]))
        rolled: dict[int, tuple[int, int]] = dict(direct)
        for nid in order:
            correct, total = rolled.get(nid, (0, 0))
            parent = id_to_parent.get(nid)
            if parent and parent in by_id:
                c, t = rolled.get(parent, (0, 0))
                rolled[parent] = (c + correct, t + total)
        visible_ids = set(by_id.keys())
        for r in node_map:
            row_id = int(r["id"])
            correct, total = rolled.get(row_id, (0, 0))
            mastery = round(correct / total * 100) if total else None
            level = int(r["level"])
            category = "leaf" if level >= 3 else "knowledge"
            nodes.append({
                "id": f"node:{row_id}", "name": str(r["name"]), "category": category,
                "course": focus, "level": level,
                "mastery": mastery or 0, "mastery_status": _mastery_status(mastery),
                "description": str(r["description"] or f"{focus}：{r['name']}"),
                "symbolSize": 30 if category == "leaf" else (46 if level == 1 else 34),
            })
            parent = id_to_parent.get(row_id)
            source = f"node:{parent}" if parent and parent in visible_ids else f"course:{focus}"
            links.append({"source": source, "target": f"node:{row_id}", "relation": "parent", "label": "包含"})

    selected = [name for name in _user_courses_sync(user_id)["courses"] if name in graph_course_set]
    return {"focus_course": focus, "nodes": nodes, "links": links, "total": len(nodes),
            "selected_courses": selected, "graph_courses": list(graph_course_set), "depth": depth}
