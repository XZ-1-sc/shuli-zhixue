import { notify } from "../services/toast";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

function buildUrl(path, params = {}) {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  return url.toString();
}

async function readJson(response) {
  const text = await response.text();
  if (!response.ok) {
    let detail = text;
    try {
      detail = JSON.parse(text).detail || text;
    } catch (error) {
      detail = text || `HTTP ${response.status}`;
    }
    if (response.status >= 500 && (!detail || /^internal server error$/i.test(String(detail).trim()))) {
      detail = "服务器暂时无法处理请求，请稍后重试。";
    }
    notify(detail);
    throw new Error(detail);
  }
  return text ? JSON.parse(text) : {};
}

export async function apiGet(path, params = {}) {
  return readJson(await fetch(buildUrl(path, params), { credentials: "include" }));
}

export async function apiPost(path, body = {}) {
  return readJson(
    await fetch(buildUrl(path), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
  );
}

export async function apiUpload(path, formData) {
  return readJson(
    await fetch(buildUrl(path), {
      method: "POST",
      credentials: "include",
      body: formData
    })
  );
}

export async function apiPut(path, body = {}) {
  return readJson(
    await fetch(buildUrl(path), {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
  );
}

export async function apiDelete(path, params = {}) {
  return readJson(
    await fetch(buildUrl(path, params), {
      method: "DELETE",
      credentials: "include"
    })
  );
}

export async function streamChat(
  payload,
  { onSession, onThinking, onDelta, onCard, onAction, onEvent, onDone } = {}
) {
  const response = await fetch(buildUrl("/api/chat"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok || !response.body) {
    const raw = await response.text();
    try {
      throw new Error(JSON.parse(raw).detail || raw);
    } catch (error) {
      if (error instanceof SyntaxError) throw new Error(raw || `HTTP ${response.status}`);
      throw error;
    }
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";
    for (const event of events) {
      const data = event
        .split(/\r?\n/)
        .filter((item) => item.startsWith("data:"))
        .map((item) => item.replace(/^data:\s?/, ""))
        .join("\n");
      if (!data) {
        continue;
      }
      if (data === "[DONE]") {
        onDone?.();
        return;
      }
      const parsed = JSON.parse(data);
      onEvent?.(parsed);
      if (parsed.session_id) {
        onSession?.(parsed.session_id);
      }
      if (parsed.type === "thinking") onThinking?.(parsed);
      const delta = parsed.type === "delta" ? parsed.text ?? parsed.delta : parsed.delta;
      if (delta) onDelta?.(delta, parsed);
      if (parsed.type === "card" && parsed.card) onCard?.(parsed.card);
      if (parsed.type === "action" && parsed.action) onAction?.(parsed.action);
    }
  }
  onDone?.();
}
