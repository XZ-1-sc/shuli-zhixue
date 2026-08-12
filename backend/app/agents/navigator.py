import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..database.session import SessionLocal


COURSE_KEYWORDS = [
    "高等数学上",
    "高等数学下",
    "线性代数上",
    "线性代数下",
    "概率论与数理统计",
    "级数与常微分方程",
    "复变函数",
    "实变函数",
    "抽象代数",
    "数学建模与综合专题",
]


def _row_to_question(row: Any) -> dict[str, Any]:
    item = dict(row._mapping)
    item["options"] = {
        "A": item.pop("option_a", None),
        "B": item.pop("option_b", None),
        "C": item.pop("option_c", None),
        "D": item.pop("option_d", None),
    }
    item["options"] = {key: value for key, value in item["options"].items() if value}
    return item


def _extract_course(strategy: str) -> str:
    for course in COURSE_KEYWORDS:
        if course in strategy:
            return course
    if "线性代数" in strategy:
        return "线性代数上"
    if "概率" in strategy or "统计" in strategy:
        return "概率论与数理统计"
    if "微分方程" in strategy or "级数" in strategy:
        return "级数与常微分方程"
    return "高等数学上"


def _extract_knowledge_tag(strategy: str) -> str | None:
    candidates = re.findall(r"(极限|连续|导数|积分|矩阵|特征值|概率|级数|微分方程|复变|实变|群|环|建模)", strategy)
    if not candidates:
        return None
    keyword = candidates[0]
    mapping = {
        "极限": "Limits",
        "连续": "Limits",
        "导数": "Differentiation",
        "积分": "Integration",
        "矩阵": "Matrices",
        "特征值": "Eigenvalues",
        "概率": "Probability",
        "级数": "Series",
        "微分方程": "Differential Equations",
    }
    return mapping.get(keyword, keyword)


def recommend(strategy: str, limit: int = 10) -> list[dict[str, Any]]:
    course = _extract_course(strategy)
    knowledge_tag = _extract_knowledge_tag(strategy)
    params: dict[str, Any] = {"course": course, "limit": limit}
    filters = ["course = :course"]
    if knowledge_tag:
        filters.append("(knowledge_tag = :knowledge_tag OR fine_tag = :knowledge_tag)")
        params["knowledge_tag"] = knowledge_tag

    query = text(
        f"""
        SELECT
          id, question_text, option_a, option_b, option_c, option_d,
          question_type, correct_answer, stage, course, knowledge_tag, fine_tag, difficulty
        FROM questions
        WHERE {" AND ".join(filters)}
        ORDER BY difficulty ASC, RAND()
        LIMIT :limit
        """
    )
    try:
        with SessionLocal() as db:
            rows = db.execute(query, params).fetchall()
            if not rows and knowledge_tag:
                rows = db.execute(
                    text(
                        """
                        SELECT
                          id, question_text, option_a, option_b, option_c, option_d,
                          question_type, correct_answer, stage, course, knowledge_tag, fine_tag, difficulty
                        FROM questions
                        WHERE course = :course
                        ORDER BY difficulty ASC, RAND()
                        LIMIT :limit
                        """
                    ),
                    {"course": course, "limit": limit},
                ).fetchall()
    except SQLAlchemyError:
        return []
    return [_row_to_question(row) for row in rows]
