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

export async function streamChat(payload, { onSession, onDelta }) {
  const response = await fetch(buildUrl("/api/chat"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok || !response.body) {
    throw new Error(await response.text());
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
      const line = event.split("\n").find((item) => item.startsWith("data:"));
      if (!line) {
        continue;
      }
      const data = line.replace(/^data:\s*/, "");
      if (data === "[DONE]") {
        return;
      }
      const parsed = JSON.parse(data);
      if (parsed.session_id) {
        onSession?.(parsed.session_id);
      }
      if (parsed.delta) {
        onDelta?.(parsed.delta);
      }
    }
  }
}
