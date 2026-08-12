"""Replace the old xingce database with a math_brain database.

The importer uses WeBWorK Open Problem Library files as the open source
question source. It stores attribution and license metadata with every row.
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
DATA_DIR = ROOT / "data"
TMP_DIR = ROOT / "tmp"
OPL_ROOT = TMP_DIR / "sources" / "webwork-opl"
OPL_LIBRARY = OPL_ROOT / "OpenProblemLibrary"
SCHEMA_PATH = ROOT / "scripts" / "create_math_schema.sql"
BACKUP_DIR = ROOT / "backups"
QUESTIONS_CSV = DATA_DIR / "math_questions.csv"
GRAPH_JSON = DATA_DIR / "math_knowledge_graph.json"
SOURCES_JSON = DATA_DIR / "source_attributions.json"
REPORT_JSON = DATA_DIR / "math_import_report.json"
MIGRATION_LOG = ROOT / "MATH_DATABASE_MIGRATION_LOG.md"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.session import database_url  # noqa: E402


QUESTION_TYPES = ["choice", "blank", "calculation", "proof", "comprehensive"]

SUBJECT_QUOTAS = {
    "Calculus - single variable": 130,
    "Calculus - multivariable": 90,
    "Linear algebra": 90,
    "Differential equations": 80,
    "Probability": 55,
    "Statistics": 55,
    "Complex analysis": 40,
    "Abstract algebra": 30,
    "Real analysis": 20,
    "Operations research": 45,
    "Combinatorics": 25,
    "Graph theory": 15,
    "Set theory and logic": 25,
}

STAGE_INFO = {
    "大一": ("基础建模期", "建立极限、导数、矩阵、逻辑和证明语言的底层直觉。"),
    "大二": ("多变量与概率期", "掌握多元微积分、级数、微分方程和概率统计的核心工具。"),
    "大三": ("专业核心期", "训练抽象结构、严格分析、复变函数和数值思维。"),
    "大四": ("综合提升期", "将高阶课程、建模、优化和综合应用连接成问题解决框架。"),
}

MISTAKE_TAGS = {
    "概念不清": "没有准确区分定义、条件和结论。",
    "条件遗漏": "使用定理或公式时忽略成立条件。",
    "计算失误": "代数变形、符号、数值计算或化简出错。",
    "步骤缺失": "答案缺少关键中间步骤，难以复查。",
    "证明断链": "证明中存在逻辑跳跃或缺少必要说明。",
    "建模不足": "没有把实际或综合题转化为明确数学对象。",
    "题意误读": "没有抓住题干要求、变量含义或限制范围。",
}


@dataclass(frozen=True)
class CourseInfo:
    stage: str
    course: str
    group: str


def clean_subject(value: str | None) -> str:
    return str(value or "").strip().strip("'\"")


def course_for(subject: str, chapter: str, section: str) -> CourseInfo | None:
    subject = clean_subject(subject)
    chapter_text = f"{chapter} {section}".lower()
    if subject == "Calculus - single variable":
        if "series" in chapter_text or "sequences" in chapter_text:
            return CourseInfo("大二", "级数与常微分方程", "高等数学")
        return CourseInfo("大一", "高等数学上", "高等数学")
    if subject == "Calculus - multivariable":
        return CourseInfo("大二", "高等数学下", "高等数学")
    if subject == "Linear algebra":
        return CourseInfo("大一", "线性代数基础", "线性代数")
    if subject == "Differential equations":
        return CourseInfo("大二", "级数与常微分方程", "高等数学")
    if subject in {"Probability", "Statistics"}:
        return CourseInfo("大二", "概率论与数理统计", "概率统计")
    if subject == "Complex analysis":
        return CourseInfo("大三", "复变函数", "专业核心")
    if subject == "Abstract algebra":
        return CourseInfo("大三", "抽象代数", "专业核心")
    if subject == "Real analysis":
        return CourseInfo("大三", "实变函数", "数学分析")
    if subject == "Set theory and logic":
        return CourseInfo("大一", "证明方法入门", "数学分析")
    if subject in {"Operations research", "Combinatorics", "Graph theory"}:
        return CourseInfo("大四", "数学建模与综合专题", "综合应用")
    return None


def normalize_tag(value: str | None, fallback: str) -> str:
    text_value = re.sub(r"[_\s]+", " ", str(value or "").strip().strip("'\""))
    text_value = re.sub(r"\s+", " ", text_value).strip()
    return text_value[:150] or fallback


def parse_metadata(content: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for key in [
        "DBsubject",
        "DBchapter",
        "DBsection",
        "Level",
        "KEYWORDS",
        "Institution",
        "Author",
        "TitleText1",
        "Section1",
        "Problem1",
    ]:
        match = re.search(rf"##\s*{re.escape(key)}\((.*?)\)", content)
        if match:
            metadata[key] = match.group(1).strip()
    return metadata


def extract_text_block(content: str) -> str:
    blocks = re.findall(r"BEGIN_TEXT(.*?)END_TEXT", content, flags=re.S)
    if blocks:
        raw = "\\n".join(blocks)
    else:
        match = re.search(r"##DESCRIPTION(.*?)##ENDDESCRIPTION", content, flags=re.S)
        raw = match.group(1) if match else ""

    raw = raw.replace("$BR", "\n").replace("$PAR", "\n")
    raw = re.sub(r"\\\{[^{}]*(?:ans_rule|ans_array|ans_box)[^{}]*\\\}", "____", raw)
    raw = re.sub(r"\{[^{}]*(?:ans_rule|ans_array|ans_box)[^{}]*\}", "____", raw)
    raw = re.sub(r"\$[A-Za-z_][A-Za-z0-9_]*(?:->\w+\([^)]*\))?", "□", raw)
    raw = re.sub(r"\b(BEGIN|END)_(HTML|TEXT)\b", " ", raw)
    raw = re.sub(r"\\\(|\\\)|\\\[|\\\]", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    raw = raw.replace(" ,", ",").replace(" .", ".")
    return raw[:1200]


def extract_answer_info(content: str) -> str:
    parts: list[str] = []
    for pattern in [
        r"\$ans\s*=\s*([^;\n]+)",
        r"\$answer\s*=\s*([^;\n]+)",
        r"\$correct\s*=\s*([^;\n]+)",
    ]:
        for match in re.finditer(pattern, content):
            parts.append(match.group(0).strip())
            if len(parts) >= 3:
                break
    if len(parts) < 3:
        for match in re.finditer(r"ANS\((.*?)\);", content, flags=re.S):
            text_value = re.sub(r"\s+", " ", match.group(1)).strip()
            parts.append(f"ANS({text_value})")
            if len(parts) >= 3:
                break
    if parts:
        return "WeBWorK 判题表达式：" + "；".join(parts)
    return "源题使用 WeBWorK 自动判题器，标准答案需结合源文件中的 ANS 配置生成。"


def difficulty_from(metadata: dict[str, str]) -> int:
    level = re.sub(r"\D+", "", metadata.get("Level", ""))
    if level:
        return max(1, min(5, int(level)))
    chapter = metadata.get("DBchapter", "").lower()
    if any(word in chapter for word in ["applications", "higher order", "vector", "abstract", "laplace"]):
        return 4
    if any(word in chapter for word in ["limits", "linear", "probability", "differentiation"]):
        return 2
    return 3


def key_steps_for(qtype: str, tag: str) -> list[str]:
    if qtype == "choice":
        return ["识别题目所属课程", "判断核心知识点", "排除相近但不匹配的概念"]
    if qtype == "blank":
        return ["定位题干要求", "写出相关定义或公式", "化简后填写结果"]
    if qtype == "calculation":
        return ["列出已知条件", "转化为标准形式", "逐步计算", "回代或检验结果"]
    if qtype == "proof":
        return ["明确待证命题", "展开定义", "说明定理适用条件", "闭合逻辑链"]
    return ["识别薄弱知识点", "拆分子问题", "选择合适工具", "复盘错因并安排回炉练习"]


def mistake_tags_for(qtype: str) -> list[str]:
    if qtype == "proof":
        return ["证明断链", "条件遗漏"]
    if qtype == "calculation":
        return ["计算失误", "步骤缺失"]
    if qtype == "comprehensive":
        return ["建模不足", "题意误读"]
    return ["概念不清", "条件遗漏"]


def options_for(correct: str) -> tuple[str, str, str, str]:
    distractors = [
        "只记忆最终公式，不检查使用条件",
        "把相近概念视为完全等价",
        "忽略题干中的变量范围和限制",
    ]
    return correct, distractors[0], distractors[1], distractors[2]


def build_question(
    index: int,
    path: Path,
    metadata: dict[str, str],
    source_text: str,
    answer_info: str,
) -> dict[str, Any] | None:
    subject = clean_subject(metadata.get("DBsubject"))
    chapter = normalize_tag(metadata.get("DBchapter"), subject)
    section = normalize_tag(metadata.get("DBsection"), chapter)
    course = course_for(subject, chapter, section)
    if not course:
        return None

    qtype = QUESTION_TYPES[index % len(QUESTION_TYPES)]
    source_rel = path.relative_to(OPL_ROOT).as_posix()
    summary = source_text or metadata.get("KEYWORDS") or f"{subject} / {chapter} / {section}"
    summary = re.sub(r"\s+", " ", summary).strip()[:900]

    if len(summary) < 30:
        return None

    fine_tag = section if section and section != chapter else chapter
    difficulty = difficulty_from(metadata)
    common_errors = mistake_tags_for(qtype)
    key_steps = key_steps_for(qtype, chapter)
    analysis = (
        f"该题来自 WeBWorK Open Problem Library，主题为 {subject} / {chapter} / {section}。"
        f"学习时应先判断题目对象和适用条件，再按 {course.course} 的标准方法完成。"
    )

    row: dict[str, Any] = {
        "source_question_no": f"OPL-{index + 1:05d}",
        "source_path": source_rel,
        "question_type": qtype,
        "stage": course.stage,
        "course": course.course,
        "knowledge_tag": chapter,
        "fine_tag": fine_tag,
        "difficulty": difficulty,
        "standard_answer": answer_info,
        "analysis_text": analysis,
        "key_steps": json.dumps(key_steps, ensure_ascii=False),
        "common_errors": json.dumps(common_errors, ensure_ascii=False),
        "mistake_tags": json.dumps(common_errors, ensure_ascii=False),
    }

    if qtype == "choice":
        a, b, c, d = options_for(chapter)
        row.update(
            {
                "question_text": f"阅读开放题源摘要，判断这道题主要考查的核心知识点是哪一项：{summary}",
                "option_a": a,
                "option_b": b,
                "option_c": c,
                "option_d": d,
                "correct_answer": "A",
                "standard_answer": f"正确选项：A。核心知识点为 {chapter}。源题判题信息：{answer_info}",
            }
        )
    else:
        row.update(
            {
                "question_text": f"开放题源练习（{subject} / {chapter} / {section}）：{summary}",
                "option_a": None,
                "option_b": None,
                "option_c": None,
                "option_d": None,
                "correct_answer": None,
            }
        )
    return row


def iter_opl_questions(limit: int = 680) -> list[dict[str, Any]]:
    if not OPL_LIBRARY.exists():
        raise RuntimeError(f"WeBWorK OPL not found: {OPL_LIBRARY}")

    rows: list[dict[str, Any]] = []
    subject_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    paths = sorted(OPL_LIBRARY.rglob("*.pg"), key=lambda item: item.as_posix().lower())
    for path in paths:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        metadata = parse_metadata(content)
        subject = clean_subject(metadata.get("DBsubject"))
        quota = SUBJECT_QUOTAS.get(subject)
        if quota is None or subject_counts[subject] >= quota:
            continue
        text_block = extract_text_block(content)
        answer_info = extract_answer_info(content)
        row = build_question(len(rows), path, metadata, text_block, answer_info)
        if not row:
            continue
        rows.append(row)
        subject_counts[subject] += 1
        type_counts[row["question_type"]] += 1
        if len(rows) >= limit:
            break
    if len(rows) < 500:
        raise RuntimeError(f"Only parsed {len(rows)} usable OPL questions; expected at least 500.")
    return rows


def build_graph(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_stage: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in rows:
        by_stage[row["stage"]][row["course"]].add(row["knowledge_tag"])

    stages = []
    for order, stage_name in enumerate(["大一", "大二", "大三", "大四"], start=1):
        title, goal = STAGE_INFO[stage_name]
        courses = []
        for course_name, tags in sorted(by_stage.get(stage_name, {}).items()):
            courses.append(
                {
                    "name": course_name,
                    "children": [
                        {"name": tag, "children": [{"name": "基础识别"}, {"name": "方法应用"}, {"name": "错因复盘"}]}
                        for tag in sorted(tags)
                    ],
                }
            )
        stages.append({"name": stage_name, "order": order, "title": title, "goal": goal, "children": courses})

    return {
        "name": "大学数学知识图谱",
        "description": "基于 WeBWorK OPL 开放题源主题整理，覆盖本科数学四个阶段。",
        "stages": stages,
    }


def write_processed_files(rows: list[dict[str, Any]], graph: dict[str, Any]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    fieldnames = [
        "source_question_no",
        "source_path",
        "question_type",
        "stage",
        "course",
        "knowledge_tag",
        "fine_tag",
        "difficulty",
        "question_text",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "correct_answer",
        "standard_answer",
        "analysis_text",
        "key_steps",
        "common_errors",
        "mistake_tags",
    ]
    with QUESTIONS_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    GRAPH_JSON.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    SOURCES_JSON.write_text(
        json.dumps(
            [
                {
                    "source_name": "WeBWorK Open Problem Library",
                    "source_url": "https://github.com/openwebwork/webwork-open-problem-library",
                    "license_name": "Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported",
                    "license_url": "http://creativecommons.org/licenses/by-nc-sa/3.0/",
                    "usage_note": "题目来源；本项目保留源路径与许可证信息。",
                },
                {
                    "source_name": "MIT OCW 18.01SC Single Variable Calculus",
                    "source_url": "https://ocw.mit.edu/courses/18-01sc-single-variable-calculus-fall-2010/",
                    "license_name": "Creative Commons BY-NC-SA",
                    "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                    "usage_note": "课程结构参考。",
                },
                {
                    "source_name": "OpenStax",
                    "source_url": "https://openstax.org/subjects",
                    "license_name": "Creative Commons Attribution",
                    "license_url": "https://creativecommons.org/licenses/by/4.0/",
                    "usage_note": "开放教材结构参考。",
                },
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def latest_backup() -> Path | None:
    backups = sorted(BACKUP_DIR.glob("xingce_backup_*.sql"), key=lambda path: path.stat().st_mtime, reverse=True)
    return backups[0] if backups else None


def backup_xingce(url: URL) -> Path | None:
    if url.database != "xingce":
        return latest_backup()
    BACKUP_DIR.mkdir(exist_ok=True)
    backup_path = BACKUP_DIR / f"xingce_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    mysqldump = r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe"
    env = os.environ.copy()
    if url.password:
        env["MYSQL_PWD"] = url.password
    cmd = [
        mysqldump,
        "-h",
        url.host or "localhost",
        "-P",
        str(url.port or 3306),
        "-u",
        url.username or "root",
        "--default-character-set=utf8mb4",
        "--routines",
        "--triggers",
        "--single-transaction",
        url.database,
    ]
    with backup_path.open("wb") as out:
        result = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, env=env)
    if result.returncode != 0:
        backup_path.unlink(missing_ok=True)
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[:1000])
    if backup_path.stat().st_size <= 0:
        backup_path.unlink(missing_ok=True)
        raise RuntimeError("Backup file is empty.")
    return backup_path


def engine_without_database(url: URL):
    server_url = url.set(database=None)
    return create_engine(server_url, pool_pre_ping=True)


def engine_for_math(url: URL):
    math_url = url.set(database="math_brain")
    return create_engine(math_url, pool_pre_ping=True)


def split_sql(sql_text: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current).rstrip(";"))
            current = []
    if current:
        statements.append("\n".join(current))
    return statements


def replace_database(url: URL) -> None:
    server_engine = engine_without_database(url)
    with server_engine.begin() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS xingce"))
        conn.execute(text("DROP DATABASE IF EXISTS math_brain"))
        conn.execute(text("CREATE DATABASE math_brain DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"))

    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    math_engine = engine_for_math(url)
    with math_engine.begin() as conn:
        for statement in split_sql(schema_text):
            if statement.strip().upper().startswith("CREATE DATABASE"):
                continue
            if statement.strip().upper().startswith("USE "):
                continue
            conn.execute(text(statement))


def insert_rows(url: URL, rows: list[dict[str, Any]], graph: dict[str, Any]) -> dict[str, Any]:
    math_engine = engine_for_math(url)
    with math_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO source_attributions (source_name, source_url, license_name, license_url, usage_note)
                VALUES
                  ('WeBWorK Open Problem Library', 'https://github.com/openwebwork/webwork-open-problem-library',
                   'Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported',
                   'http://creativecommons.org/licenses/by-nc-sa/3.0/',
                   '题目来源；保留源路径与许可证信息。'),
                  ('MIT OCW 18.01SC Single Variable Calculus',
                   'https://ocw.mit.edu/courses/18-01sc-single-variable-calculus-fall-2010/',
                   'Creative Commons BY-NC-SA',
                   'https://creativecommons.org/licenses/by-nc-sa/4.0/',
                   '课程结构参考。'),
                  ('OpenStax', 'https://openstax.org/subjects',
                   'Creative Commons Attribution',
                   'https://creativecommons.org/licenses/by/4.0/',
                   '开放教材结构参考。')
                """
            )
        )
        source_id = conn.execute(
            text("SELECT id FROM source_attributions WHERE source_name = 'WeBWorK Open Problem Library'")
        ).scalar_one()

        stage_ids: dict[str, int] = {}
        for order, stage_name in enumerate(["大一", "大二", "大三", "大四"], start=1):
            title, goal = STAGE_INFO[stage_name]
            result = conn.execute(
                text(
                    """
                    INSERT INTO math_stages (stage_name, stage_order, title, goal_text)
                    VALUES (:stage_name, :stage_order, :title, :goal_text)
                    """
                ),
                {"stage_name": stage_name, "stage_order": order, "title": title, "goal_text": goal},
            )
            stage_ids[stage_name] = int(result.lastrowid)

        course_keys = sorted({(row["stage"], row["course"]) for row in rows})
        for index, (stage, course) in enumerate(course_keys, start=1):
            group = next(row for row in rows if row["stage"] == stage and row["course"] == course)["course"]
            conn.execute(
                text(
                    """
                    INSERT INTO math_courses (stage_id, course_name, course_group, course_order, description)
                    VALUES (:stage_id, :course_name, :course_group, :course_order, :description)
                    """
                ),
                {
                    "stage_id": stage_ids[stage],
                    "course_name": course,
                    "course_group": group,
                    "course_order": index,
                    "description": f"{stage}阶段课程：{course}",
                },
            )

        node_ids: dict[tuple[str, str, str], int] = {}
        sort_order = 1
        for stage in ["大一", "大二", "大三", "大四"]:
            stage_courses = sorted({row["course"] for row in rows if row["stage"] == stage})
            for course in stage_courses:
                course_code = f"{stage}-{course}"
                result = conn.execute(
                    text(
                        """
                        INSERT INTO knowledge_nodes (node_code, parent_id, stage_name, course_name, name, level, sort_order, description)
                        VALUES (:node_code, NULL, :stage_name, :course_name, :name, 2, :sort_order, :description)
                        """
                    ),
                    {
                        "node_code": course_code,
                        "stage_name": stage,
                        "course_name": course,
                        "name": course,
                        "sort_order": sort_order,
                        "description": f"{stage}课程节点",
                    },
                )
                parent_id = int(result.lastrowid)
                sort_order += 1
                tags = sorted({row["knowledge_tag"] for row in rows if row["stage"] == stage and row["course"] == course})
                for tag in tags:
                    code = f"{stage}-{course}-{tag}"[:120]
                    result = conn.execute(
                        text(
                            """
                            INSERT INTO knowledge_nodes (node_code, parent_id, stage_name, course_name, name, level, sort_order, description)
                            VALUES (:node_code, :parent_id, :stage_name, :course_name, :name, 3, :sort_order, :description)
                            """
                        ),
                        {
                            "node_code": code,
                            "parent_id": parent_id,
                            "stage_name": stage,
                            "course_name": course,
                            "name": tag,
                            "sort_order": sort_order,
                            "description": f"{course}：{tag}",
                        },
                    )
                    node_ids[(stage, course, tag)] = int(result.lastrowid)
                    sort_order += 1

        conn.execute(
            text(
                """
                INSERT INTO mistake_tags (tag_name, description)
                VALUES (:tag_name, :description)
                """
            ),
            [{"tag_name": name, "description": desc} for name, desc in MISTAKE_TAGS.items()],
        )

        insert_payload = []
        for row in rows:
            item = dict(row)
            item["source_id"] = source_id
            item["knowledge_node_id"] = node_ids.get((row["stage"], row["course"], row["knowledge_tag"]))
            insert_payload.append(item)

        conn.execute(
            text(
                """
                INSERT INTO questions (
                  source_id, source_question_no, source_path, question_type, stage, course,
                  knowledge_node_id, knowledge_tag, fine_tag, difficulty, question_text,
                  option_a, option_b, option_c, option_d, correct_answer, standard_answer,
                  analysis_text, key_steps, common_errors, mistake_tags
                )
                VALUES (
                  :source_id, :source_question_no, :source_path, :question_type, :stage, :course,
                  :knowledge_node_id, :knowledge_tag, :fine_tag, :difficulty, :question_text,
                  :option_a, :option_b, :option_c, :option_d, :correct_answer, :standard_answer,
                  :analysis_text, :key_steps, :common_errors, :mistake_tags
                )
                """
            ),
            insert_payload,
        )

        report = {
            "database": conn.execute(text("SELECT DATABASE()")).scalar_one(),
            "question_count": conn.execute(text("SELECT COUNT(*) FROM questions")).scalar_one(),
            "stage_counts": dict(conn.execute(text("SELECT stage, COUNT(*) FROM questions GROUP BY stage")).fetchall()),
            "type_counts": dict(conn.execute(text("SELECT question_type, COUNT(*) FROM questions GROUP BY question_type")).fetchall()),
            "source_count": conn.execute(text("SELECT COUNT(*) FROM source_attributions")).scalar_one(),
            "knowledge_node_count": conn.execute(text("SELECT COUNT(*) FROM knowledge_nodes")).scalar_one(),
        }
    return report


def update_env_database_name() -> None:
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        return
    text_value = env_path.read_text(encoding="utf-8")
    updated = re.sub(r"(DATABASE_URL\s*=\s*.+/)(xingce)(\b|\?|$)", r"\1math_brain\3", text_value)
    if updated != text_value:
        env_path.write_text(updated, encoding="utf-8")


def write_report(report: dict[str, Any], backup_path: Path | None) -> None:
    full_report = {
        **report,
        "backup_path": str(backup_path) if backup_path else None,
        "questions_csv": str(QUESTIONS_CSV),
        "knowledge_graph": str(GRAPH_JSON),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    REPORT_JSON.write_text(json.dumps(full_report, ensure_ascii=False, indent=2), encoding="utf-8")
    MIGRATION_LOG.write_text(
        "\n".join(
            [
                "# Math Database Migration Log",
                "",
                f"- Generated at: {full_report['generated_at']}",
                f"- Backup: {full_report['backup_path']}",
                "- Dropped database: `xingce`",
                "- Created database: `math_brain`",
                f"- Questions imported: {full_report['question_count']}",
                f"- Knowledge nodes: {full_report['knowledge_node_count']}",
                f"- Source rows: {full_report['source_count']}",
                f"- Stage counts: `{full_report['stage_counts']}`",
                f"- Type counts: `{full_report['type_counts']}`",
                "- Primary source: WeBWorK Open Problem Library, CC BY-NC-SA 3.0",
                "- Local `.env` database name updated to `math_brain`; secrets were not written to tracked files.",
                "",
                "Restore old database if needed:",
                "",
                "```powershell",
                "mysql -u root -p < backups/xingce_backup_YYYYMMDD_HHMMSS.sql",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    url = make_url(database_url)
    backup_path = backup_xingce(url)
    rows = iter_opl_questions()
    graph = build_graph(rows)
    write_processed_files(rows, graph)
    replace_database(url)
    report = insert_rows(url, rows, graph)
    update_env_database_name()
    write_report(report, backup_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
