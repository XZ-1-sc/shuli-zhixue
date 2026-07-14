(function () {
  const API_BASE_URL =
    window.XINGCE_API_BASE_URL ||
    (["5500", "5173", "3000"].includes(window.location.port)
      ? `${window.location.protocol}//${window.location.hostname}:8000`
      : window.location.origin);
  const MODULES = ["言语", "判断", "资料", "数量", "常识"];
  const DEFAULT_SCORES = [76, 54, 68, 61, 72];
  const USER_STORAGE_KEY = "xingce_current_user";
  const SESSION_STORAGE_PREFIX = "xingce_chat_session_id_";
  const PLAN_STORAGE_PREFIX = "xingce_selected_plan_";

  const FALLBACK_SCORE_GROUPS = [
    {
      province: "国考",
      items: [
        { year: 2025, exam: "中央机关及直属机构", category: "综合管理类", score: 121.4 },
        { year: 2024, exam: "中央机关及直属机构", category: "行政执法类", score: 118.7 },
        { year: 2023, exam: "中央机关及直属机构", category: "地市级", score: 116.2 }
      ]
    },
    {
      province: "北京",
      items: [
        { year: 2025, exam: "北京市考", category: "市级机关", score: 137.5 },
        { year: 2024, exam: "北京市考", category: "区级机关", score: 132.8 },
        { year: 2023, exam: "北京市考", category: "基层岗位", score: 126.6 }
      ]
    },
    {
      province: "广东",
      items: [
        { year: 2025, exam: "广东省考", category: "县级以上机关", score: 74.2 },
        { year: 2024, exam: "广东省考", category: "珠三角岗位", score: 78.6 },
        { year: 2023, exam: "广东省考", category: "乡镇岗位", score: 66.4 }
      ]
    },
    {
      province: "江苏",
      items: [
        { year: 2025, exam: "江苏省考", category: "A类", score: 131.2 },
        { year: 2024, exam: "江苏省考", category: "B类", score: 126.5 },
        { year: 2023, exam: "江苏省考", category: "C类", score: 121.8 }
      ]
    },
    {
      province: "浙江",
      items: [
        { year: 2025, exam: "浙江省考", category: "综合类", score: 132.1 },
        { year: 2024, exam: "浙江省考", category: "基层类", score: 127.4 },
        { year: 2023, exam: "浙江省考", category: "行政执法类", score: 123.6 }
      ]
    }
  ];

  const FALLBACK_PLAN_OPTIONS = [
    {
      exam_type: "国考",
      job_category: "行政执法类",
      plan_name: "国考执法冲刺方案",
      focus: ["资料分析速度", "判断推理稳定性", "申论热点联动"]
    },
    {
      exam_type: "国考",
      job_category: "地市级综合管理",
      plan_name: "地市级稳分方案",
      focus: ["言语主旨题", "逻辑判断", "常识时政"]
    },
    {
      exam_type: "省考",
      job_category: "省直机关",
      plan_name: "省直高分方案",
      focus: ["数量关系取舍", "资料分析满分率", "判断推理难题"]
    },
    {
      exam_type: "省考",
      job_category: "乡镇基层",
      plan_name: "基层岗位提速方案",
      focus: ["常识判断", "言语理解", "资料分析基础题"]
    },
    {
      exam_type: "事业单位",
      job_category: "综合岗",
      plan_name: "事业单位综合备考方案",
      focus: ["公共基础知识", "言语表达", "判断推理基础"]
    }
  ];

  const state = {
    radarChart: null,
    activeChatController: null,
    user: null,
    sessionId: null,
    scoreGroups: [],
    planOptions: [],
    selectedPlan: null,
    activeScoreFilter: "all",
    selectedScoreYear: null,
    questionTypes: [],
    currentPractice: {
      taskId: null,
      mode: "custom",
      module: null,
      knowledgeTag: null,
      questions: [],
      index: 0,
      selectedAnswer: null,
      answered: false,
      startedAt: null
    },
    historyOffset: 0,
    historyLimit: 50,
    historyItems: [],
    drag: null,
    authMode: "login"
  };

  const elements = {
    pageScroll: document.getElementById("pageScroll"),
    radar: document.getElementById("knowledgeRadar"),
    diagnosisSummary: document.getElementById("diagnosisSummary"),
    targetScoreInput: document.getElementById("targetScoreInput"),
    examDateInput: document.getElementById("examDateInput"),
    remainingDaysMetric: document.getElementById("remainingDaysMetric"),
    goalSaveButton: document.getElementById("goalSaveButton"),
    weaknessChip: document.getElementById("weaknessChip"),
    currentPlanChip: document.getElementById("currentPlanChip"),
    taskList: document.getElementById("recommendedTasks"),
    scoreboardList: document.getElementById("scoreboardList"),
    scoreFilters: document.getElementById("scoreFilters"),
    scoreYearSelect: document.getElementById("scoreYearSelect"),
    planOptions: document.getElementById("planOptions"),
    planSaveStatus: document.getElementById("planSaveStatus"),
    xiaoluoLauncher: document.getElementById("xiaoluoLauncher"),
    xiaoluoDrawer: document.getElementById("xiaoluoDrawer"),
    xiaoluoClose: document.getElementById("xiaoluoClose"),
    xiaoluoDragHandle: document.getElementById("xiaoluoDragHandle"),
    chatMessages: document.getElementById("chatMessages"),
    chatInput: document.getElementById("chatInput"),
    chatSendButton: document.getElementById("chatSendButton"),
    historyToggle: document.getElementById("historyToggle"),
    historyPane: document.getElementById("historyPane"),
    chatHistoryList: document.getElementById("chatHistoryList"),
    historyCount: document.getElementById("historyCount"),
    historyLoadMore: document.getElementById("historyLoadMore"),
    authOverlay: document.getElementById("authOverlay"),
    loginForm: document.getElementById("loginForm"),
    authTitle: document.getElementById("authTitle"),
    authCopy: document.getElementById("authCopy"),
    usernameInput: document.getElementById("usernameInput"),
    passwordInput: document.getElementById("passwordInput"),
    passwordConfirmInput: document.getElementById("passwordConfirmInput"),
    loginSubmit: document.getElementById("loginSubmit"),
    authModeToggle: document.getElementById("authModeToggle"),
    loginError: document.getElementById("loginError"),
    loginStatus: document.getElementById("loginStatus"),
    logoutButton: document.getElementById("logoutButton")
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function pickFirstObjectValue(source, keys) {
    if (!source || typeof source !== "object") {
      return undefined;
    }

    for (const key of keys) {
      if (source[key] !== undefined && source[key] !== null) {
        return source[key];
      }
    }

    return undefined;
  }

  function getUserId() {
    return state.user?.user_id || state.user?.id || 1;
  }

  function scrollToElement(element) {
    element?.classList.remove("is-hidden");
    element?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function openPracticePage(options = {}) {
    const params = new URLSearchParams();
    params.set("mode", options.mode || "custom");
    params.set("limit", String(options.limit || (options.mode === "mock" ? 20 : 5)));
    if (options.module) {
      params.set("module", options.module);
    }
    if (options.knowledgeTag) {
      params.set("knowledge_tag", options.knowledgeTag);
    }
    if (state.selectedPlan?.plan_name) {
      params.set("plan", state.selectedPlan.plan_name);
    }
    window.location.href = `./practice.html?${params.toString()}`;
  }

  function openPlanPage(plan = state.selectedPlan) {
    const params = new URLSearchParams();
    if (plan?.plan_name) {
      params.set("plan", plan.plan_name);
    }
    window.location.href = `./plan.html${params.toString() ? `?${params.toString()}` : ""}`;
  }

  function daysUntil(dateText) {
    if (!dateText) {
      return 0;
    }
    const today = new Date();
    const target = new Date(`${dateText}T00:00:00`);
    today.setHours(0, 0, 0, 0);
    if (Number.isNaN(target.getTime())) {
      return 0;
    }
    return Math.max(Math.ceil((target - today) / 86400000), 0);
  }

  function planFocusItems(plan) {
    if (!plan) {
      return ["逻辑判断", "资料分析", "言语理解"];
    }
    if (Array.isArray(plan.focus) && plan.focus.length) {
      return plan.focus;
    }
    const fallback = {
      "国考执法冲刺方案": ["资料分析速度", "判断推理稳定性", "常识时政"],
      "地市级稳分方案": ["言语主旨题", "逻辑判断", "常识时政"],
      "省直高分方案": ["资料分析满分率", "判断推理难题", "数量关系取舍"],
      "基层岗位提速方案": ["常识判断", "言语理解", "资料分析基础题"],
      "事业单位综合备考方案": ["公共基础知识", "言语表达", "判断推理基础"]
    };
    return fallback[plan.plan_name] || ["判断推理", "资料分析", "言语理解"];
  }

  function moduleForFocus(focusText) {
    const text = String(focusText || "");
    if (text.includes("资料")) return "资料分析";
    if (text.includes("言语") || text.includes("主旨")) return "言语理解与表达";
    if (text.includes("数量")) return "数量关系";
    if (text.includes("常识") || text.includes("时政") || text.includes("公共基础")) return "常识判断";
    return "判断推理";
  }

  function tagForFocus(focusText) {
    const text = String(focusText || "");
    if (text.includes("比重")) return "比重计算";
    if (text.includes("速度") && text.includes("资料")) return "综合分析";
    if (text.includes("逻辑")) return "逻辑判断";
    if (text.includes("图形")) return "图形推理";
    if (text.includes("言语") || text.includes("主旨")) return "片段阅读";
    if (text.includes("常识") || text.includes("时政")) return "时政热点";
    if (text.includes("数量")) return "数量计算";
    return text.replace(/速度|稳定性|满分率|难题|基础题|取舍/g, "").trim() || null;
  }

  function countForType(moduleName, tag) {
    const hit = state.questionTypes.find((item) => {
      const moduleMatch = item.module === moduleName || item.module.includes(moduleName) || moduleName.includes(item.module);
      return moduleMatch && item.knowledge_tag === tag;
    });
    return hit?.total || 0;
  }

  function randomSessionId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }

    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
      const random = Math.random() * 16 | 0;
      const value = char === "x" ? random : (random & 0x3 | 0x8);
      return value.toString(16);
    });
  }

  function ensureSessionId() {
    const key = `${SESSION_STORAGE_PREFIX}${getUserId()}`;
    if (!state.sessionId) {
      state.sessionId = localStorage.getItem(key) || randomSessionId();
      localStorage.setItem(key, state.sessionId);
    }
    return state.sessionId;
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, options);

    if (!response.ok) {
      const detail = await response.text().catch(() => "");
      throw new Error(detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  function updateGoalUi(goal) {
    if (elements.targetScoreInput) {
      elements.targetScoreInput.value = goal?.target_score ?? 78;
    }
    if (elements.examDateInput) {
      elements.examDateInput.value = goal?.exam_date || "";
    }
    if (elements.remainingDaysMetric) {
      const remaining = goal?.remaining_days ?? daysUntil(elements.examDateInput?.value);
      elements.remainingDaysMetric.innerHTML = `剩余 <strong>${remaining}</strong> 天`;
    }
  }

  async function loadUserGoal() {
    try {
      const goal = await fetchJson(`${API_BASE_URL}/api/user-goals?user_id=${getUserId()}`);
      updateGoalUi(goal);
    } catch (error) {
      const defaultDate = new Date();
      defaultDate.setDate(defaultDate.getDate() + 42);
      updateGoalUi({
        target_score: 78,
        exam_date: defaultDate.toISOString().slice(0, 10),
        remaining_days: 42
      });
    }
  }

  async function saveUserGoal() {
    const targetScore = Number(elements.targetScoreInput?.value || 78);
    const examDate = elements.examDateInput?.value;
    if (!examDate) {
      if (elements.remainingDaysMetric) {
        elements.remainingDaysMetric.textContent = "请设置考试日期";
      }
      return;
    }

    try {
      const goal = await fetchJson(`${API_BASE_URL}/api/user-goals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: getUserId(),
          target_score: targetScore,
          exam_date: examDate,
          target_exam: state.selectedPlan?.exam_type || "国考"
        })
      });
      updateGoalUi(goal);
    } catch (error) {
      updateGoalUi({
        target_score: targetScore,
        exam_date: examDate,
        remaining_days: daysUntil(examDate)
      });
    }
  }

  function normalizeDiagnosisText(data) {
    if (typeof data === "string") {
      return data;
    }

    const text = pickFirstObjectValue(data, [
      "diagnosis",
      "diagnosis_text",
      "result",
      "message",
      "summary"
    ]);

    if (typeof text === "string") {
      return text;
    }

    if (data && typeof data === "object") {
      return JSON.stringify(data, null, 2);
    }

    return "暂无诊断结果。";
  }

  function normalizeScoreValue(value, fallback) {
    const numberValue = Number(value);
    if (!Number.isFinite(numberValue)) {
      return fallback;
    }
    return Math.max(0, Math.min(100, Math.round(numberValue)));
  }

  function scoresFromObject(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return null;
    }

    const aliases = {
      "言语": ["言语", "言语理解", "言语理解与表达"],
      "判断": ["判断", "判断推理"],
      "资料": ["资料", "资料分析"],
      "数量": ["数量", "数量关系"],
      "常识": ["常识", "常识判断"]
    };

    return MODULES.map((moduleName, index) => {
      const matchedKey = aliases[moduleName].find((key) => value[key] !== undefined);
      return normalizeScoreValue(matchedKey ? value[matchedKey] : undefined, DEFAULT_SCORES[index]);
    });
  }

  function scoresFromArray(value) {
    if (!Array.isArray(value)) {
      return null;
    }

    if (value.length >= MODULES.length && value.every((item) => typeof item !== "object")) {
      return MODULES.map((_, index) => normalizeScoreValue(value[index], DEFAULT_SCORES[index]));
    }

    const scoreMap = {};
    value.forEach((item) => {
      if (!item || typeof item !== "object") {
        return;
      }
      const name = pickFirstObjectValue(item, ["module", "name", "label", "dimension"]);
      const score = pickFirstObjectValue(item, ["score", "value", "accuracy", "rate"]);
      if (name !== undefined) {
        scoreMap[String(name)] = score;
      }
    });

    return scoresFromObject(scoreMap);
  }

  function inferScoresFromDiagnosisText(text) {
    const scores = [...DEFAULT_SCORES];
    const weakModuleMap = {
      "言语": ["言语", "逻辑填空", "阅读理解", "片段阅读"],
      "判断": ["判断", "逻辑判断", "图形推理", "定义判断", "类比推理"],
      "资料": ["资料", "比重", "增长率", "平均数"],
      "数量": ["数量", "工程问题", "行程问题", "排列组合", "几何"],
      "常识": ["常识", "法律", "时政", "科技", "历史"]
    };

    MODULES.forEach((moduleName, index) => {
      const hit = weakModuleMap[moduleName].some((keyword) => text.includes(keyword));
      if (hit) {
        scores[index] = Math.min(scores[index], 56);
      }
    });

    return scores;
  }

  function extractRadarScores(data) {
    const radarData = pickFirstObjectValue(data, [
      "radar",
      "radar_scores",
      "scores",
      "module_scores",
      "knowledge_scores"
    ]);

    return (
      scoresFromArray(radarData) ||
      scoresFromObject(radarData) ||
      inferScoresFromDiagnosisText(normalizeDiagnosisText(data))
    );
  }

  function renderRadar(scores) {
    if (!elements.radar || !window.echarts) {
      return;
    }

    if (!state.radarChart) {
      state.radarChart = echarts.init(elements.radar);
      window.addEventListener("resize", () => state.radarChart.resize());
    }

    state.radarChart.setOption({
      color: ["#22d3ee"],
      tooltip: {},
      radar: {
        indicator: MODULES.map((name) => ({ name, max: 100 })),
        splitNumber: 4,
        axisName: {
          color: "#c7efff",
          fontSize: 13
        },
        axisLine: {
          lineStyle: { color: "rgba(199, 239, 255, 0.22)" }
        },
        splitLine: {
          lineStyle: { color: "rgba(199, 239, 255, 0.18)" }
        },
        splitArea: {
          areaStyle: {
            color: ["rgba(34, 211, 238, 0.03)", "rgba(34, 211, 238, 0.07)"]
          }
        }
      },
      series: [
        {
          name: "能力得分",
          type: "radar",
          data: [
            {
              value: scores,
              name: "当前能力",
              areaStyle: { color: "rgba(34, 211, 238, 0.28)" },
              lineStyle: { width: 2 },
              symbolSize: 5
            }
          ]
        }
      ]
    });
  }

  function updateDiagnosisArea(data) {
    const diagnosisText = normalizeDiagnosisText(data);
    const scores = extractRadarScores(data);
    const weakestIndex = scores.indexOf(Math.min(...scores));
    const weakestModule = MODULES[weakestIndex] || "判断";

    renderRadar(scores);

    if (elements.diagnosisSummary) {
      elements.diagnosisSummary.textContent = `${weakestModule}偏弱，建议优先强化。${diagnosisText.slice(0, 44)}`;
    }

    if (elements.weaknessChip) {
      elements.weaknessChip.textContent = `薄弱点：${weakestModule}`;
    }
  }

  function normalizeRecommendations(data) {
    if (Array.isArray(data)) {
      return data;
    }

    const list = pickFirstObjectValue(data, [
      "questions",
      "recommendations",
      "recommended_questions",
      "recommended_tasks",
      "tasks",
      "data",
      "items"
    ]);

    if (Array.isArray(list)) {
      return list;
    }

    const ids = pickFirstObjectValue(data, ["recommended_question_ids", "question_ids"]);
    if (Array.isArray(ids)) {
      return ids.map((id) => ({ id, question_text: `推荐题目 ${id}` }));
    }

    return [];
  }

  function taskTitle(item, index) {
    return pickFirstObjectValue(item, [
      "title",
      "task_name",
      "question_text",
      "knowledge_tag",
      "module"
    ]) || `推荐题目 ${index + 1}`;
  }

  function renderRecommendations(items) {
    if (!elements.taskList) {
      return;
    }

    if (!items.length) {
      elements.taskList.innerHTML = `
        <div class="task-item" role="button" tabindex="0" data-task-title="暂无推荐题目">
          <div class="task-main">
            <div class="task-icon" aria-hidden="true"></div>
            <div>
              <div class="task-name">暂无推荐题目</div>
              <div class="task-meta">请确认后端 /api/recommend 接口是否已启动。</div>
            </div>
          </div>
          <span class="tag">等待</span>
        </div>
      `;
      return;
    }

    elements.taskList.innerHTML = items.slice(0, 10).map((item, index) => {
      const title = taskTitle(item, index);
      const id = pickFirstObjectValue(item, ["id", "question_id", "source_question_no"]);
      const moduleName = pickFirstObjectValue(item, ["module", "所属模块"]) || "行测";
      const tag = pickFirstObjectValue(item, ["knowledge_tag", "知识点标签"]) || "专项";
      const difficulty = pickFirstObjectValue(item, ["difficulty", "难度"]) || "中等";
      const label = index === 0 ? "优先" : "待完成";
      const labelClass = index === 0 ? "tag priority" : "tag";

      return `
        <div class="task-item" role="button" tabindex="0"
          data-question-id="${escapeHtml(id || "")}"
          data-task-title="${escapeHtml(title)}"
          data-module="${escapeHtml(moduleName)}"
          data-knowledge-tag="${escapeHtml(tag)}">
          <div class="task-main">
            <div class="task-icon" aria-hidden="true"></div>
            <div>
              <div class="task-name">${escapeHtml(title)}</div>
              <div class="task-meta">${escapeHtml(moduleName)} · ${escapeHtml(tag)} · 难度 ${escapeHtml(difficulty)}</div>
            </div>
          </div>
          <span class="${labelClass}">${label}</span>
        </div>
      `;
    }).join("");
  }

  function renderScoreboard(groups) {
    if (!elements.scoreboardList) {
      return;
    }

    const visibleGroups = groups.filter((group) => {
      if (state.activeScoreFilter === "all") {
        return true;
      }
      if (state.activeScoreFilter === "国考") {
        return group.province === "国考";
      }
      return group.province !== "国考";
    });

    elements.scoreboardList.innerHTML = visibleGroups.map((group) => `
      <article class="score-group">
        <div class="score-group-title">
          <span>${escapeHtml(group.province)}</span>
          <span>${group.items.length} 条</span>
        </div>
        ${group.items.map((item) => `
          <div class="score-row" role="button" tabindex="0"
            data-score-text="${escapeHtml(`${group.province}${item.year}${item.category}进面分数线${item.score}`)}">
            <span>${escapeHtml(item.year)}</span>
            <span>${escapeHtml(item.exam)}</span>
            <span>${escapeHtml(item.category)}</span>
            <span class="score-value">${escapeHtml(item.score)}</span>
          </div>
        `).join("")}
      </article>
    `).join("");
  }

  function renderScoreYears(years, selectedYear) {
    if (!elements.scoreYearSelect) {
      return;
    }
    elements.scoreYearSelect.innerHTML = years.map((year) => (
      `<option value="${escapeHtml(year)}" ${Number(year) === Number(selectedYear) ? "selected" : ""}>${escapeHtml(year)}年</option>`
    )).join("");
  }

  function renderPlanOptions() {
    if (!elements.planOptions) {
      return;
    }

    elements.planOptions.innerHTML = state.planOptions.map((plan, index) => {
      const isSelected = state.selectedPlan && state.selectedPlan.plan_name === plan.plan_name;
      const focus = Array.isArray(plan.focus) ? plan.focus.join(" / ") : String(plan.focus || "专项训练");

      return `
        <button class="plan-card ${isSelected ? "is-selected" : ""}" type="button" data-plan-index="${index}">
          <span class="plan-type">${escapeHtml(plan.exam_type)} · ${escapeHtml(plan.job_category)}</span>
          <span class="plan-name">${escapeHtml(plan.plan_name)}</span>
          <span class="plan-focus">${escapeHtml(focus)}</span>
          <span class="tag">${isSelected ? "已选择" : "选择方案"}</span>
        </button>
      `;
    }).join("");
  }

  function setPlanStatus(message, isError = false) {
    if (!elements.planSaveStatus) {
      return;
    }
    elements.planSaveStatus.textContent = message;
    elements.planSaveStatus.style.color = isError ? "#ffc9c9" : "#7df4bc";
  }

  function updatePlanChip() {
    if (!elements.currentPlanChip) {
      return;
    }
    elements.currentPlanChip.textContent = state.selectedPlan
      ? `方案：${state.selectedPlan.plan_name}`
      : "方案：未选择";
  }

  function savePlanToLocal(plan) {
    localStorage.setItem(`${PLAN_STORAGE_PREFIX}${getUserId()}`, JSON.stringify(plan));
  }

  function loadPlanFromLocal() {
    try {
      return JSON.parse(localStorage.getItem(`${PLAN_STORAGE_PREFIX}${getUserId()}`));
    } catch (error) {
      return null;
    }
  }

  async function selectPlan(plan) {
    state.selectedPlan = plan;
    savePlanToLocal(plan);
    updatePlanChip();
    renderPlanOptions();
    setPlanStatus("正在保存备考方案...");

    try {
      await fetchJson(`${API_BASE_URL}/api/study-plans/select`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: getUserId(),
          exam_type: plan.exam_type,
          job_category: plan.job_category,
          plan_name: plan.plan_name
        })
      });
      setPlanStatus(`已保存：${plan.plan_name}`);
    } catch (error) {
      setPlanStatus("方案已在本机选择；如需跨设备同步，请确认登录和数据库表已创建。", true);
    }
  }

  function renderPracticeTypeCards(container, focusItems) {
    if (!container) {
      return;
    }
    const items = focusItems?.length ? focusItems : [
      "逻辑判断", "图形推理", "资料分析", "言语理解", "常识判断"
    ];

    container.innerHTML = items.map((item) => {
      const moduleName = moduleForFocus(item);
      const tag = tagForFocus(item);
      const total = tag ? countForType(moduleName, tag) : 0;
      return `
        <button class="practice-type-card" type="button"
          data-module="${escapeHtml(moduleName)}"
          data-knowledge-tag="${escapeHtml(tag || "")}">
          <strong>${escapeHtml(item)}</strong>
          <span>${escapeHtml(moduleName)} · ${tag ? escapeHtml(tag) : "随机"} · 题库 ${total || "若干"} 题</span>
        </button>
      `;
    }).join("");
  }

  function openPlanDetail(plan) {
    if (!plan) {
      return;
    }
    const focus = planFocusItems(plan);
    elements.planDetailView?.classList.remove("is-hidden");
    if (elements.planDetailTitle) {
      elements.planDetailTitle.textContent = plan.plan_name;
    }
    if (elements.planDetailSummary) {
      elements.planDetailSummary.textContent = `${plan.exam_type} · ${plan.job_category}。先按题型做专项，再进入随机混合模拟。`;
    }
    if (elements.planRouteList) {
      elements.planRouteList.innerHTML = focus.map((item, index) => `
        <div class="route-step">
          <span>第 ${index + 1} 优先级：${escapeHtml(item)}</span>
          <button class="nav-link" type="button" data-route-practice="${escapeHtml(item)}">开始</button>
        </div>
      `).join("");
    }
    if (elements.mockPlanText) {
      elements.mockPlanText.textContent = `${plan.plan_name}：先做 20 题混合小卷，完成后根据错题模块更新雷达图和今日任务。`;
    }
    renderPracticeTypeCards(elements.planPracticeTypes, focus);
    scrollToElement(elements.planDetailView);
  }

  function renderPracticeTypes() {
    const focus = state.selectedPlan ? planFocusItems(state.selectedPlan) : [
      "逻辑判断", "资料分析", "逻辑填空", "数量计算", "常识判断"
    ];
    renderPracticeTypeCards(elements.practiceTypeGrid, focus);
  }

  function currentQuestion() {
    return state.currentPractice.questions[state.currentPractice.index] || null;
  }

  function resetQuestionState() {
    state.currentPractice.selectedAnswer = null;
    state.currentPractice.answered = false;
    state.currentPractice.startedAt = Date.now();
    if (elements.questionResult) {
      elements.questionResult.textContent = "";
    }
    if (elements.submitAnswerButton) {
      elements.submitAnswerButton.disabled = false;
    }
  }

  function renderCurrentQuestion() {
    const question = currentQuestion();
    if (!question) {
      if (elements.questionProgress) {
        elements.questionProgress.textContent = "第 0 / 0 题";
      }
      if (elements.questionText) {
        elements.questionText.textContent = "当前没有题目，请重新抽题。";
      }
      if (elements.answerOptions) {
        elements.answerOptions.innerHTML = "";
      }
      return;
    }

    resetQuestionState();
    if (elements.questionProgress) {
      elements.questionProgress.textContent = `第 ${state.currentPractice.index + 1} / ${state.currentPractice.questions.length} 题`;
    }
    if (elements.questionText) {
      elements.questionText.textContent = question.question_text;
    }
    if (elements.answerOptions) {
      const options = [
        ["A", question.option_a],
        ["B", question.option_b],
        ["C", question.option_c],
        ["D", question.option_d]
      ];
      elements.answerOptions.innerHTML = options.map(([label, text]) => `
        <button class="answer-option" type="button" data-answer="${label}">
          <span class="option-label">${label}</span>
          <span>${escapeHtml(text)}</span>
        </button>
      `).join("");
    }
  }

  async function startPractice(options = {}) {
    openPracticePage(options);
    return;
    const moduleName = options.module || null;
    const knowledgeTag = options.knowledgeTag || null;
    const limit = options.limit || 5;
    const mode = options.mode || "custom";
    const params = new URLSearchParams({
      limit: String(limit),
      mode
    });
    if (moduleName) {
      params.set("module", moduleName);
    }
    if (knowledgeTag) {
      params.set("knowledge_tag", knowledgeTag);
    }

    elements.practiceView?.classList.remove("is-hidden");
    if (elements.practiceModeLabel) {
      elements.practiceModeLabel.textContent = mode === "mock" ? "模拟考试" : "随机练习";
    }
    if (elements.practiceTitle) {
      elements.practiceTitle.textContent = knowledgeTag || moduleName || "全模块随机练习";
    }
    if (elements.practiceSubtitle) {
      elements.practiceSubtitle.textContent = "每次进入都会随机抽题，提交后会写入做题记录并更新雷达图。";
    }

    try {
      const data = await fetchJson(`${API_BASE_URL}/api/practice/random?${params.toString()}`);
      state.currentPractice = {
        taskId: data.task_id,
        mode: data.mode || mode,
        module: moduleName,
        knowledgeTag,
        questions: Array.isArray(data.questions) ? data.questions : [],
        index: 0,
        selectedAnswer: null,
        answered: false,
        startedAt: Date.now()
      };
    } catch (error) {
      state.currentPractice.questions = [];
      if (elements.questionText) {
        elements.questionText.textContent = "抽题失败，请确认后端和题库可用。";
      }
    }

    renderPracticeTypes();
    renderCurrentQuestion();
    scrollToElement(elements.practiceView);
  }

  async function startMockExam() {
    openPracticePage({ mode: "mock", limit: 20 });
    return;
    elements.practiceView?.classList.remove("is-hidden");
    if (elements.practiceModeLabel) {
      elements.practiceModeLabel.textContent = "模拟考试";
    }
    if (elements.practiceTitle) {
      elements.practiceTitle.textContent = "全模块随机模拟";
    }
    if (elements.practiceSubtitle) {
      elements.practiceSubtitle.textContent = "模拟考试会随机抽取混合题目，提交后按真实记录刷新雷达图。";
    }
    try {
      const data = await fetchJson(`${API_BASE_URL}/api/mock-exam?limit=20`);
      state.currentPractice = {
        taskId: data.task_id,
        mode: "mock",
        module: null,
        knowledgeTag: null,
        questions: Array.isArray(data.questions) ? data.questions : [],
        index: 0,
        selectedAnswer: null,
        answered: false,
        startedAt: Date.now()
      };
    } catch (error) {
      state.currentPractice.questions = [];
    }
    renderPracticeTypes();
    renderCurrentQuestion();
    scrollToElement(elements.practiceView);
  }

  function chooseAnswer(answer) {
    if (state.currentPractice.answered) {
      return;
    }
    state.currentPractice.selectedAnswer = answer;
    elements.answerOptions?.querySelectorAll(".answer-option").forEach((button) => {
      button.classList.toggle("is-selected", button.dataset.answer === answer);
    });
  }

  async function submitCurrentAnswer() {
    const question = currentQuestion();
    if (!question || !state.currentPractice.selectedAnswer || state.currentPractice.answered) {
      if (elements.questionResult) {
        elements.questionResult.textContent = "请先选择一个选项";
      }
      return;
    }

    const spent = Math.max(Math.round((Date.now() - state.currentPractice.startedAt) / 1000), 1);
    try {
      const result = await fetchJson(`${API_BASE_URL}/api/practice/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: getUserId(),
          task_id: state.currentPractice.taskId,
          question_id: question.id,
          selected_answer: state.currentPractice.selectedAnswer,
          time_spent_seconds: spent,
          practice_mode: state.currentPractice.mode
        })
      });
      state.currentPractice.answered = true;
      elements.answerOptions?.querySelectorAll(".answer-option").forEach((button) => {
        const answer = button.dataset.answer;
        button.classList.toggle("is-correct", answer === result.correct_answer);
        button.classList.toggle("is-wrong", answer === result.selected_answer && !result.is_correct);
      });
      if (elements.questionResult) {
        elements.questionResult.textContent = result.is_correct
          ? "回答正确"
          : `回答错误，正确答案：${result.correct_answer}`;
      }
      if (elements.submitAnswerButton) {
        elements.submitAnswerButton.disabled = true;
      }
      if (result.scores) {
        renderRadar(MODULES.map((name, index) => normalizeScoreValue(result.scores[name], DEFAULT_SCORES[index])));
      }
      await loadDiagnosis();
    } catch (error) {
      if (elements.questionResult) {
        elements.questionResult.textContent = "提交失败，请确认已登录并且数据库表可用。";
      }
    }
  }

  function nextQuestion() {
    if (state.currentPractice.index < state.currentPractice.questions.length - 1) {
      state.currentPractice.index += 1;
      renderCurrentQuestion();
      return;
    }
    if (elements.questionResult) {
      elements.questionResult.textContent = "本组题已完成，可以重新抽题或开始模拟考试。";
    }
  }

  function appendMessage(role, content) {
    if (!elements.chatMessages) {
      return null;
    }

    const row = document.createElement("div");
    row.className = `message-row ${role}`;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.textContent = content || "";

    row.appendChild(bubble);
    elements.chatMessages.appendChild(row);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    return bubble;
  }

  function setMessagesFromHistory(messages) {
    if (!elements.chatMessages) {
      return;
    }

    elements.chatMessages.innerHTML = "";

    if (!messages.length) {
      appendMessage("assistant", "这轮会话还没有历史。你可以直接问我今天怎么练。");
      return;
    }

    messages.forEach((message) => {
      appendMessage(message.role === "user" ? "user" : "assistant", message.content);
    });
  }

  function openXiaoluoDrawer() {
    if (elements.xiaoluoDrawer) {
      elements.xiaoluoDrawer.classList.add("is-open");
    }
    ensureSessionId();
  }

  function closeXiaoluoDrawer() {
    if (!elements.xiaoluoDrawer) {
      return;
    }
    elements.xiaoluoDrawer.classList.remove("is-open", "is-dragging");
    elements.xiaoluoDrawer.style.left = "";
    elements.xiaoluoDrawer.style.top = "";
    elements.xiaoluoDrawer.style.right = "";
    elements.xiaoluoDrawer.style.transform = "";
  }

  function extractStreamText(data) {
    if (!data) {
      return "";
    }

    try {
      const parsed = JSON.parse(data);
      if (parsed.session_id) {
        state.sessionId = parsed.session_id;
        localStorage.setItem(`${SESSION_STORAGE_PREFIX}${getUserId()}`, state.sessionId);
        return "";
      }

      const openAiDelta = parsed.choices?.[0]?.delta?.content;
      const openAiMessage = parsed.choices?.[0]?.message?.content;
      if (openAiDelta || openAiMessage) {
        return openAiDelta || openAiMessage;
      }

      return pickFirstObjectValue(parsed, ["content", "delta", "message", "reply", "text"]) || "";
    } catch (error) {
      return data;
    }
  }

  function consumeSseBlock(block, bubble) {
    const lines = block
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    const dataLines = lines
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trim());

    if (!dataLines.length) {
      const text = extractStreamText(block.trim());
      if (bubble && text) {
        bubble.textContent += text;
      }
      return;
    }

    const data = dataLines.join("\n");
    if (data === "[DONE]") {
      return;
    }

    const text = extractStreamText(data);
    if (bubble && text) {
      bubble.textContent += text;
      elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    }
  }

  async function postChatStream(message, bubble) {
    state.activeChatController = new AbortController();

    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
      },
      body: JSON.stringify({
        user_id: getUserId(),
        session_id: ensureSessionId(),
        message
      }),
      signal: state.activeChatController.signal
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    if (!response.body) {
      bubble.textContent += await response.text();
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const result = await reader.read();
      if (result.done) {
        break;
      }

      buffer += decoder.decode(result.value, { stream: true });
      const blocks = buffer.split(/\n\n|\r\n\r\n/);
      buffer = blocks.pop() || "";

      blocks.forEach((block) => consumeSseBlock(block, bubble));
    }

    if (buffer.trim()) {
      consumeSseBlock(buffer, bubble);
    }
  }

  async function sendChatMessage(customMessage) {
    const message = (customMessage || elements.chatInput?.value || "").trim();
    if (!message) {
      return;
    }

    openXiaoluoDrawer();

    if (state.activeChatController) {
      state.activeChatController.abort();
    }

    if (elements.chatInput) {
      elements.chatInput.value = "";
    }

    if (elements.chatSendButton) {
      elements.chatSendButton.disabled = true;
    }

    appendMessage("user", message);
    const assistantBubble = appendMessage("assistant", "");

    try {
      await postChatStream(message, assistantBubble);
      if (!assistantBubble.textContent.trim()) {
        assistantBubble.textContent = "我建议先做一组判断推理，再复盘错因。";
      }
      await loadChatHistory(true);
    } catch (error) {
      assistantBubble.textContent = "小逻暂时连不上后端，请确认 /api/chat 已启动。";
    } finally {
      if (elements.chatSendButton) {
        elements.chatSendButton.disabled = false;
      }
      state.activeChatController = null;
    }
  }

  function renderHistoryList(items, append = false) {
    if (!elements.chatHistoryList) {
      return;
    }

    if (!append) {
      elements.chatHistoryList.innerHTML = "";
    }

    if (!items.length && !append) {
      elements.chatHistoryList.innerHTML = `
        <div class="history-item">
          <span class="history-time">暂无历史</span>
          执行聊天表脚本后，小逻会自动保存对话。
        </div>
      `;
    } else {
      const html = items.map((item) => `
        <div class="history-item" role="button" tabindex="0" data-session-id="${escapeHtml(item.session_id)}">
          <span class="history-time">${escapeHtml(formatTime(item.created_at))} · ${escapeHtml(item.role === "user" ? "你" : "小逻")}</span>
          ${escapeHtml(item.content).slice(0, 90)}
        </div>
      `).join("");
      elements.chatHistoryList.insertAdjacentHTML("beforeend", html);
    }

    if (elements.historyCount) {
      elements.historyCount.textContent = `${state.historyItems.length} 条`;
    }
  }

  async function loadChatHistory(reset = false) {
    if (reset) {
      state.historyOffset = 0;
      state.historyItems = [];
    }

    try {
      const data = await fetchJson(
        `${API_BASE_URL}/api/chat/history?user_id=${getUserId()}&limit=${state.historyLimit}&offset=${state.historyOffset}`
      );
      const messages = Array.isArray(data.messages) ? data.messages : [];
      state.historyItems = reset ? messages : state.historyItems.concat(messages);
      state.historyOffset += messages.length;
      renderHistoryList(messages, !reset);
    } catch (error) {
      state.historyItems = [];
      renderHistoryList([], false);
    }
  }

  async function loadSessionMessages(sessionId) {
    try {
      const data = await fetchJson(
        `${API_BASE_URL}/api/chat/history?user_id=${getUserId()}&session_id=${encodeURIComponent(sessionId)}&limit=100`
      );
      const messages = Array.isArray(data.messages) ? [...data.messages].reverse() : [];
      state.sessionId = sessionId;
      localStorage.setItem(`${SESSION_STORAGE_PREFIX}${getUserId()}`, sessionId);
      setMessagesFromHistory(messages);
      openXiaoluoDrawer();
    } catch (error) {
      appendMessage("assistant", "这条历史暂时读取失败，请确认数据库连接。");
    }
  }

  function formatTime(value) {
    if (!value) {
      return "刚刚";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }

    return date.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  function loadStoredUser() {
    try {
      state.user = JSON.parse(localStorage.getItem(USER_STORAGE_KEY));
    } catch (error) {
      state.user = null;
    }
  }

  function updateLoginStatus() {
    if (!elements.loginStatus) {
      return;
    }
    elements.loginStatus.textContent = state.user ? `用户 ${state.user.username}` : "未登录";
  }

  function showLoginIfNeeded() {
    updateLoginStatus();
    if (!elements.authOverlay) {
      return;
    }
    updateAuthMode();
    elements.authOverlay.classList.toggle("is-visible", !state.user);
  }

  function updateAuthMode() {
    const isRegister = state.authMode === "register";
    elements.loginForm?.classList.toggle("is-register", isRegister);

    if (elements.authTitle) {
      elements.authTitle.textContent = isRegister ? "注册行测智脑" : "登录行测智脑";
    }

    if (elements.authCopy) {
      elements.authCopy.textContent = isRegister
        ? "创建账号后，小逻会把你的对话历史和备考方案绑定到这个用户。"
        : "登录后，小逻对话历史和备考方案会绑定到你的账号，换设备也能继续。";
    }

    if (elements.loginSubmit) {
      elements.loginSubmit.textContent = isRegister ? "注册并进入" : "登录";
    }

    if (elements.authModeToggle) {
      elements.authModeToggle.textContent = isRegister ? "已有账号？去登录" : "还没有账号？去注册";
    }

    if (elements.passwordInput) {
      elements.passwordInput.autocomplete = isRegister ? "new-password" : "current-password";
    }

    if (elements.passwordConfirmInput) {
      elements.passwordConfirmInput.required = isRegister;
      if (!isRegister) {
        elements.passwordConfirmInput.value = "";
      }
    }

    if (elements.loginError) {
      elements.loginError.textContent = "";
    }
  }

  function toggleAuthMode() {
    state.authMode = state.authMode === "login" ? "register" : "login";
    updateAuthMode();
  }

  function readableApiError(error, fallback) {
    try {
      const parsed = JSON.parse(error.message);
      if (parsed.detail) {
        return parsed.detail;
      }
    } catch (parseError) {
      return error.message || fallback;
    }

    return fallback;
  }

  async function activateUser(data) {
    state.user = {
      user_id: data.user_id,
      username: data.username
    };
    state.sessionId = null;
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(state.user));
    showLoginIfNeeded();
    ensureSessionId();
    await Promise.all([
      loadDiagnosis(),
      loadCurrentPlan(),
      loadUserGoal(),
      loadChatHistory(true)
    ]);
  }

  async function handleAuthSubmit(event) {
    event.preventDefault();

    const username = elements.usernameInput?.value.trim();
    const password = elements.passwordInput?.value || "";
    if (!username || !password) {
      elements.loginError.textContent = "请输入用户名和密码。";
      return;
    }

    if (state.authMode === "register") {
      const passwordConfirm = elements.passwordConfirmInput?.value || "";
      if (password.length < 6) {
        elements.loginError.textContent = "注册密码至少需要 6 位。";
        return;
      }
      if (password !== passwordConfirm) {
        elements.loginError.textContent = "两次输入的密码不一致。";
        return;
      }
    }

    elements.loginSubmit.disabled = true;
    elements.loginError.textContent = "";

    try {
      const endpoint = state.authMode === "register" ? "register" : "login";
      const data = await fetchJson(`${API_BASE_URL}/api/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });

      await activateUser(data);
    } catch (error) {
      const action = state.authMode === "register" ? "注册" : "登录";
      elements.loginError.textContent = readableApiError(
        error,
        `${action}失败，请确认 MySQL、users 表和输入信息。`
      );
    } finally {
      elements.loginSubmit.disabled = false;
    }
  }

  function handleLogout() {
    localStorage.removeItem(USER_STORAGE_KEY);
    state.user = null;
    state.sessionId = null;
    state.selectedPlan = null;
    updatePlanChip();
    renderPlanOptions();
    showLoginIfNeeded();
  }

  async function loadDiagnosis() {
    try {
      const data = await fetchJson(`${API_BASE_URL}/api/diagnose?user_id=${getUserId()}`);
      updateDiagnosisArea(data);
    } catch (error) {
      renderRadar(DEFAULT_SCORES);
      if (elements.diagnosisSummary) {
        elements.diagnosisSummary.textContent = "诊断接口暂未连接，当前展示示例能力图。";
      }
    }
  }

  async function loadRecommendations() {
    try {
      const data = await fetchJson(`${API_BASE_URL}/api/recommend`);
      renderRecommendations(normalizeRecommendations(data));
    } catch (error) {
      renderRecommendations([]);
    }
  }

  async function loadScoreLines(year) {
    try {
      const params = year ? `?year=${encodeURIComponent(year)}` : "";
      const data = await fetchJson(`${API_BASE_URL}/api/score-lines${params}`);
      state.scoreGroups = Array.isArray(data.groups) ? data.groups : FALLBACK_SCORE_GROUPS;
      state.selectedScoreYear = data.selected_year || year || null;
      renderScoreYears(data.available_years || [], state.selectedScoreYear);
    } catch (error) {
      state.scoreGroups = FALLBACK_SCORE_GROUPS;
    }
    renderScoreboard(state.scoreGroups);
  }

  async function loadPlanOptions() {
    try {
      const data = await fetchJson(`${API_BASE_URL}/api/study-plans/options`);
      state.planOptions = Array.isArray(data.options) ? data.options : FALLBACK_PLAN_OPTIONS;
    } catch (error) {
      state.planOptions = FALLBACK_PLAN_OPTIONS;
    }
    renderPlanOptions();
  }

  async function loadQuestionTypes() {
    try {
      const data = await fetchJson(`${API_BASE_URL}/api/question-types`);
      state.questionTypes = Array.isArray(data.counts) ? data.counts : [];
    } catch (error) {
      state.questionTypes = [];
    }
    renderPracticeTypes();
    if (state.selectedPlan) {
      renderPracticeTypeCards(elements.planPracticeTypes, planFocusItems(state.selectedPlan));
    }
  }

  async function loadCurrentPlan() {
    const localPlan = loadPlanFromLocal();
    if (localPlan) {
      state.selectedPlan = localPlan;
      updatePlanChip();
      renderPlanOptions();
    }

    try {
      const data = await fetchJson(`${API_BASE_URL}/api/study-plans/current?user_id=${getUserId()}`);
      if (data.plan) {
        state.selectedPlan = data.plan;
        savePlanToLocal(data.plan);
        updatePlanChip();
        renderPlanOptions();
        setPlanStatus(`已载入：${data.plan.plan_name}`);
      }
    } catch (error) {
      if (!localPlan) {
        setPlanStatus("登录后可跨设备同步备考方案。");
      }
    }
  }

  function bindNavigation() {
    document.querySelectorAll("[data-scroll-target]").forEach((button) => {
      button.addEventListener("click", () => {
        const target = document.getElementById(button.dataset.scrollTarget);
        target?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });

    document.querySelectorAll("[data-open-xiaoluo]").forEach((button) => {
      button.addEventListener("click", openXiaoluoDrawer);
    });

    document.querySelectorAll("[data-open-practice]").forEach((button) => {
      button.addEventListener("click", () => startPractice({ limit: 5, mode: "custom" }));
    });

    document.querySelectorAll("[data-open-mock]").forEach((button) => {
      button.addEventListener("click", startMockExam);
    });
  }

  function bindTaskEvents() {
    if (!elements.taskList) {
      return;
    }

    elements.taskList.addEventListener("click", (event) => {
      const item = event.target.closest(".task-item");
      if (!item) {
        return;
      }
      const moduleName = item.dataset.module || "";
      const tag = item.dataset.knowledgeTag || "";
      startPractice({
        module: moduleName,
        knowledgeTag: tag,
        limit: 5,
        mode: "daily"
      });
    });

    elements.taskList.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      event.preventDefault();
      event.target.click();
    });
  }

  function bindScoreboardEvents() {
    if (elements.scoreFilters) {
      elements.scoreFilters.addEventListener("click", (event) => {
        const button = event.target.closest("[data-score-filter]");
        if (!button) {
          return;
        }
        state.activeScoreFilter = button.dataset.scoreFilter;
        elements.scoreFilters.querySelectorAll(".score-filter").forEach((item) => {
          item.classList.toggle("is-active", item === button);
        });
        renderScoreboard(state.scoreGroups);
      });
    }

    elements.scoreYearSelect?.addEventListener("change", () => {
      loadScoreLines(elements.scoreYearSelect.value);
    });

    if (elements.scoreboardList) {
      elements.scoreboardList.addEventListener("click", (event) => {
        const row = event.target.closest(".score-row");
        if (!row) {
          return;
        }
        openXiaoluoDrawer();
        const text = row.dataset.scoreText || "进面分数线";
        elements.chatInput.value = `帮我分析${text}，我现在应该怎么定目标分？`;
        elements.chatInput.focus();
      });
    }
  }

  function bindPlanEvents() {
    if (!elements.planOptions) {
      return;
    }

    elements.planOptions.addEventListener("click", async (event) => {
      const card = event.target.closest("[data-plan-index]");
      if (!card) {
        return;
      }
      const plan = state.planOptions[Number(card.dataset.planIndex)];
      if (plan) {
        await selectPlan(plan);
        openPlanPage(plan);
      }
    });

    elements.planRouteList?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-route-practice]");
      if (!button) {
        return;
      }
      const focus = button.dataset.routePractice;
      startPractice({
        module: moduleForFocus(focus),
        knowledgeTag: tagForFocus(focus),
        limit: 5,
        mode: "chapter"
      });
    });

    elements.planPracticeTypes?.addEventListener("click", (event) => {
      const card = event.target.closest(".practice-type-card");
      if (!card) {
        return;
      }
      startPractice({
        module: card.dataset.module,
        knowledgeTag: card.dataset.knowledgeTag,
        limit: 5,
        mode: "chapter"
      });
    });
  }

  function bindPracticeEvents() {
    elements.practiceTypeGrid?.addEventListener("click", (event) => {
      const card = event.target.closest(".practice-type-card");
      if (!card) {
        return;
      }
      startPractice({
        module: card.dataset.module,
        knowledgeTag: card.dataset.knowledgeTag,
        limit: 5,
        mode: "custom"
      });
    });

    elements.answerOptions?.addEventListener("click", (event) => {
      const option = event.target.closest(".answer-option");
      if (option?.dataset.answer) {
        chooseAnswer(option.dataset.answer);
      }
    });

    elements.submitAnswerButton?.addEventListener("click", submitCurrentAnswer);
    elements.nextQuestionButton?.addEventListener("click", nextQuestion);
    elements.newPracticeButton?.addEventListener("click", () => {
      if (state.currentPractice.mode === "mock") {
        startMockExam();
        return;
      }
      startPractice({
        module: state.currentPractice.module,
        knowledgeTag: state.currentPractice.knowledgeTag,
        limit: 5,
        mode: state.currentPractice.mode
      });
    });
    elements.startMockExamButton?.addEventListener("click", startMockExam);
  }

  function bindChatEvents() {
    elements.xiaoluoLauncher?.addEventListener("click", openXiaoluoDrawer);
    elements.xiaoluoClose?.addEventListener("click", closeXiaoluoDrawer);

    elements.chatSendButton?.addEventListener("click", () => {
      sendChatMessage();
    });

    elements.chatInput?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        sendChatMessage();
      }
    });

    document.querySelectorAll("[data-quick-chat]").forEach((button) => {
      button.addEventListener("click", () => {
        sendChatMessage(button.dataset.quickChat);
      });
    });

    elements.historyToggle?.addEventListener("click", async () => {
      elements.historyPane?.classList.toggle("is-open");
      if (elements.historyPane?.classList.contains("is-open")) {
        await loadChatHistory(true);
      }
    });

    elements.historyLoadMore?.addEventListener("click", () => loadChatHistory(false));

    elements.chatHistoryList?.addEventListener("click", (event) => {
      const item = event.target.closest("[data-session-id]");
      if (item?.dataset.sessionId) {
        loadSessionMessages(item.dataset.sessionId);
      }
    });
  }

  function bindDrawerDrag() {
    const drawer = elements.xiaoluoDrawer;
    const handle = elements.xiaoluoDragHandle;
    if (!drawer || !handle) {
      return;
    }

    handle.addEventListener("pointerdown", (event) => {
      if (event.target.closest("button")) {
        return;
      }

      const rect = drawer.getBoundingClientRect();
      drawer.classList.add("is-dragging");
      drawer.style.left = `${rect.left}px`;
      drawer.style.top = `${rect.top}px`;
      drawer.style.right = "auto";
      drawer.style.transform = "none";
      state.drag = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        left: rect.left,
        top: rect.top
      };
      handle.setPointerCapture(event.pointerId);
    });

    handle.addEventListener("pointermove", (event) => {
      if (!state.drag || state.drag.pointerId !== event.pointerId) {
        return;
      }

      const nextLeft = state.drag.left + event.clientX - state.drag.startX;
      const nextTop = state.drag.top + event.clientY - state.drag.startY;
      const maxLeft = window.innerWidth - drawer.offsetWidth - 8;
      const maxTop = window.innerHeight - drawer.offsetHeight - 8;
      drawer.style.left = `${Math.max(8, Math.min(maxLeft, nextLeft))}px`;
      drawer.style.top = `${Math.max(8, Math.min(maxTop, nextTop))}px`;
    });

    function endDrag(event) {
      if (!state.drag || state.drag.pointerId !== event.pointerId) {
        return;
      }
      drawer.classList.remove("is-dragging");
      state.drag = null;
      handle.releasePointerCapture(event.pointerId);
    }

    handle.addEventListener("pointerup", endDrag);
    handle.addEventListener("pointercancel", endDrag);
  }

  function bindAuthEvents() {
    elements.loginForm?.addEventListener("submit", handleAuthSubmit);
    elements.authModeToggle?.addEventListener("click", toggleAuthMode);
    elements.logoutButton?.addEventListener("click", handleLogout);
    elements.goalSaveButton?.addEventListener("click", saveUserGoal);
    elements.examDateInput?.addEventListener("change", () => {
      updateGoalUi({
        target_score: Number(elements.targetScoreInput?.value || 78),
        exam_date: elements.examDateInput.value,
        remaining_days: daysUntil(elements.examDateInput.value)
      });
    });
  }

  async function init() {
    loadStoredUser();
    renderRadar(DEFAULT_SCORES);
    bindNavigation();
    bindTaskEvents();
    bindScoreboardEvents();
    bindPlanEvents();
    bindChatEvents();
    bindPracticeEvents();
    bindDrawerDrag();
    bindAuthEvents();
    showLoginIfNeeded();
    ensureSessionId();

    await Promise.all([
      loadDiagnosis(),
      loadRecommendations(),
      loadScoreLines(),
      loadPlanOptions(),
      loadQuestionTypes(),
      loadUserGoal()
    ]);

    await Promise.all([
      loadCurrentPlan(),
      loadChatHistory(true)
    ]);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
