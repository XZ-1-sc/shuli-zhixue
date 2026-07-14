import json
from pathlib import Path
from typing import Any

from ..utils.llm_client import call_llm


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "strategist.txt"


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def _format_strategy_input(strategy_input: Any) -> str:
    if isinstance(strategy_input, str):
        return strategy_input.strip()

    if not strategy_input:
        return "暂无诊断结果。"

    if isinstance(strategy_input, dict):
        return json.dumps(strategy_input, ensure_ascii=False, indent=2)

    try:
        return "\n".join(
            json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item)
            for item in strategy_input
        )
    except TypeError:
        return str(strategy_input)


def plan(strategy_input: Any) -> str:
    diagnosis_text = _format_strategy_input(strategy_input)
    system_prompt = _load_prompt()
    user_prompt = (
        "请根据以下诊断结果，制定接下来一周的行测学习优先级，并严格按照指定格式输出。\n\n"
        f"诊断结果：\n{diagnosis_text}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return call_llm(messages)
