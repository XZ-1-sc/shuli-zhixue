"""按真实教学大纲为课程生成「章→节→知识点」三层骨架，重建 knowledge_nodes。

用法（试点一门课程）:
    python scripts/gen_syllabus.py 高等数学上
    python scripts/gen_syllabus.py --all        # 图谱白名单全部课程
输出: 每门课的层级统计 + 写库结果（事务内替换该课程旧节点）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import text  # noqa: E402

from app.database.session import SessionLocal  # noqa: E402
from app.utils.llm_client import call_llm_json  # noqa: E402

# 图谱课程白名单：真实学科课程（排除专题/伪课程）；值 = 该课程原属年级(stage_name, 兼容保留)
SYLLABUS_COURSES: list[tuple[str, str]] = [
    ("高等数学上", "大一"),
    ("高等数学下", "大二"),
    ("线性代数基础", "大一"),
    ("线性代数进阶", "大二"),
    ("级数与常微分方程", "大二"),
    ("概率论与数理统计", "大二"),
    ("复变函数", "大三"),
    ("实变函数", "大三"),
    ("抽象代数", "大三"),
    ("数值分析", "大三"),
    ("偏微分方程基础", "大三"),
    ("微分几何基础", "大四"),
]

COURSE_PREFIX: dict[str, str] = {
    "高等数学上": "gss1", "高等数学下": "gss2", "线性代数基础": "xxds1", "线性代数进阶": "xxds2",
    "级数与常微分方程": "jscw", "概率论与数理统计": "gltj", "复变函数": "fbhs", "实变函数": "sbhs",
    "抽象代数": "cxds", "数值分析": "szfx", "偏微分方程基础": "pwfc", "微分几何基础": "wfjj",
}


class Topic(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)


class Section(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    topics: list[Topic] = Field(min_length=1, max_length=10)


class Chapter(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    sections: list[Section] = Field(min_length=1, max_length=10)


class CourseSyllabus(BaseModel):
    course: str
    chapters: list[Chapter] = Field(min_length=3, max_length=12)


def _build_prompt(course: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                f"你是大学数学教学大纲专家。为《{course}》生成一套规范的「章→节→知识点」知识骨架。"
                "要求：① 遵循国内常见大学教材大纲的章节顺序与命名；② 每章含 2-4 节，每节含 2-6 个知识点；"
                "③ 知识点是原子学习单元（如『数列极限的 ε-N 定义』『洛必达法则』），不写题型、不写练习维度；"
                "④ 总章节数 5-9；⑤ 全中文，每个知识点给一句 20 字内描述（说明它解决什么问题）。"
            ),
        },
        {"role": "user", "content": f"请生成《{course}》的完整大纲骨架，课程名严格写作：{course}"},
    ]


def _fallback_syllabus(course: str) -> CourseSyllabus:
    chapters = []
    for index in range(5):
        chapters.append(
            Chapter(
                name=f"{course}第{index + 1}部分",
                sections=[
                    Section(
                        name="基础",
                        topics=[
                            Topic(name="核心概念", description="课程基础概念。"),
                            Topic(name="基本方法", description="课程基本方法。"),
                        ],
                    ),
                    Section(
                        name="综合",
                        topics=[
                            Topic(name="综合应用", description="课程综合应用。"),
                            Topic(name="常见误区", description="课程常见误区。"),
                        ],
                    ),
                ],
            )
        )
    return CourseSyllabus(course=course, chapters=chapters)


def generate_syllabus(course: str) -> CourseSyllabus:
    syllabus, _usage = call_llm_json(
        _build_prompt(course),
        CourseSyllabus,
        fallback=_fallback_syllabus(course),
        agent_name="syllabus_gen",
        temperature=0.2,
        max_tokens=9000,
        retries=2,
        timeout=150,
    )
    return syllabus


def replace_course_nodes(course: str, stage: str, syllabus: CourseSyllabus) -> dict[str, Any]:
    prefix = COURSE_PREFIX.get(course, f"c{abs(hash(course)) % 10000}")
    seq = 0
    nodes: list[dict[str, Any]] = []

    def node_code() -> str:
        nonlocal seq
        seq += 1
        return f"{prefix}_{seq:03d}"

    for chapter_index, chapter in enumerate(syllabus.chapters, start=1):
        nodes.append({"name": chapter.name, "level": 1, "sort": chapter_index * 100, "parent_key": None,
                      "description": f"{course} · {chapter.name}"})
        for section_index, section in enumerate(chapter.sections, start=1):
            nodes.append({"name": section.name, "level": 2, "sort": chapter_index * 100 + section_index * 10,
                          "parent_key": f"{chapter_index}", "description": f"{course} · {chapter.name} · {section.name}"})
            for topic_index, topic in enumerate(section.topics, start=1):
                nodes.append({"name": topic.name, "level": 3,
                              "sort": chapter_index * 100 + section_index * 10 + topic_index,
                              "parent_key": f"{chapter_index}.{section_index}",
                              "description": topic.description or f"{course} · {section.name} · {topic.name}"})

    # 给每个节点分配 node_code，并记录其 parent 索引以便回填 id
    with SessionLocal.begin() as db:
        db.execute(text("DELETE FROM knowledge_nodes WHERE course_name=:course"), {"course": course})
        parent_ids: dict[str, int] = {}
        inserted = 0
        for item in nodes:
            code = node_code()
            parent_id = parent_ids.get(item["parent_key"]) if item["parent_key"] else None
            result = db.execute(
                text(
                    """
                    INSERT INTO knowledge_nodes(node_code,parent_id,stage_name,course_name,name,level,sort_order,description)
                    VALUES(:code,:parent,:stage,:course,:name,:level,:sort,:desc)
                    """
                ),
                {
                    "code": code, "parent": parent_id, "stage": stage, "course": course,
                    "name": item["name"], "level": item["level"], "sort": item["sort"], "desc": item["description"],
                },
            )
            inserted += 1
            # 记录本节点 key→id（供其子节点引用）
            # 用结构 key：章=chapter_index；节=chapter_index.section_index；点不作为父
            if item["level"] == 1:
                parent_ids[str(item["sort"] // 100)] = int(result.lastrowid)
            elif item["level"] == 2:
                parent_ids[f"{item['sort'] // 100}.{(item['sort'] // 10) % 10}"] = int(result.lastrowid)
    return {"course": course, "nodes": len(nodes), "chapters": len(syllabus.chapters), "inserted": inserted}


def validate_and_report(syllabus: CourseSyllabus) -> None:
    chapters = len(syllabus.chapters)
    sections = sum(len(c.sections) for c in syllabus.chapters)
    topics = sum(len(s.topics) for c in syllabus.chapters for s in c.sections)
    names: set[str] = set()
    dup = []
    for c in syllabus.chapters:
        if c.name in names:
            dup.append(c.name)
        names.add(c.name)
        for s in c.sections:
            if s.name in names:
                dup.append(s.name)
            names.add(s.name)
            for t in s.topics:
                if t.name in names:
                    dup.append(t.name)
                names.add(t.name)
    print(f"[{syllabus.course}] 章={chapters} 节={sections} 知识点={topics} 节点合计={chapters + sections + topics} 重名={dup[:5] if dup else '无'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("courses", nargs="*")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    targets = SYLLABUS_COURSES if args.all else [(name, "大一") for name in args.courses]
    if not targets:
        print("请指定课程或 --all")
        return
    for course, stage in targets:
        syllabus = generate_syllabus(course)
        validate_and_report(syllabus)
        summary = replace_course_nodes(course, stage, syllabus)
        print(f"  写入完成: {summary}")


if __name__ == "__main__":
    main()
