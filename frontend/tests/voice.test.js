import test from "node:test";
import assert from "node:assert/strict";
import { createVoiceSession, isVoiceSupported, pickChineseVoice, speechChunks } from "../src/services/voice.js";

const natural = { name: "Microsoft Xiaoxiao Online (Natural)", lang: "zh-CN", localService: false };
const local = { name: "Microsoft Huihui Desktop", lang: "zh-CN", localService: true };
const settle = async () => { await Promise.resolve(); await Promise.resolve(); };

function fixture(callback = async () => "先看函数在该点附近的变化。") {
  let time = 0;
  let timerId = 0;
  const timers = new Map();
  const microphones = [];
  const spoken = [];
  const states = [];
  const notices = [];
  const requests = [];
  let wakeCount = 0;
  const document = new EventTarget();
  document.hidden = false;
  const env = Object.assign(new EventTarget(), {
    isSecureContext: true,
    navigator: { userAgent: "Edg/147", onLine: true },
    document,
    performance: { now: () => time },
    setTimeout: (fn, delay) => { const id = ++timerId; timers.set(id, { at: time + delay, fn }); return id; },
    clearTimeout: (id) => timers.delete(id),
    SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } }
  });
  env.SpeechRecognition = class {
    constructor() { this.results = []; this.running = false; microphones.push(this); }
    start() { this.running = true; this.onstart?.(); }
    abort() { this.running = false; }
    end() { this.running = false; this.onend?.(); }
    hear(text, final = true) {
      const result = Object.assign([{ transcript: text }], { isFinal: final });
      if (this.results.at(-1)?.isFinal === false) this.results[this.results.length - 1] = result;
      else this.results.push(result);
      this.onresult?.({ resultIndex: this.results.length - 1, results: this.results });
    }
  };
  const synthesis = Object.assign(new EventTarget(), {
    voices: [natural, local],
    current: null,
    getVoices() { return this.voices; },
    speak(utterance) { this.current = utterance; spoken.push(utterance); utterance.onstart?.(); },
    cancel() { this.current = null; },
    finish() { const current = this.current; this.current = null; current?.onend?.(); },
    error(error) { this.current?.onerror?.({ error }); }
  });
  env.speechSynthesis = synthesis;
  const session = createVoiceSession({
    environment: env,
    onState: (state) => states.push(state),
    onNotice: (message) => notices.push(message),
    onWake: () => { wakeCount += 1; },
    onUtterance: (message) => { requests.push(message); return callback(message); }
  });
  function advance(ms) {
    const until = time + ms;
    let steps = 0;
    for (;;) {
      const next = [...timers].filter(([, timer]) => timer.at <= until).sort((a, b) => a[1].at - b[1].at)[0];
      if (!next) break;
      assert.ok(++steps < 1000, "timer retry loop");
      time = next[1].at;
      timers.delete(next[0]);
      next[1].fn();
    }
    time = until;
  }
  const mic = () => microphones.at(-1);
  function wake() {
    session.startWake();
    mic().hear("你好小逻");
    assert.equal(session.getMode(), "speaking");
    synthesis.finish();
    assert.equal(session.getMode(), "listening");
  }
  return { env, session, mic, microphones, synthesis, spoken, states, notices, requests, timers,
    advance, wake, wakeCount: () => wakeCount };
}

test("unsupported and iOS browsers do not create audio sessions", () => {
  assert.equal(isVoiceSupported(undefined), false);
  const f = fixture();
  f.env.navigator.userAgent = "iPhone";
  assert.equal(isVoiceSupported(f.env), false);
  assert.equal(f.microphones.length, 0);
  assert.equal(f.spoken.length, 0);
  f.session.dispose();
});

test("only the fixed wake phrase wakes; greeting is spoken and returns to listening", () => {
  const f = fixture();
  f.session.startWake();
  f.mic().hear("小逻");
  f.mic().hear("小逻小逻");
  assert.equal(f.wakeCount(), 0);
  f.mic().hear("你好，小逻。");
  assert.equal(f.wakeCount(), 1);
  assert.equal(f.spoken[0].text, "我在，请讲。");
  f.synthesis.finish();
  assert.equal(f.session.getMode(), "listening");
  f.session.dispose();
});

test("wake phrase plus question retains the question and failure returns to continuous listening", async () => {
  const f = fixture(async () => null);
  f.session.startWake();
  f.mic().hear("你好小逻，极限怎么求？");
  await settle();
  assert.deepEqual(f.requests, ["极限怎么求？"]);
  assert.equal(f.session.getMode(), "listening");
  f.session.dispose();
});

test("two voice turns share continuous listening without a second wake phrase", async () => {
  const f = fixture();
  f.wake();
  for (const question of ["极限怎么求", "再讲一个例子"]) {
    f.mic().hear(question);
    f.advance(850);
    assert.equal(f.session.getMode(), "thinking");
    assert.equal(f.mic().running, false);
    await settle();
    assert.equal(f.session.getMode(), "speaking");
    f.synthesis.finish();
    assert.equal(f.session.getMode(), "listening");
  }
  assert.equal(f.wakeCount(), 1);
  assert.deepEqual(f.requests, ["极限怎么求", "再讲一个例子"]);
  f.session.dispose();
});

test("interim results do not send; adjacent final fragments and duplicate events submit once", async () => {
  const f = fixture();
  f.wake();
  f.mic().hear("先说", false);
  f.advance(400);
  assert.equal(f.requests.length, 0);
  f.mic().hear("先说极限");
  f.advance(500);
  f.mic().hear("再举例子");
  f.mic().onresult({ resultIndex: 0, results: f.mic().results });
  f.advance(850);
  await settle();
  assert.deepEqual(f.requests, ["先说极限 再举例子"]);
  f.session.dispose();
});

test("normal recognition end restarts in conversation and does not reset the idle deadline", () => {
  const f = fixture();
  f.wake();
  f.advance(20000);
  const previous = f.mic();
  previous.end();
  f.advance(450);
  assert.notEqual(f.mic(), previous);
  assert.equal(f.session.getMode(), "listening");
  f.advance(9550);
  assert.equal(f.session.getMode(), "wake");
  assert.equal(f.mic().running, true);
  f.session.dispose();
});

test("real user speech renews the 30 second idle window", () => {
  const f = fixture();
  f.wake();
  f.advance(29000);
  f.mic().hear("我还在想", false);
  f.advance(2000);
  assert.equal(f.session.getMode(), "listening");
  f.advance(28000);
  assert.equal(f.session.getMode(), "wake");
  f.session.dispose();
});

test("speaker echo is ignored; a new utterance interrupts and retains its final result", async () => {
  const f = fixture();
  f.wake();
  f.session.speak("先观察函数在零点附近的变化。");
  f.mic().hear("先观察函数在零点附近的变化");
  f.advance(900);
  assert.equal(f.session.getMode(), "speaking");
  assert.equal(f.requests.length, 0);
  const oldEnd = f.synthesis.current.onend;
  const sameMic = f.mic();
  f.mic().hear("换一种方法", false);
  assert.equal(f.session.getMode(), "listening");
  assert.equal(f.synthesis.current, null);
  assert.equal(f.mic(), sameMic);
  f.mic().hear("换一种方法解释");
  f.advance(850);
  oldEnd();
  await settle();
  assert.deepEqual(f.requests, ["换一种方法解释"]);
  f.session.dispose();
});

test("manual interruption resumes listening and late synthesis callbacks cannot queue chunks", () => {
  const f = fixture();
  f.wake();
  f.session.speak("甲".repeat(400));
  const staleEnd = f.synthesis.current.onend;
  const count = f.spoken.length;
  f.session.interrupt();
  staleEnd();
  assert.equal(f.spoken.length, count);
  assert.equal(f.session.getMode(), "listening");
  f.session.dispose();
});

test("natural voice is preferred, while offline and errors retry the same chunk locally", () => {
  const f = fixture();
  assert.equal(pickChineseVoice([local, natural]), natural);
  assert.equal(pickChineseVoice([natural, local], true), local);
  f.wake();
  f.session.speak("请看这个例子。");
  assert.equal(f.spoken.at(-1).voice, natural);
  f.synthesis.error("network");
  assert.equal(f.spoken.at(-1).voice, local);
  assert.equal(f.spoken.at(-1).text, "请看这个例子。");
  assert.match(f.notices.at(-1), /切换本地/);
  f.synthesis.finish();
  f.env.navigator.onLine = false;
  f.session.speak("离线时使用本地音色。");
  assert.equal(f.spoken.at(-1).voice, local);
  f.session.dispose();
});

test("recognition outage during narration still allows local speech, then exposes the error", () => {
  const f = fixture();
  f.wake();
  f.session.speak("离线后仍朗读本地文字。");
  f.mic().onerror({ error: "network" });
  f.synthesis.error("network");
  assert.equal(f.spoken.at(-1).voice, local);
  assert.equal(f.session.getMode(), "speaking");
  f.synthesis.finish();
  assert.equal(f.session.getMode(), "error-network");
  f.advance(2000);
  assert.equal(f.mic().running, false);
  f.session.dispose();
});

test("missing or failed Chinese voices recover with visible notice instead of deadlock", () => {
  const f = fixture();
  f.synthesis.voices = [{ name: "English", lang: "en-US", localService: true }];
  f.session.startWake();
  f.mic().hear("你好小逻");
  assert.equal(f.session.getMode(), "listening");
  assert.match(f.notices.at(-1), /中文音色/);
  f.synthesis.voices = [local];
  f.session.speak("再次尝试。");
  f.synthesis.error("synthesis-failed");
  assert.equal(f.session.getMode(), "listening");
  assert.match(f.notices.at(-1), /朗读暂不可用/);
  f.session.dispose();
});

test("speech denial is visible and does not retry indefinitely", () => {
  const f = fixture();
  f.wake();
  f.session.speak("测试。");
  const count = f.spoken.length;
  f.synthesis.error("not-allowed");
  assert.equal(f.spoken.length, count);
  assert.match(f.notices.at(-1), /自动朗读/);
  assert.equal(f.session.getMode(), "listening");
  f.session.dispose();
});

test("permission, network, device and language errors release microphone without retrying", () => {
  for (const [error, expected] of [
    ["not-allowed", "error-permission"], ["network", "error-network"],
    ["audio-capture", "error-microphone"], ["language-not-supported", "error-language"]
  ]) {
    const f = fixture();
    f.session.startWake();
    f.mic().onerror({ error });
    f.advance(20000);
    assert.equal(f.session.getMode(), expected);
    assert.equal(f.microphones.length, 1);
    assert.equal(f.mic().running, false);
    f.session.dispose();
  }
});

test("stop while waiting for chat invalidates its late reply, even after re-enabling", async () => {
  let resolve;
  const f = fixture(() => new Promise((done) => { resolve = done; }));
  f.wake();
  f.mic().hear("请介绍导数");
  f.advance(850);
  f.session.stop();
  f.session.startWake();
  const count = f.spoken.length;
  resolve("这条旧回复不能开始朗读。");
  await settle();
  assert.equal(f.session.getMode(), "wake");
  assert.equal(f.spoken.length, count);
  f.session.dispose();
});

test("chat errors resume listening with an explanation", async () => {
  const f = fixture(async () => { throw new Error("offline"); });
  f.wake();
  f.mic().hear("讲解函数");
  f.advance(850);
  await settle();
  assert.equal(f.session.getMode(), "listening");
  assert.match(f.notices.at(-1), /回答未完成/);
  f.session.dispose();
});

test("hidden tab releases audio; visibility restores only an enabled wake session", () => {
  const f = fixture();
  f.wake();
  f.env.document.hidden = true;
  f.env.document.dispatchEvent(new Event("visibilitychange"));
  assert.equal(f.session.getMode(), "paused");
  assert.equal(f.mic().running, false);
  f.env.document.hidden = false;
  f.env.document.dispatchEvent(new Event("visibilitychange"));
  assert.equal(f.session.getMode(), "wake");
  f.session.stop();
  f.env.document.dispatchEvent(new Event("visibilitychange"));
  assert.equal(f.session.getMode(), "off");
  f.session.dispose();
});

test("dispose clears restart/restore work and event listeners", () => {
  const f = fixture();
  f.session.startWake();
  f.mic().end();
  f.session.dispose();
  f.advance(60000);
  f.env.document.dispatchEvent(new Event("visibilitychange"));
  assert.equal(f.microphones.length, 1);
  assert.equal(f.timers.size, 0);
  assert.equal(f.session.getMode(), "off");
});

test("insecure LAN HTTP gives a visible error before microphone access", () => {
  const f = fixture();
  f.env.isSecureContext = false;
  f.session.startWake();
  assert.equal(f.session.getMode(), "error-secure");
  assert.equal(f.microphones.length, 0);
  f.session.dispose();
});

test("long Markdown replies produce bounded readable chunks", () => {
  const chunks = speechChunks("## 标题\n**重点**看[说明](https://example.com)\n" + "甲".repeat(1000));
  assert.ok(chunks.every((chunk) => [...chunk].length <= 180));
  assert.equal(chunks.join("").match(/甲/g).length, 1000);
  assert.ok(!chunks.join("").includes("https://"));
});

