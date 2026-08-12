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
    try:
        return json.dumps(strategy_input, ensure_ascii=False, indent=2)
    except TypeError:
        return str(strategy_input)


def plan(strategy_input: Any) -> str:
    messages = [
        {"role": "system", "content": _load_prompt()},
        {"role": "user", "content": f"请根据以下诊断结果生成一周大学数学学习计划：\n{_format_strategy_input(strategy_input)}"},
    ]
    return call_llm(messages, temperature=0.35, max_tokens=1200)
