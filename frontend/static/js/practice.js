(function () {
  const API_BASE_URL =
    window.XINGCE_API_BASE_URL ||
    (["5500", "5173", "3000"].includes(window.location.port)
      ? `${window.location.protocol}//${window.location.hostname}:8000`
      : window.location.origin);
  const USER_STORAGE_KEY = "xingce_current_user";
  const PLAN_TASK_PREFIX = "xingce_plan_tasks_";

  const state = {
    user: null,
    taskId: null,
    mode: "custom",
    module: "",
    knowledgeTag: "",
    planName: "",
    planTaskId: "",
    returnTo: "",
    questions: [],
    index: 0,
    selectedAnswer: null,
    answered: false,
    startedAt: Date.now()
  };

  const elements = {
    userLabel: document.getElementById("userLabel"),
    modeLabel: document.getElementById("modeLabel"),
    typeList: document.getElementById("typeList"),
    practiceTitle: document.getElementById("practiceTitle"),
    practiceSubtitle: document.getElementById("practiceSubtitle"),
    questionProgress: document.getElementById("questionProgress"),
    questionMeta: document.getElementById("questionMeta"),
    questionText: document.getElementById("questionText"),
    answerOptions: document.getElementById("answerOptions"),
    subjectiveAnswer: document.getElementById("subjectiveAnswer"),
    feedback: document.getElementById("feedback"),
    submitButton: document.getElementById("submitButton"),
    nextButton: document.getElementById("nextButton"),
    reloadButton: document.getElementById("reloadButton"),
    mockButton: document.getElementById("mockButton"),
    homeButton: document.getElementById("homeButton")
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function loadUser() {
    try {
      state.user = JSON.parse(localStorage.getItem(USER_STORAGE_KEY));
    } catch (error) {
      state.user = null;
    }

    if (elements.userLabel) {
      elements.userLabel.textContent = state.user?.username ? `用户 ${state.user.username}` : "未登录";
    }
  }

  function getUserId() {
    return state.user?.user_id || state.user?.id || 1;
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) {
      const detail = await response.text().catch(() => "");
      throw new Error(detail || `HTTP ${response.status}`);
    }
    return response.json();
  }

  function readParams() {
    const params = new URLSearchParams(window.location.search);
    state.mode = params.get("mode") || "custom";
    state.module = params.get("module") || "";
    state.knowledgeTag = params.get("knowledge_tag") || "";
    state.planName = params.get("plan") || "";
    state.planTaskId = params.get("plan_task_id") || "";
    state.returnTo = params.get("return_to") || "";
    if (state.returnTo === "plan" && elements.homeButton) {
      elements.homeButton.textContent = "返回方案";
    }

    const limit = Number(params.get("limit") || (state.mode === "mock" ? 20 : 5));
    return { limit: Number.isFinite(limit) && limit > 0 ? limit : 5 };
  }

  function modeText(mode) {
    if (mode === "mock") return "模拟考试";
    if (mode === "daily") return "今日必做";
    if (mode === "chapter") return "专项练习";
    return "随机练习";
  }

  function questionTypeText(question) {
    if (!question) return "";
    if (question.question_type === "short_answer") return "简答题";
    if (question.question_type === "analysis") return "材料分析";
    return "选择题";
  }

  async function loadQuestionTypes() {
    if (!elements.typeList) return;

    try {
      const data = await fetchJson(`${API_BASE_URL}/api/question-types`);
      const counts = Array.isArray(data.counts) ? data.counts : [];
      const cards = counts.slice(0, 40).map((item) => `
        <button class="type-card" type="button"
          data-module="${escapeHtml(item.module)}"
          data-knowledge-tag="${escapeHtml(item.knowledge_tag)}">
          <strong>${escapeHtml(item.knowledge_tag)}</strong>
          <span class="muted">${escapeHtml(item.module)} · ${escapeHtml(item.total)} 题</span>
        </button>
      `).join("");

      elements.typeList.innerHTML = `
        <button class="type-card" type="button" data-module="" data-knowledge-tag="">
          <strong>全模块随机</strong>
          <span class="muted">选择题 + 简答题 + 材料分析</span>
        </button>
        ${cards}
      `;
    } catch (error) {
      elements.typeList.innerHTML = `
        <button class="type-card" type="button" data-module="" data-knowledge-tag="">
          <strong>全模块随机</strong>
          <span class="muted">题型加载失败时使用默认随机抽题</span>
        </button>
      `;
    }
  }

  async function loadPractice() {
    const { limit } = readParams();
    const title = state.knowledgeTag || state.module || modeText(state.mode);

    elements.modeLabel.textContent = modeText(state.mode);
    elements.practiceTitle.textContent = title;
    elements.practiceSubtitle.textContent = state.mode === "mock"
      ? "本次为混合模拟考试，题目从题库随机抽取。"
      : "本组题从题库随机抽取，包含选择题、简答题和材料分析题。";

    const params = new URLSearchParams({
      limit: String(limit),
      mode: state.mode
    });
    if (state.module) params.set("module", state.module);
    if (state.knowledgeTag) params.set("knowledge_tag", state.knowledgeTag);

    try {
      const url = state.mode === "mock"
        ? `${API_BASE_URL}/api/mock-exam?limit=${encodeURIComponent(limit)}`
        : `${API_BASE_URL}/api/practice/random?${params.toString()}`;
      const data = await fetchJson(url);
      state.taskId = data.task_id;
      state.mode = data.mode || state.mode;
      state.questions = Array.isArray(data.questions) ? data.questions : [];
      state.index = 0;
      if (data.fallback_used && elements.practiceSubtitle) {
        elements.practiceSubtitle.textContent = "当前筛选题量不足，已自动使用相近题目补足。";
      }
      renderQuestion();
    } catch (error) {
      elements.questionProgress.textContent = "第 0 / 0 题";
      elements.questionMeta.innerHTML = "";
      elements.questionText.textContent = "抽题失败，请确认后端已启动且题库可用。";
      elements.answerOptions.innerHTML = "";
      elements.subjectiveAnswer.hidden = true;
      elements.submitButton.disabled = true;
    }
  }

  function currentQuestion() {
    return state.questions[state.index] || null;
  }

  function renderQuestion() {
    const question = currentQuestion();
    state.selectedAnswer = null;
    state.answered = false;
    state.startedAt = Date.now();
    elements.submitButton.disabled = false;
    elements.feedback.textContent = "提交后会显示正确答案、参考答案或主观题关键词评分。";

    if (!question) {
      elements.questionProgress.textContent = "第 0 / 0 题";
      elements.questionMeta.innerHTML = "";
      elements.questionText.textContent = "没有抽到题目，请重新抽题。";
      elements.answerOptions.innerHTML = "";
      elements.subjectiveAnswer.hidden = true;
      elements.submitButton.disabled = true;
      return;
    }

    elements.questionProgress.textContent = `第 ${state.index + 1} / ${state.questions.length} 题`;
    elements.questionMeta.innerHTML = `
      <span class="pill">${escapeHtml(questionTypeText(question))}</span>
      <span class="pill">${escapeHtml(question.module || "行测")}</span>
      <span class="pill">${escapeHtml(question.knowledge_tag || "综合")}</span>
    `;
    elements.questionText.textContent = question.question_text || "题干缺失";

    if (question.question_type === "choice" || !question.question_type) {
      renderChoiceQuestion(question);
      return;
    }

    renderSubjectiveQuestion();
  }

  function renderChoiceQuestion(question) {
    elements.subjectiveAnswer.hidden = true;
    elements.subjectiveAnswer.value = "";
    const options = [
      ["A", question.option_a],
      ["B", question.option_b],
      ["C", question.option_c],
      ["D", question.option_d]
    ];

    elements.answerOptions.innerHTML = options.map(([label, text]) => `
      <button class="answer-option" type="button" data-answer="${label}">
        <span class="option-label">${label}</span>
        <span>${escapeHtml(text || "选项缺失")}</span>
      </button>
    `).join("");
  }

  function renderSubjectiveQuestion() {
    elements.answerOptions.innerHTML = "";
    elements.subjectiveAnswer.hidden = false;
    elements.subjectiveAnswer.value = "";
    elements.subjectiveAnswer.focus();
  }

  function chooseAnswer(answer) {
    if (state.answered) return;
    state.selectedAnswer = answer;
    elements.answerOptions.querySelectorAll(".answer-option").forEach((button) => {
      button.classList.toggle("is-selected", button.dataset.answer === answer);
    });
  }

  async function submitAnswer() {
    const question = currentQuestion();
    if (!question || state.answered) return;

    const isChoice = question.question_type === "choice" || !question.question_type;
    if (isChoice && !state.selectedAnswer) {
      elements.feedback.textContent = "请先选择一个选项。";
      return;
    }
    if (!isChoice && !elements.subjectiveAnswer.value.trim()) {
      elements.feedback.textContent = "请先填写答案。";
      return;
    }

    const spent = Math.max(Math.round((Date.now() - state.startedAt) / 1000), 1);
    const payload = {
      user_id: getUserId(),
      task_id: state.taskId,
      question_id: question.id,
      time_spent_seconds: spent,
      practice_mode: state.mode === "mock" ? "mock" : state.mode
    };

    if (isChoice) {
      payload.selected_answer = state.selectedAnswer;
    } else {
      payload.answer_text = elements.subjectiveAnswer.value.trim();
    }

    try {
      const result = await fetchJson(`${API_BASE_URL}/api/practice/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      state.answered = true;
      elements.submitButton.disabled = true;
      renderFeedback(result, isChoice);
      if (state.index >= state.questions.length - 1) {
        markPlanTaskComplete();
      }
    } catch (error) {
      elements.feedback.textContent = "提交失败，请确认已经登录、后端已启动，并且数据库表可用。";
    }
  }

  function renderFeedback(result, isChoice) {
    if (isChoice) {
      elements.answerOptions.querySelectorAll(".answer-option").forEach((button) => {
        const answer = button.dataset.answer;
        button.classList.toggle("is-correct", answer === result.correct_answer);
        button.classList.toggle("is-wrong", answer === result.selected_answer && !result.is_correct);
      });
      elements.feedback.textContent = result.is_correct
        ? "回答正确。做题记录已保存，雷达图会根据真实记录更新。"
        : `回答错误。正确答案：${result.correct_answer}`;
      return;
    }

    elements.feedback.textContent = [
      `关键词评分：${result.score} 分`,
      `参考答案：${result.reference_answer}`,
      `参考要点：${(result.reference_points || []).join("、")}`
    ].join("\n");
  }

  function planTaskStorageKey() {
    return `${PLAN_TASK_PREFIX}${getUserId()}_${state.planName || "default"}`;
  }

  function markPlanTaskComplete() {
    if (state.returnTo !== "plan" || !state.planTaskId) {
      return;
    }

    try {
      const stored = JSON.parse(localStorage.getItem(planTaskStorageKey())) || {};
      stored[state.planTaskId] = true;
      localStorage.setItem(planTaskStorageKey(), JSON.stringify(stored));
      elements.feedback.textContent = `${elements.feedback.textContent}\n本组任务已完成，返回方案页后会自动更新进度。`;
    } catch (error) {
      // Practice submission already succeeded; task progress can still be marked manually.
    }
  }

  function nextQuestion() {
    if (state.index < state.questions.length - 1) {
      state.index += 1;
      renderQuestion();
      return;
    }
    elements.feedback.textContent = "本组题已经完成。你可以重新抽题、切换题型，或者开始模拟考试。";
  }

  function openPractice(module, knowledgeTag) {
    const params = new URLSearchParams({
      mode: "custom",
      limit: "5"
    });
    if (module) params.set("module", module);
    if (knowledgeTag) params.set("knowledge_tag", knowledgeTag);
    window.location.href = `./practice.html?${params.toString()}`;
  }

  function bindEvents() {
    elements.answerOptions.addEventListener("click", (event) => {
      const button = event.target.closest(".answer-option");
      if (button?.dataset.answer) chooseAnswer(button.dataset.answer);
    });

    elements.typeList.addEventListener("click", (event) => {
      const card = event.target.closest(".type-card");
      if (!card) return;
      openPractice(card.dataset.module, card.dataset.knowledgeTag);
    });

    elements.submitButton.addEventListener("click", submitAnswer);
    elements.nextButton.addEventListener("click", nextQuestion);
    elements.reloadButton.addEventListener("click", () => window.location.reload());
    elements.mockButton.addEventListener("click", () => {
      window.location.href = "./practice.html?mode=mock&limit=20";
    });
    elements.homeButton.addEventListener("click", () => {
      if (state.returnTo === "plan") {
        const params = new URLSearchParams();
        if (state.planName) {
          params.set("plan", state.planName);
        }
        window.location.href = `./plan.html${params.toString() ? `?${params.toString()}` : ""}`;
        return;
      }
      window.location.href = "./index.html";
    });
  }

  async function init() {
    loadUser();
    bindEvents();
    await Promise.all([loadQuestionTypes(), loadPractice()]);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
