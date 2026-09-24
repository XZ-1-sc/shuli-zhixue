import json
import re
from typing import Any


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

def _parse_solution_steps(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []

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
    item["solution_steps"] = _parse_solution_steps(item.get("solution_steps"))
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
      q.solution_steps,
      q.steps_source,
      q.steps_review_status,
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
