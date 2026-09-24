// Loaded only by Selenium before the app. Never imported by production code.
(() => {
  const test = window.__voiceTest = { requests: [], spoken: [], microphones: [], idle: null, failure: null };
  const role = new URLSearchParams(location.search).get("voiceRole") || "teacher";
  const fakeUser = { user_id: 999999, username: "语音界面测试", role };
  localStorage.setItem("math_brain_current_user", JSON.stringify(fakeUser));
  const actualFetch = window.fetch.bind(window);
  window.fetch = async (input, options = {}) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (!url.pathname.startsWith("/api/")) return actualFetch(input, options);
    if (url.pathname === "/api/chat") {
      test.requests.push(JSON.parse(options.body));
      if (test.holdReply) await new Promise((resolve) => { test.releaseReply = resolve; });
      if (test.failure === "chat") {
        test.failure = null;
        return new Response(JSON.stringify({ detail: "测试：回答服务暂不可用" }), { status: 503 });
      }
      const encoder = new TextEncoder();
      return new Response(new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('data: {"session_id":"voice-browser-session"}\n\n'));
          controller.enqueue(encoder.encode('data: {"type":"delta","text":"先观察函数的变化。"}\n\n'));
          setTimeout(() => {
            controller.enqueue(encoder.encode('data: {"type":"delta","text":"再用一个例子验证。"}\n\n'));
            controller.enqueue(encoder.encode('data: [DONE]\n\n'));
            controller.close();
          }, 100);
        }
      }), { headers: { "Content-Type": "text/event-stream" } });
    }
    const data = {
      "/api/auth/me": fakeUser,
      "/api/messages/conversations": { items: [] },
      "/api/notifications/summary": { unread_count: 0, latest: null },
      "/api/chat/sessions": { sessions: [{ session_id: "voice-browser-session", message_count: 2, last_message_at: "2026-09-05T10:00:00" }] },
      "/api/chat/history": { messages: [{ id: 1, role: "assistant", content: "历史对话仍可查看。" }] }
    };
    return new Response(JSON.stringify(data[url.pathname] || {}), { headers: { "Content-Type": "application/json" } });
  };
  const timeout = window.setTimeout.bind(window);
  window.setTimeout = (callback, delay, ...args) => {
    if (delay === 30000) test.idle = callback;
    return timeout(callback, delay, ...args);
  };
  class Recognition {
    constructor() { this.results = []; test.microphones.push(this); }
    start() { this.active = true; timeout(() => this.onstart?.(), 1); }
    abort() { this.active = false; }
    hear(text, final = true) {
      const result = Object.assign([{ transcript: text }], { isFinal: final });
      if (this.results.at(-1)?.isFinal === false) this.results[this.results.length - 1] = result;
      else this.results.push(result);
      this.onresult?.({ resultIndex: this.results.length - 1, results: this.results });
    }
  }
  class Utterance { constructor(text) { this.text = text; } }
  const synthesis = Object.assign(new EventTarget(), {
    speaking: false, current: null,
    getVoices: () => [
      { name: "Microsoft Xiaoxiao Online (Natural)", lang: "zh-CN", localService: false },
      { name: "Microsoft Huihui Desktop", lang: "zh-CN", localService: true }
    ],
    speak(utterance) {
      this.current = utterance;
      this.speaking = true;
      test.spoken.push({ text: utterance.text, voice: utterance.voice.name });
      timeout(() => utterance.onstart?.(), 1);
    },
    cancel() { this.current = null; this.speaking = false; }
  });
  Object.defineProperty(window, "SpeechRecognition", { configurable: true, value: Recognition });
  Object.defineProperty(window, "SpeechSynthesisUtterance", { configurable: true, value: Utterance });
  Object.defineProperty(window, "speechSynthesis", { configurable: true, value: synthesis });
  test.hear = (text, final = true) => test.microphones.at(-1).hear(text, final);
  test.finish = () => { const current = synthesis.current; synthesis.current = null; synthesis.speaking = false; current?.onend?.(); };
  test.error = (error) => test.microphones.at(-1).onerror?.({ error });
  test.ttsError = (error) => synthesis.current?.onerror?.({ error });
})();
