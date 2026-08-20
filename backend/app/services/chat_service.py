import asyncio
import json
from collections.abc import AsyncIterator

from ..database.repositories.chat import (
    CHAT_SYSTEM_PROMPT,
    _assert_chat_session_owner_sync,
    _load_chat_context,
    _normalize_session_id,
    _save_chat_message,
)
from ..database.repositories.diagnosis import _diagnose_sync
from ..utils.llm_client import call_llm


async def chat_event_stream(user_id: int, message: str, requested_session_id: str | None) -> AsyncIterator[str]:
    session_id = _normalize_session_id(requested_session_id)
    await asyncio.to_thread(_assert_chat_session_owner_sync, user_id, session_id)
    previous_messages = await asyncio.to_thread(_load_chat_context, user_id, session_id)
    diagnosis = await asyncio.to_thread(_diagnose_sync, user_id)
    messages = [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"当前诊断摘要：{diagnosis.get('summary')}；薄弱点：{json.dumps(diagnosis.get('weak_points'), ensure_ascii=False)}",
        },
        *previous_messages,
        {"role": "user", "content": f"<student_input>{message}</student_input>"},
    ]
    reply = await asyncio.to_thread(
        call_llm,
        messages,
        conversation_id=session_id,
        agent_name="chat_assistant",
    )
    if not reply:
        reply = "我建议先做一组极限与连续的基础题，再把错误按“概念混淆 / 计算失误 / 思路断点”三类标注。"

    await asyncio.to_thread(_save_chat_message, user_id, session_id, "user", message)
    await asyncio.to_thread(_save_chat_message, user_id, session_id, "assistant", reply)

    yield f"data: {json.dumps({'session_id': session_id}, ensure_ascii=False)}\n\n"
    for char in reply:
        yield f"data: {json.dumps({'delta': char}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.025)
    yield "data: [DONE]\n\n"
