/** Browser-only voice I/O. Chat requests still use the existing /api/chat flow. */
const SILENCE_MS = 30000;
const SENTENCE_PAUSE_MS = 850;
const WAKE_WORD = "你好小逻";

function normalize(text) {
  return String(text || "").replace(/[\p{P}\p{S}\s]/gu, "").toLowerCase();
}

export function speechChunks(text) {
  const plain = String(text || "")
    .replace(/\x60{3}[\s\S]*?\x60{3}/g, "代码请查看文字回复。")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/https?:\/\/\S+/g, "链接请查看文字回复")
    .replace(/^[\s]*[>#*-]+\s*/gm, "")
    .replace(/[*\x60#$|]/g, "")
    .trim();
  // Also split a single unpunctuated paragraph: every chunk really is <= 180 chars.
  return (plain.match(/[^。！？!?；;\n]+[。！？!?；;\n]?/g) || [])
    .flatMap((part) => part.match(/.{1,180}/gu) || [])
    .map((part) => part.trim()).filter(Boolean);
}

export function pickChineseVoice(voices, localOnly = false) {
  const chinese = voices.filter((voice) => /^(zh|cmn)(-|_|$)/i.test(voice.lang));
  const local = chinese.filter((voice) => voice.localService === true);
  if (!localOnly) {
    const natural = chinese.find((voice) => /Microsoft.*Xiaoxiao|晓晓/i.test(voice.name))
      || chinese.find((voice) => /Microsoft.*(Natural|Online)|自然/i.test(voice.name));
    if (natural) return natural;
  }
  return local.find((voice) => /Huihui|Yaoyao|慧慧|瑶瑶/i.test(voice.name))
    || local[0] || (!localOnly ? chinese[0] : null) || null;
}

export function isVoiceSupported(env = globalThis.window) {
  const navigator = env?.navigator;
  const ios = /iPhone|iPad|iPod/i.test(navigator?.userAgent || "")
    || (navigator?.platform === "MacIntel" && navigator?.maxTouchPoints > 1);
  return Boolean(!ios && (env?.SpeechRecognition || env?.webkitSpeechRecognition)
    && env?.speechSynthesis && env?.SpeechSynthesisUtterance);
}

export function createVoiceSession(config = {}) {
  const env = config.environment || globalThis.window;
  const supported = isVoiceSupported(env);
  const synthesis = env?.speechSynthesis;
  const timers = new Map();
  const now = () => env?.performance?.now() || 0;
  let enabled = false;
  let disposed = false;
  let mode = "off";
  let recognition = null;
  let activeUtterance = null;
  let turnId = 0;
  let speechId = 0;
  let pendingText = "";
  let echoText = "";
  let echoUntil = 0;
  let failedRestarts = 0;
  let recognitionFailure = null;

  function clearTimer(key) {
    if (timers.has(key)) env.clearTimeout(timers.get(key));
    timers.delete(key);
  }
  function later(key, callback, delay) {
    clearTimer(key);
    timers.set(key, env.setTimeout(() => {
      timers.delete(key);
      if (!disposed) callback();
    }, delay));
  }
  function state(value) {
    mode = value;
    config.onState?.(value);
  }
  function notice(value = "") { config.onNotice?.(value); }
  function shouldListen() { return enabled && !recognitionFailure && ["wake", "listening", "speaking"].includes(mode); }

  function stopMic() {
    clearTimer("restart");
    clearTimer("mic-start");
    const previous = recognition;
    recognition = null;
    if (previous) {
      previous.onstart = previous.onresult = previous.onerror = previous.onend = null;
      previous.onspeechstart = previous.onspeechend = null;
      try { previous.abort(); } catch { /* Already ended. */ }
    }
  }
  function stopSpeech() {
    speechId += 1;
    clearTimer("voices");
    clearTimer("speech-start");
    clearTimer("speech-end");
    if (activeUtterance) {
      activeUtterance.onstart = activeUtterance.onend = activeUtterance.onerror = null;
      activeUtterance = null;
      synthesis.cancel();
    }
    echoUntil = now() + 1500;
  }
  function invalidate() {
    turnId += 1;
    clearTimer("idle");
    clearTimer("sentence");
    pendingText = "";
    stopMic();
    stopSpeech();
  }
  function fail(reason) {
    enabled = false;
    invalidate();
    state(reason);
  }
  function touchActivity() {
    if (mode === "listening") later("idle", startWake, SILENCE_MS);
  }

  function isEcho(text) {
    if (!echoText || (mode !== "speaking" && now() > echoUntil)) return false;
    const clean = normalize(text);
    if (!clean) return true;
    if (echoText.includes(clean)) return true;
    // Recognizers may omit punctuation or mishear a few characters of speaker output.
    if (clean.length < 5) return false;
    let matches = 0;
    for (let i = 0; i < clean.length - 1; i += 1) {
      if (echoText.includes(clean.slice(i, i + 2))) matches += 1;
    }
    return matches / (clean.length - 1) > 0.78;
  }

  function waitForReply() {
    const resume = mode === "wake" ? "wake" : "listening";
    invalidate();
    const ticket = { id: turnId, resume };
    if (enabled) state("thinking");
    return ticket;
  }
  function completeTurn(reply, ticket) {
    // Replies after stop, a new turn, hiding the tab or disposal cannot restart audio.
    if (disposed || !enabled || ticket?.id !== turnId || mode !== "thinking") return;
    if (reply) speak(reply);
    else if (ticket.resume === "wake") startWake();
    else startListening();
  }
  function submit(text) {
    const ticket = waitForReply();
    ticket.resume = "listening";
    try {
      Promise.resolve(config.onUtterance?.(text)).then(
        (reply) => completeTurn(reply, ticket),
        () => {
          if (enabled && ticket.id === turnId) notice("这次回答未完成，请再说一次或使用文字输入。");
          completeTurn(null, ticket);
        }
      );
    } catch {
      completeTurn(null, ticket);
    }
  }
  function queueSentence() {
    if (!pendingText) return;
    later("sentence", () => {
      if (mode === "listening" && pendingText) submit(pendingText.trim());
    }, SENTENCE_PAUSE_MS);
  }
  function hear(text, final) {
    if (!text.trim() || !enabled) return;
    if (mode === "wake") {
      if (!final || !normalize(text).includes(WAKE_WORD)) return;
      // Keep a question spoken in the same breath as the wake phrase.
      const question = text.replace(/^.*?你[\s，,]*好[\s，,]*小[\s，,]*逻[\s，,。.!！?？:：]*/u, "").trim();
      config.onWake?.(question);
      if (question) submit(question);
      else speak("我在，请讲。");
      return;
    }
    if (!["listening", "speaking"].includes(mode) || isEcho(text)) return;
    if (mode === "speaking") {
      if (normalize(text).length < 2) return;
      // Retain this recognizer so its final result is not lost during interruption.
      stopSpeech();
      state("listening");
    }
    touchActivity();
    clearTimer("sentence");
    if (final) {
      const clean = normalize(text);
      if (clean === WAKE_WORD) return;
      if (["停止朗读", "暂停朗读", "停一下", "别说了"].includes(clean)) return;
      pendingText += (pendingText ? " " : "") + text.trim();
      queueSentence();
    }
  }

  function startMic() {
    if (!shouldListen() || recognition || disposed) return;
    const Recognition = env.SpeechRecognition || env.webkitSpeechRecognition;
    const current = new Recognition();
    recognition = current;
    current.lang = "zh-CN";
    current.continuous = true;
    current.interimResults = true;
    current.maxAlternatives = 1;
    const processedFinals = new Set();
    current.onstart = () => {
      if (recognition !== current) return;
      failedRestarts = 0;
      clearTimer("mic-start");
    };
    current.onresult = (event) => {
      if (recognition !== current) return;
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        if (processedFinals.has(i)) continue;
        const result = event.results[i];
        if (result.isFinal) processedFinals.add(i);
        hear(result[0]?.transcript || "", result.isFinal);
        if (recognition !== current) break;
      }
    };
    current.onspeechstart = () => {
      if (recognition !== current || mode !== "listening") return;
      clearTimer("sentence");
      touchActivity();
    };
    current.onspeechend = () => { if (recognition === current) queueSentence(); };
    current.onerror = (event) => {
      if (recognition !== current) return;
      const errors = {
        "not-allowed": "error-permission", "service-not-allowed": "error-permission",
        "network": "error-network", "audio-capture": "error-microphone",
        "language-not-supported": "error-language"
      };
      if (event.error === "network" && mode === "speaking") {
        // Recognition and synthesis are independent: local speech can still finish offline.
        recognitionFailure = "error-network";
        stopMic();
        notice("语音识别连接已断开，朗读结束后请检查网络并重试。");
      } else if (errors[event.error]) fail(errors[event.error]);
      else if (!["no-speech", "aborted"].includes(event.error)) fail("error-recognition");
      else {
        stopMic();
        if (shouldListen()) later("restart", startMic, 450);
      }
    };
    current.onend = () => {
      if (recognition !== current) return;
      recognition = null;
      clearTimer("mic-start");
      if (shouldListen()) later("restart", startMic, 450);
    };
    try {
      later("mic-start", () => {
        if (recognition === current) fail("error-recognition");
      }, 10000);
      current.start();
    } catch (error) {
      stopMic();
      if (error.name === "NotAllowedError" || error.name === "SecurityError") fail("error-permission");
      else if (++failedRestarts >= 3) fail("error-recognition");
      else later("restart", startMic, 600);
    }
  }

  function startWake() {
    if (!supported || disposed) return;
    if (env.isSecureContext === false) { fail("error-secure"); return; }
    enabled = true;
    recognitionFailure = null;
    invalidate();
    notice();
    state(env.document?.hidden ? "paused" : "wake");
    startMic();
  }
  function startListening() {
    if (!enabled || disposed) return;
    if (recognitionFailure) { fail(recognitionFailure); return; }
    clearTimer("sentence");
    pendingText = "";
    stopSpeech();
    state("listening");
    touchActivity();
    startMic();
  }
  function interrupt() {
    if (mode === "speaking" && enabled) startListening();
  }

  function voiceInfo(voice) {
    config.onVoice?.(voice ? { name: voice.name, local: voice.localService === true } : null);
  }
  function refreshVoices() {
    voiceInfo(pickChineseVoice(synthesis?.getVoices() || [], env?.navigator?.onLine === false));
  }
  function speak(text) {
    if (!enabled || disposed) return;
    const chunks = speechChunks(text);
    if (!chunks.length) { startListening(); return; }
    clearTimer("idle");
    stopSpeech();
    state("speaking");
    const id = speechId;
    let index = 0;
    let forceLocal = env.navigator?.onLine === false;
    const alive = () => enabled && !disposed && id === speechId && mode === "speaking";
    const finish = () => {
      if (!alive()) return;
      startListening();
      config.onSpeakEnd?.();
    };
    const play = () => {
      if (!alive()) return;
      if (index >= chunks.length) { finish(); return; }
      const voice = pickChineseVoice(synthesis.getVoices(), forceLocal || env.navigator?.onLine === false);
      voiceInfo(voice);
      if (!voice) {
        notice("未找到可用的中文音色，请在 Windows 安装中文语音；回答仍可查看文字。");
        finish();
        return;
      }
      const utterance = new env.SpeechSynthesisUtterance(chunks[index]);
      activeUtterance = utterance;
      utterance.voice = voice;
      utterance.lang = voice.lang || "zh-CN";
      utterance.rate = 1;
      utterance.pitch = 1;
      echoText = normalize(chunks.slice(Math.max(0, index - 1), index + 1).join(""));
      const valid = () => alive() && activeUtterance === utterance;
      const failure = (event = {}) => {
        if (!valid()) return;
        clearTimer("speech-start");
        clearTimer("speech-end");
        utterance.onstart = utterance.onend = utterance.onerror = null;
        activeUtterance = null;
        synthesis.cancel();
        // Retry the SAME chunk locally, rather than silently dropping failed text.
        if (!forceLocal && !voice.localService && event.error !== "not-allowed"
            && pickChineseVoice(synthesis.getVoices(), true)) {
          forceLocal = true;
          notice("在线音色暂不可用，已切换本地中文音色。");
          play();
        } else {
          notice(event.error === "not-allowed"
            ? "浏览器暂停了自动朗读，请点击麦克风关闭后重新开启；文字回复已保留。"
            : "朗读暂不可用，可查看文字回复或点击麦克风重试。");
          finish();
        }
      };
      utterance.onstart = () => { if (valid()) clearTimer("speech-start"); };
      utterance.onend = () => {
        if (!valid()) return;
        clearTimer("speech-start");
        clearTimer("speech-end");
        activeUtterance = null;
        index += 1;
        play();
      };
      utterance.onerror = failure;
      later("speech-start", failure, 6000);
      later("speech-end", failure, 60000);
      try { synthesis.speak(utterance); } catch { failure(); }
    };
    // Voice lists commonly arrive asynchronously after page load.
    if (synthesis.getVoices().length) play();
    else later("voices", play, 500);
    startMic();
  }

  function stop() {
    enabled = false;
    invalidate();
    for (const key of timers.keys()) clearTimer(key);
    notice();
    state("off");
  }
  function visibilityChanged() {
    if (!enabled) return;
    if (env.document.hidden) { invalidate(); state("paused"); }
    else if (mode === "paused") startWake();
  }
  function dispose() {
    stop();
    disposed = true;
    synthesis?.removeEventListener?.("voiceschanged", refreshVoices);
    env?.document?.removeEventListener("visibilitychange", visibilityChanged);
    env?.removeEventListener("pagehide", stop);
  }
  if (supported) {
    refreshVoices();
    synthesis.addEventListener?.("voiceschanged", refreshVoices);
    env.document?.addEventListener("visibilitychange", visibilityChanged);
    env.addEventListener("pagehide", stop);
  }
  return {
    supported: () => supported, startWake, startListening, stop, dispose, speak,
    interrupt, cancelSpeech: interrupt, waitForReply, completeTurn,
    isSpeaking: () => mode === "speaking", getMode: () => mode
  };
}
