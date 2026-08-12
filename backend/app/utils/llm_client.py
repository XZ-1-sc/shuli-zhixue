import os
import time
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    requests = None
    RequestException = Exception
else:
    RequestException = requests.RequestException

try:
    from dotenv import load_dotenv
except ImportError:

    def load_dotenv(*args: Any, **kwargs: Any) -> None:
        return None


BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE)

DEFAULT_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
DEFAULT_FALLBACK_REPLY = "小逻暂时连不上大模型。你可以先完成一组基础题，我会根据本地做题记录继续给出诊断和复盘建议。"


def call_llm(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    timeout: int = 30,
    retries: int = 1,
) -> str:
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")

    if requests is None or not api_key:
        return DEFAULT_FALLBACK_REPLY

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    for attempt in range(retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])
        except (RequestException, KeyError, IndexError, ValueError):
            if attempt < retries:
                time.sleep(2)

    return DEFAULT_FALLBACK_REPLY
