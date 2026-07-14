import json
from pathlib import Path
from typing import Any

from ..utils.llm_client import call_llm


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "diagnostician.txt"


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def _format_record(record: Any, index: int) -> str:
    if isinstance(record, dict):
        return f"{index}. " + json.dumps(record, ensure_ascii=False)
    return f"{index}. {record}"


def _format_records(user_records: Any) -> str:
    if isinstance(user_records, str):
        return user_records.strip()

    if not user_records:
        return "暂无做题记录。"

    try:
        return "\n".join(
            _format_record(record, index)
            for index, record in enumerate(user_records, start=1)
        )
    except TypeError:
        return str(user_records)


def diagnose(user_records: Any) -> str:
    records_text = _format_records(user_records)
    system_prompt = _load_prompt()
    user_prompt = (
        "请根据以下用户做题记录，诊断三个最薄弱的环节，并严格按照指定格式输出。\n\n"
        f"用户做题记录：\n{records_text}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return call_llm(messages)
