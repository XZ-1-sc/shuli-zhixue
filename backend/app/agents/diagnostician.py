import json
from pathlib import Path
from typing import Any

from ..utils.llm_client import call_llm


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "diagnostician.txt"


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def _format_records(user_records: Any) -> str:
    if isinstance(user_records, str):
        return user_records.strip()
    if not user_records:
        return "暂无做题记录。"
    try:
        return json.dumps(user_records, ensure_ascii=False, indent=2)
    except TypeError:
        return str(user_records)


def diagnose(user_records: Any) -> str:
    messages = [
        {"role": "system", "content": _load_prompt()},
        {"role": "user", "content": f"请根据以下大学数学做题记录输出诊断：\n{_format_records(user_records)}"},
    ]
    return call_llm(messages, temperature=0.2, max_tokens=900)
