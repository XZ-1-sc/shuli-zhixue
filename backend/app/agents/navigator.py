import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..database.session import SessionLocal


MODULE_NAMES = [
    "言语理解与表达",
    "判断推理",
    "资料分析",
    "数量关系",
    "常识判断",
]

TAG_TO_MODULE = {
    "逻辑填空": "言语理解与表达",
    "阅读理解": "言语理解与表达",
    "片段阅读": "言语理解与表达",
    "标题提炼": "言语理解与表达",
    "下文推断": "言语理解与表达",
    "语句排序": "言语理解与表达",
    "逻辑判断": "判断推理",
    "定义判断": "判断推理",
    "类比推理": "判断推理",
    "图形推理": "判断推理",
    "增长率": "资料分析",
    "比重计算": "资料分析",
    "平均数": "资料分析",
    "倍数与比较": "资料分析",
    "综合分析": "资料分析",
    "数量计算": "数量关系",
    "经济利润问题": "数量关系",
    "工程问题": "数量关系",
    "行程问题": "数量关系",
    "几何问题": "数量关系",
    "排列组合与概率": "数量关系",
    "法律常识": "常识判断",
    "时政热点": "常识判断",
    "常识综合": "常识判断",
    "经济常识": "常识判断",
    "科技与自然": "常识判断",
    "历史人文": "常识判断",
}


@dataclass(frozen=True)
class FocusTarget:
    module: str
    knowledge_tag: str | None = None


def _extract_focus_text(strategy: str) -> str:
    for line in strategy.splitlines():
        if "建议主攻模块" in line:
            return line.split("：", 1)[-1].split(":", 1)[-1].strip()
    return strategy.strip()


def _find_module(text_value: str) -> str | None:
    for module in MODULE_NAMES:
        if module in text_value:
            return module
    for tag, module in TAG_TO_MODULE.items():
        if tag in text_value:
            return module
    return None


def _find_knowledge_tag(text_value: str, module: str | None) -> str | None:
    bracket_match = re.search(r"[（(]([^）)]+)[）)]", text_value)
    if bracket_match:
        bracket_value = bracket_match.group(1).strip()
        for tag in TAG_TO_MODULE:
            if tag in bracket_value:
                return tag
        return bracket_value or None

    for tag, tag_module in TAG_TO_MODULE.items():
        if tag in text_value and (module is None or tag_module == module):
            return tag
    return None


def _parse_focus_targets(strategy: str) -> list[FocusTarget]:
    focus_text = _extract_focus_text(strategy)
    parts = [
        part.strip()
        for part in re.split(r">|＞|,|，|;|；|、|\n", focus_text)
        if part.strip()
    ]

    targets: list[FocusTarget] = []
    seen: set[tuple[str, str | None]] = set()
    for part in parts:
        module = _find_module(part)
        if not module:
            continue
        knowledge_tag = _find_knowledge_tag(part, module)
        key = (module, knowledge_tag)
        if key in seen:
            continue
        targets.append(FocusTarget(module=module, knowledge_tag=knowledge_tag))
        seen.add(key)
    return targets


def _question_row_to_dict(row: Any) -> dict[str, Any]:
    item = dict(row._mapping)
    item["options"] = {
        "A": item.pop("option_a"),
        "B": item.pop("option_b"),
        "C": item.pop("option_c"),
        "D": item.pop("option_d"),
    }
    return item


def recommend(strategy: str, limit: int = 10) -> list[dict[str, Any]]:
    targets = _parse_focus_targets(strategy)
    if not targets:
        return []

    params: dict[str, Any] = {"limit": limit}
    module_conditions: list[str] = []
    priority_cases: list[str] = []

    for index, target in enumerate(targets):
        module_key = f"module_{index}"
        params[module_key] = target.module
        module_conditions.append(f"module = :{module_key}")

        if target.knowledge_tag:
            tag_key = f"tag_{index}"
            params[tag_key] = target.knowledge_tag
            priority_cases.append(
                "WHEN module = :{module_key} AND knowledge_tag = :{tag_key} THEN {priority}".format(
                    module_key=module_key,
                    tag_key=tag_key,
                    priority=index,
                )
            )

    module_priority_offset = len(priority_cases) + 10
    for index, target in enumerate(targets):
        module_key = f"module_{index}"
        priority_cases.append(
            "WHEN module = :{module_key} THEN {priority}".format(
                module_key=module_key,
                priority=module_priority_offset + index,
            )
        )

    query = text(
        """
        SELECT
          id,
          question_text,
          option_a,
          option_b,
          option_c,
          option_d,
          correct_answer,
          module,
          knowledge_tag,
          difficulty,
          source_name,
          source_question_no
        FROM questions
        WHERE {where_clause}
        ORDER BY
          CASE
            {priority_clause}
            ELSE 999
          END,
          difficulty ASC,
          id ASC
        LIMIT :limit
        """.format(
            where_clause=" OR ".join(module_conditions),
            priority_clause="\n            ".join(priority_cases),
        )
    )

    try:
        with SessionLocal() as db:
            rows = db.execute(query, params).fetchall()
    except SQLAlchemyError:
        return []

    return [_question_row_to_dict(row) for row in rows]
