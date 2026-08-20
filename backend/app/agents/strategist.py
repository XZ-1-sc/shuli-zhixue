import json
from pathlib import Path

from ..utils.llm_client import call_llm_json
from .schemas import Diagnosis, WeeklyPlan


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "strategist.txt"


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def _fallback_plan(diagnosis: Diagnosis) -> WeeklyPlan:
    if not diagnosis.weak_points:
        return WeeklyPlan(
            focus_course="高等数学上",
            focus_knowledge="极限与导数基础",
            daily_hours=1.0,
            priority_order=["完成首测", "复习核心定义", "基础题训练", "错题复盘"],
            give_up_types=["高难综合证明题", "超出当前阶段的竞赛题"],
        )
    primary = diagnosis.weak_points[0]
    return WeeklyPlan(
        focus_course=primary.course,
        focus_knowledge=primary.knowledge,
        daily_hours=1.5,
        priority_order=[
            *[f"{item.course} - {item.knowledge}" for item in diagnosis.weak_points],
            "同类题巩固",
            "周末错题复盘",
        ],
        give_up_types=["跨阶段高难综合题", "尚无先修基础的证明题"],
    )


def plan(diagnosis: Diagnosis, *, conversation_id: str | None = None) -> WeeklyPlan:
    messages = [
        {"role": "system", "content": _load_prompt()},
        {"role": "user", "content": json.dumps(diagnosis.model_dump(), ensure_ascii=False, indent=2)},
    ]
    result, _ = call_llm_json(
        messages,
        WeeklyPlan,
        fallback=_fallback_plan(diagnosis),
        conversation_id=conversation_id,
        agent_name="strategist",
        temperature=0.3,
        max_tokens=1000,
    )
    return result
