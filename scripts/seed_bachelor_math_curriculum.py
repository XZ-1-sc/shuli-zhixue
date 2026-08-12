"""Normalize the bachelor curriculum and seed a balanced Chinese question bank."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import text

from backend.app.database.session import SessionLocal
from scripts.bachelor_math_seed_data import COURSES, TOPICS


SOURCE_NAME = "数理智学中文演示题库"
TYPE_ORDER = ("choice", "blank", "calculation", "proof", "comprehensive")
TYPE_LABELS = {
    "choice": "选择题",
    "blank": "填空题",
    "calculation": "计算题",
    "proof": "证明题",
    "comprehensive": "综合题",
}
STAGE_TITLES = {
    "大一": (1, "基础建构期", "建立微积分、线性代数、解析几何和数学证明的基础语言。"),
    "大二": (2, "工具扩展期", "掌握多元微积分、级数、微分方程、概率统计与线性代数进阶工具。"),
    "大三": (3, "专业深化期", "进入现代分析、代数、数值计算和偏微分方程。"),
    "大四": (4, "综合应用期", "连接拓扑、几何、泛函分析与数学建模，形成综合问题解决能力。"),
}
COURSE_ALIASES = {
    "线性代数上": "线性代数基础",
    "线性代数下": "线性代数进阶",
}


def node_code(stage: str, course: str, label: str) -> str:
    digest = hashlib.sha1(f"{stage}|{course}|{label}".encode("utf-8")).hexdigest()[:18]
    return f"cn-{digest}"


def key_steps(question_type: str, fine_tag: str) -> list[str]:
    if question_type == "choice":
        return [f"识别“{fine_tag}”的适用条件", "写出定义、定理或核心公式", "逐项核对并排除干扰项"]
    if question_type == "blank":
        return [f"定位“{fine_tag}”中的目标概念", "检查符号、定义域和前提条件", "用最简规范形式填写"]
    if question_type == "calculation":
        return ["整理已知量和待求量", f"选择“{fine_tag}”对应的公式或方法", "分步计算并回代检查"]
    if question_type == "proof":
        return ["写清前提与待证结论", f"展开“{fine_tag}”的定义或关键定理", "补齐推理链并检查是否使用全部条件"]
    return ["把综合问题拆成可验证的子问题", f"建立与“{fine_tag}”相关的数学表达", "完成计算或证明并解释结论边界"]


def ensure_curriculum(db) -> dict[tuple[str, str, str], int]:
    stage_ids: dict[str, int] = {}
    for stage_name, (stage_order, title, goal_text) in STAGE_TITLES.items():
        db.execute(
            text(
                """
                INSERT INTO math_stages (stage_name, stage_order, title, goal_text)
                VALUES (:stage_name, :stage_order, :title, :goal_text)
                ON DUPLICATE KEY UPDATE
                  stage_order=VALUES(stage_order), title=VALUES(title), goal_text=VALUES(goal_text)
                """
            ),
            {"stage_name": stage_name, "stage_order": stage_order, "title": title, "goal_text": goal_text},
        )
        stage_ids[stage_name] = int(
            db.execute(text("SELECT id FROM math_stages WHERE stage_name=:stage"), {"stage": stage_name}).scalar_one()
        )

    for stage, course, group_name, course_order, description in COURSES:
        db.execute(
            text(
                """
                INSERT INTO math_courses
                  (stage_id, course_name, course_group, course_order, description)
                VALUES
                  (:stage_id, :course_name, :course_group, :course_order, :description)
                ON DUPLICATE KEY UPDATE
                  course_group=VALUES(course_group), course_order=VALUES(course_order), description=VALUES(description)
                """
            ),
            {
                "stage_id": stage_ids[stage],
                "course_name": course,
                "course_group": group_name,
                "course_order": course_order,
                "description": description,
            },
        )

    for old_name, new_name in COURSE_ALIASES.items():
        db.execute(
            text("UPDATE questions SET course=:new_name WHERE source_id=:source_id AND course=:old_name"),
            {"new_name": new_name, "old_name": old_name, "source_id": source_id(db)},
        )

    knowledge_ids: dict[tuple[str, str, str], int] = {}
    course_topics: dict[tuple[str, str], list[dict]] = {}
    for item in TOPICS:
        course_topics.setdefault((item["stage"], item["course"]), []).append(item)

    curated_source_id = source_id(db)
    existing_topics = db.execute(
        text(
            """
            SELECT DISTINCT stage, course, knowledge_tag, fine_tag
            FROM questions
            WHERE source_id=:source_id
            ORDER BY stage, course, knowledge_tag, fine_tag
            """
        ),
        {"source_id": curated_source_id},
    ).mappings().all()
    known_keys = {
        (item["stage"], item["course"], item["fine_tag"])
        for item in TOPICS
    }
    for row in existing_topics:
        key = (str(row["stage"]), str(row["course"]), str(row["fine_tag"]))
        if key in known_keys:
            continue
        course_topics.setdefault((key[0], key[1]), []).append(
            {
                "stage": key[0],
                "course": key[1],
                "knowledge_tag": str(row["knowledge_tag"]),
                "fine_tag": key[2],
            }
        )
        known_keys.add(key)

    for (stage, course), topics in course_topics.items():
        parent_label = "中文核心知识"
        parent_code = node_code(stage, course, parent_label)
        db.execute(
            text(
                """
                INSERT INTO knowledge_nodes
                  (node_code, parent_id, stage_name, course_name, name, level, sort_order, description)
                VALUES
                  (:node_code, NULL, :stage, :course, :name, 2, 900, :description)
                ON DUPLICATE KEY UPDATE
                  stage_name=VALUES(stage_name), course_name=VALUES(course_name), name=VALUES(name),
                  level=VALUES(level), sort_order=VALUES(sort_order), description=VALUES(description)
                """
            ),
            {
                "node_code": parent_code,
                "stage": stage,
                "course": course,
                "name": parent_label,
                "description": f"{course}的中文核心知识节点。",
            },
        )
        parent_id = int(
            db.execute(text("SELECT id FROM knowledge_nodes WHERE node_code=:code"), {"code": parent_code}).scalar_one()
        )
        for order, item in enumerate(topics, start=1):
            label = item["fine_tag"]
            code = node_code(stage, course, label)
            db.execute(
                text(
                    """
                    INSERT INTO knowledge_nodes
                      (node_code, parent_id, stage_name, course_name, name, level, sort_order, description)
                    VALUES
                      (:node_code, :parent_id, :stage, :course, :name, 3, :sort_order, :description)
                    ON DUPLICATE KEY UPDATE
                      parent_id=VALUES(parent_id), stage_name=VALUES(stage_name), course_name=VALUES(course_name),
                      name=VALUES(name), level=VALUES(level), sort_order=VALUES(sort_order), description=VALUES(description)
                    """
                ),
                {
                    "node_code": code,
                    "parent_id": parent_id,
                    "stage": stage,
                    "course": course,
                    "name": label,
                    "sort_order": 900 + order,
                    "description": f"{item['knowledge_tag']}：{label}",
                },
            )
            knowledge_ids[(stage, course, label)] = int(
                db.execute(text("SELECT id FROM knowledge_nodes WHERE node_code=:code"), {"code": code}).scalar_one()
            )
    return knowledge_ids


def source_id(db) -> int:
    existing = db.execute(
        text("SELECT id FROM source_attributions WHERE source_name=:source_name"),
        {"source_name": SOURCE_NAME},
    ).scalar_one_or_none()
    if existing:
        return int(existing)
    result = db.execute(
        text(
            """
            INSERT INTO source_attributions
              (source_name, source_url, license_name, license_url, usage_note)
            VALUES
              (:source_name, :source_url, :license_name, :license_url, :usage_note)
            """
        ),
        {
            "source_name": SOURCE_NAME,
            "source_url": "local://curated-bachelor-mathematics",
            "license_name": "Project curated original content",
            "license_url": "local://project",
            "usage_note": "项目原创中文本科数学题，用于默认练习、模拟测试、解析和诊断。",
        },
    )
    return int(result.lastrowid)


def seed_questions(db, knowledge_ids: dict[tuple[str, str, str], int]) -> int:
    curated_source_id = source_id(db)
    seeded = 0
    for topic_index, item in enumerate(TOPICS, start=1):
        knowledge_node_id = knowledge_ids[(item["stage"], item["course"], item["fine_tag"])]
        for question_type in TYPE_ORDER:
            content = item[question_type]
            options = content.get("options", {})
            correct_answer = content.get("answer") if question_type == "choice" else None
            standard_answer = options.get(correct_answer, correct_answer) if question_type == "choice" else content["answer"]
            payload = {
                "source_id": curated_source_id,
                "source_question_no": f"BACHELOR-CN-{topic_index:02d}-{question_type}",
                "source_path": f"curated-bachelor/{item['stage']}/{item['course']}/{item['fine_tag']}/{question_type}",
                "question_type": question_type,
                "stage": item["stage"],
                "course": item["course"],
                "knowledge_node_id": knowledge_node_id,
                "knowledge_tag": item["knowledge_tag"],
                "fine_tag": item["fine_tag"],
                "difficulty": item["difficulty"],
                "question_text": f"【{TYPE_LABELS[question_type]}】{content['prompt']}",
                "option_a": options.get("A"),
                "option_b": options.get("B"),
                "option_c": options.get("C"),
                "option_d": options.get("D"),
                "correct_answer": correct_answer,
                "standard_answer": standard_answer,
                "analysis_text": content["analysis"],
                "key_steps": json.dumps(key_steps(question_type, item["fine_tag"]), ensure_ascii=False),
                "common_errors": json.dumps(
                    ["忽略题目中的适用条件", "公式或定理使用不完整", "符号、边界或逻辑方向错误"],
                    ensure_ascii=False,
                ),
                "mistake_tags": json.dumps(
                    [item["knowledge_tag"], item["fine_tag"], "步骤完整性"], ensure_ascii=False
                ),
            }
            db.execute(
                text(
                    """
                    INSERT INTO questions
                      (source_id, source_question_no, source_path, question_type, stage, course,
                       knowledge_node_id, knowledge_tag, fine_tag, difficulty, question_text,
                       option_a, option_b, option_c, option_d, correct_answer, standard_answer,
                       analysis_text, key_steps, common_errors, mistake_tags)
                    VALUES
                      (:source_id, :source_question_no, :source_path, :question_type, :stage, :course,
                       :knowledge_node_id, :knowledge_tag, :fine_tag, :difficulty, :question_text,
                       :option_a, :option_b, :option_c, :option_d, :correct_answer, :standard_answer,
                       :analysis_text, :key_steps, :common_errors, :mistake_tags)
                    ON DUPLICATE KEY UPDATE
                       source_path=VALUES(source_path), question_type=VALUES(question_type),
                       stage=VALUES(stage), course=VALUES(course), knowledge_node_id=VALUES(knowledge_node_id),
                       knowledge_tag=VALUES(knowledge_tag), fine_tag=VALUES(fine_tag), difficulty=VALUES(difficulty),
                       question_text=VALUES(question_text), option_a=VALUES(option_a), option_b=VALUES(option_b),
                       option_c=VALUES(option_c), option_d=VALUES(option_d), correct_answer=VALUES(correct_answer),
                       standard_answer=VALUES(standard_answer), analysis_text=VALUES(analysis_text),
                       key_steps=VALUES(key_steps), common_errors=VALUES(common_errors), mistake_tags=VALUES(mistake_tags)
                    """
                ),
                payload,
            )
            seeded += 1
    return seeded


def bind_existing_curated_questions(db, knowledge_ids: dict[tuple[str, str, str], int]) -> None:
    curated_source_id = source_id(db)
    for (stage, course, fine_tag), knowledge_node_id in knowledge_ids.items():
        db.execute(
            text(
                """
                UPDATE questions
                SET knowledge_node_id=:knowledge_node_id
                WHERE source_id=:source_id AND stage=:stage AND course=:course AND fine_tag=:fine_tag
                """
            ),
            {
                "knowledge_node_id": knowledge_node_id,
                "source_id": curated_source_id,
                "stage": stage,
                "course": course,
                "fine_tag": fine_tag,
            },
        )


def main() -> None:
    with SessionLocal() as db:
        knowledge_ids = ensure_curriculum(db)
        seeded = seed_questions(db, knowledge_ids)
        bind_existing_curated_questions(db, knowledge_ids)
        db.execute(
            text(
                """
                UPDATE source_attributions
                SET source_url='local://curated-bachelor-mathematics',
                    license_name='Project curated original content',
                    license_url='local://project',
                    usage_note='项目原创中文本科数学题，用于默认练习、模拟测试、解析和诊断。'
                WHERE source_name=:source_name
                """
            ),
            {"source_name": SOURCE_NAME},
        )
        db.commit()

        total = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*) FROM questions q
                    JOIN source_attributions s ON s.id=q.source_id
                    WHERE s.source_name=:source_name
                    """
                ),
                {"source_name": SOURCE_NAME},
            ).scalar_one()
        )
    print(f"seeded_or_updated={seeded}; curated_total={total}; courses={len(COURSES)}")


if __name__ == "__main__":
    main()
