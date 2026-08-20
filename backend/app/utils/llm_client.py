import json
import os
import re
import time
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..agents.schemas import LLMUsage

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

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _record_call(conversation_id: str | None, agent_name: str, usage: LLMUsage) -> None:
    try:
        from ..database.session import SessionLocal

        with SessionLocal() as db:
            db.execute(
                text(
                    """
                    INSERT INTO llm_call_log (
                      conversation_id, agent_name, model, status,
                      prompt_tokens, completion_tokens, total_tokens, latency_ms, error_message
                    ) VALUES (
                      :conversation_id, :agent_name, :model, :status,
                      :prompt_tokens, :completion_tokens, :total_tokens, :latency_ms, :error_message
                    )
                    """
                ),
                {"conversation_id": conversation_id, "agent_name": agent_name[:64], **usage.model_dump()},
            )
            db.commit()
    except (SQLAlchemyError, OSError):
        return


def _request_once(
    messages: list[dict[str, str]],
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
    response_format: dict[str, str] | None = None,
) -> tuple[str, LLMUsage]:
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    if requests is None or not api_key:
        raise RuntimeError("LLM client is unavailable or LLM_API_KEY is not configured")

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format

    started = time.perf_counter()
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    latency_ms = max(0, round((time.perf_counter() - started) * 1000))
    response.raise_for_status()
    data = response.json()
    content = str(data["choices"][0]["message"]["content"])
    raw_usage = data.get("usage") or {}
    usage = LLMUsage(
        model=str(data.get("model") or model),
        prompt_tokens=int(raw_usage.get("prompt_tokens") or 0),
        completion_tokens=int(raw_usage.get("completion_tokens") or 0),
        total_tokens=int(raw_usage.get("total_tokens") or 0),
        latency_ms=latency_ms,
    )
    return content, usage


def call_llm(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    timeout: int = 30,
    retries: int = 1,
    *,
    conversation_id: str | None = None,
    agent_name: str = "chat",
) -> str:
    if requests is None or not os.getenv("LLM_API_KEY", ""):
        usage = LLMUsage(model=model, status="unavailable", error_message="LLM client or API key unavailable")
        _record_call(conversation_id, agent_name, usage)
        return DEFAULT_FALLBACK_REPLY

    for attempt in range(retries + 1):
        try:
            content, usage = _request_once(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            _record_call(conversation_id, agent_name, usage)
            return content
        except (RequestException, KeyError, IndexError, TypeError, ValueError, RuntimeError) as exc:
            usage = LLMUsage(model=model, status="request_error", error_message=str(exc)[:1000])
            _record_call(conversation_id, agent_name, usage)
            if attempt < retries:
                time.sleep(0.5)

    return DEFAULT_FALLBACK_REPLY


def _parse_json_object(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("LLM JSON response is not an object")
    return value


def call_llm_json(
    messages: list[dict[str, str]],
    schema: type[SchemaT],
    *,
    fallback: SchemaT | dict[str, Any],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 1200,
    timeout: int = 30,
    retries: int = 1,
    conversation_id: str | None = None,
    agent_name: str = "agent",
) -> tuple[SchemaT, LLMUsage]:
    fallback_value = fallback if isinstance(fallback, schema) else schema.model_validate(fallback)
    schema_instruction = (
        "只返回一个 JSON 对象，不要使用 Markdown，不要补充解释。对象必须符合以下 JSON Schema：\n"
        + json.dumps(schema.model_json_schema(), ensure_ascii=False)
    )
    structured_messages = [{"role": "system", "content": schema_instruction}, *messages]

    if requests is None or not os.getenv("LLM_API_KEY", ""):
        usage = LLMUsage(model=model, status="fallback_unavailable", error_message="LLM client or API key unavailable")
        _record_call(conversation_id, agent_name, usage)
        return fallback_value, usage

    last_usage = LLMUsage(model=model, status="fallback")
    attempts = max(1, min(2, retries + 1))
    for attempt in range(attempts):
        try:
            content, usage = _request_once(
                structured_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                response_format={"type": "json_object"},
            )
            try:
                parsed = schema.model_validate(_parse_json_object(content))
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
                usage.status = "invalid_json"
                usage.error_message = str(exc)[:1000]
                _record_call(conversation_id, agent_name, usage)
                last_usage = usage
                structured_messages.extend(
                    [
                        {"role": "assistant", "content": content},
                        {"role": "user", "content": "上一个 JSON 不符合 Schema，请修正后只返回合法 JSON 对象。"},
                    ]
                )
                continue
            _record_call(conversation_id, agent_name, usage)
            return parsed, usage
        except (RequestException, KeyError, IndexError, TypeError, ValueError, RuntimeError) as exc:
            last_usage = LLMUsage(model=model, status="request_error", error_message=str(exc)[:1000])
            _record_call(conversation_id, agent_name, last_usage)
            if attempt + 1 < attempts:
                time.sleep(0.5)

    last_usage.status = "fallback_invalid_json"
    return fallback_value, last_usage
