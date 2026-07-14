(function () {
  const API_BASE_URL =
    window.XINGCE_API_BASE_URL ||
    (["5500", "5173", "3000"].includes(window.location.port)
      ? `${window.location.protocol}//${window.location.hostname}:8000`
      : window.location.origin);
  const USER_STORAGE_KEY = "xingce_current_user";
  const PLAN_STORAGE_PREFIX = "xingce_selected_plan_";
  const PLAN_TASK_PREFIX = "xingce_plan_tasks_";

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
    user: null,
    planOptions: FALLBACK_PLAN_OPTIONS,
    plan: null,
    tasks: [],
    completed: {}
  };

  const elements = {
    planKicker: document.getElementById("planKicker"),
    planTitle: document.getElementById("planTitle"),
    planSummary: document.getElementById("planSummary"),
    focusTags: document.getElementById("focusTags"),
    completionMetric: document.getElementById("completionMetric"),
    recordMetric: document.getElementById("recordMetric"),
    taskList: document.getElementById("taskList"),
    completionList: document.getElementById("completionList"),
    scoreGrid: document.getElementById("scoreGrid"),
    mockButton: document.getElementById("mockButton"),
    changePlanButton: document.getElementById("changePlanButton"),
    homeButton: document.getElementById("homeButton"),
    fallbackPicker: document.getElementById("fallbackPicker"),
    planPicker: document.getElementById("planPicker")
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

  function planFocusItems(plan) {
    if (Array.isArray(plan?.focus) && plan.focus.length) {
      return plan.focus;
    }
    const fallback = {
      "国考执法冲刺方案": ["资料分析速度", "判断推理稳定性", "常识时政"],
      "地市级稳分方案": ["言语主旨题", "逻辑判断", "常识时政"],
      "省直高分方案": ["资料分析满分率", "判断推理难题", "数量关系取舍"],
      "基层岗位提速方案": ["常识判断", "言语理解", "资料分析基础题"],
      "事业单位综合备考方案": ["公共基础知识", "言语表达", "判断推理基础"]
    };
    return fallback[plan?.plan_name] || ["判断推理", "资料分析", "言语理解"];
  }

  function moduleForFocus(focusText) {
    const text = String(focusText || "");
    if (text.includes("资料")) return "资料分析";
    if (text.includes("言语") || text.includes("主旨") || text.includes("成语") || text.includes("语句")) return "言语理解与表达";
    if (text.includes("数量") || text.includes("工程") || text.includes("行程")) return "数量关系";
    if (text.includes("常识") || text.includes("时政") || text.includes("公共基础") || text.includes("法律")) return "常识判断";
    return "判断推理";
  }

  function tagForFocus(focusText) {
    const text = String(focusText || "");
    if (text.includes("比重")) return "比重计算";
    if (text.includes("增长")) return "增长率计算";
    if (text.includes("平均")) return "平均数";
    if (text.includes("图形")) return "图形推理";
    if (text.includes("加强") || text.includes("削弱")) return "加强削弱";
    if (text.includes("逻辑")) return "逻辑判断";
    if (text.includes("常识")) return "常识综合";
    if (text.includes("法律")) return "法律常识";
    if (text.includes("数量")) return "数量计算";
    if (text.includes("工程")) return "工程问题";
    if (text.includes("行程")) return "行程问题";
    if (text.includes("言语") || text.includes("主旨")) return "片段阅读";
    if (text.includes("成语")) return "成语辨析";
    if (text.includes("语句")) return "语句排序";
    return text || "综合";
  }

  function taskIdFor(label, index) {
    return `${index}-${String(label).replace(/\s+/g, "")}`;
  }

  function buildTasks(plan) {
    const focus = planFocusItems(plan);
    const tasks = focus.map((item, index) => ({
      id: taskIdFor(item, index),
      title: item,
      description: `完成 ${moduleForFocus(item)} 的 5 题专项训练。`,
      module: moduleForFocus(item),
      knowledgeTag: tagForFocus(item),
      mode: "chapter",
      limit: 5
    }));
    tasks.push({
      id: "mock-20",
      title: "20 题混合模拟",
      description: "完成一组混合小卷，用于检查方案整体吸收情况。",
      module: "",
      knowledgeTag: "",
      mode: "mock",
      limit: 20
    });
    return tasks;
  }

  function planStorageKey() {
    return `${PLAN_STORAGE_PREFIX}${getUserId()}`;
  }

  function taskStorageKey() {
    return `${PLAN_TASK_PREFIX}${getUserId()}_${state.plan?.plan_name || "default"}`;
  }

  function savePlanToLocal(plan) {
    localStorage.setItem(planStorageKey(), JSON.stringify(plan));
  }

  function loadPlanFromLocal() {
    try {
      return JSON.parse(localStorage.getItem(planStorageKey()));
    } catch (error) {
      return null;
    }
  }

  function saveCompleted() {
    localStorage.setItem(taskStorageKey(), JSON.stringify(state.completed));
  }

  function loadCompleted() {
    try {
      state.completed = JSON.parse(localStorage.getItem(taskStorageKey())) || {};
    } catch (error) {
      state.completed = {};
    }
  }

  function findPlanByName(name) {
    if (!name) return null;
    return state.planOptions.find((plan) => plan.plan_name === name) || null;
  }

  function setPlan(plan) {
    state.plan = plan;
    savePlanToLocal(plan);
    state.tasks = buildTasks(plan);
    loadCompleted();
    renderAll();
  }

  function openPractice(task) {
    const params = new URLSearchParams({
      mode: task.mode,
      limit: String(task.limit),
      return_to: "plan",
      plan_task_id: task.id
    });
    params.set("plan", state.plan?.plan_name || "");
    if (task.module) params.set("module", task.module);
    if (task.knowledgeTag) params.set("knowledge_tag", task.knowledgeTag);
    window.location.href = `./practice.html?${params.toString()}`;
  }

  function completionCount() {
    return state.tasks.filter((task) => state.completed[task.id]).length;
  }

  function renderHero() {
    if (!state.plan) {
      elements.planTitle.textContent = "请选择备考方案";
      elements.planSummary.textContent = "从首页进入或在下方选择方案后，这里会生成专属刷题任务。";
      elements.focusTags.innerHTML = "";
      elements.completionMetric.textContent = "0/0";
      return;
    }

    const focus = planFocusItems(state.plan);
    elements.planKicker.textContent = `${state.plan.exam_type} · ${state.plan.job_category}`;
    elements.planTitle.textContent = state.plan.plan_name;
    elements.planSummary.textContent = "先做高优先级专项，再用混合模拟检查全模块稳定性。所有任务完成情况在右侧独立查看。";
    elements.focusTags.innerHTML = focus.map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("");
    elements.completionMetric.textContent = `${completionCount()}/${state.tasks.length}`;
  }

  function renderTasks() {
    if (!state.plan) {
      elements.taskList.innerHTML = `<p class="muted">请先选择一个方案。</p>`;
      return;
    }

    elements.taskList.innerHTML = state.tasks.map((task, index) => {
      const done = Boolean(state.completed[task.id]);
      return `
        <article class="task-card ${done ? "is-done" : ""}">
          <div>
            <div class="task-title">${index + 1}. ${escapeHtml(task.title)}</div>
            <p class="muted">${escapeHtml(task.description)}</p>
            <div class="tag-row">
              <span class="tag">${escapeHtml(task.mode === "mock" ? "模拟考试" : task.module)}</span>
              <span class="tag">${escapeHtml(task.knowledgeTag || "全模块")}</span>
              <span class="tag ${done ? "done" : ""}">${done ? "已完成" : "待完成"}</span>
            </div>
          </div>
          <div class="task-actions">
            <button class="mini-button" type="button" data-start-task="${escapeHtml(task.id)}">开始刷题</button>
            <button class="mini-button" type="button" data-toggle-task="${escapeHtml(task.id)}">${done ? "撤销完成" : "标记完成"}</button>
          </div>
        </article>
      `;
    }).join("");
  }

  function renderCompletion() {
    if (!state.plan) {
      elements.completionList.innerHTML = `<p class="muted">暂无任务。</p>`;
      return;
    }

    elements.completionList.innerHTML = state.tasks.map((task) => {
      const done = Boolean(state.completed[task.id]);
      return `
        <div class="completion-row">
          <div>
            <strong>${escapeHtml(task.title)}</strong>
            <p class="muted">${escapeHtml(task.knowledgeTag || "混合模拟")}</p>
          </div>
          <span class="tag ${done ? "done" : ""}">${done ? "已完成" : "未完成"}</span>
        </div>
      `;
    }).join("");
  }

  function renderPlanPicker() {
    elements.fallbackPicker.hidden = Boolean(state.plan);
    elements.planPicker.innerHTML = state.planOptions.map((plan, index) => `
      <button class="plan-option" type="button" data-plan-index="${index}">
        <span class="tag">${escapeHtml(plan.exam_type)} · ${escapeHtml(plan.job_category)}</span>
        <strong>${escapeHtml(plan.plan_name)}</strong>
        <p class="muted">${escapeHtml(planFocusItems(plan).join(" / "))}</p>
      </button>
    `).join("");
  }

  function renderAll() {
    renderHero();
    renderTasks();
    renderCompletion();
    renderPlanPicker();
  }

  async function loadPlanOptions() {
    try {
      const data = await fetchJson(`${API_BASE_URL}/api/study-plans/options`);
      state.planOptions = Array.isArray(data.options) ? data.options : FALLBACK_PLAN_OPTIONS;
    } catch (error) {
      state.planOptions = FALLBACK_PLAN_OPTIONS;
    }
  }

  async function loadSelectedPlan() {
    const params = new URLSearchParams(window.location.search);
    const urlPlan = findPlanByName(params.get("plan"));
    if (urlPlan) {
      setPlan(urlPlan);
      return;
    }

    const localPlan = loadPlanFromLocal();
    if (localPlan) {
      setPlan(localPlan);
      return;
    }

    try {
      const data = await fetchJson(`${API_BASE_URL}/api/study-plans/current?user_id=${getUserId()}`);
      if (data.plan) {
        setPlan(data.plan);
        return;
      }
    } catch (error) {
      // The picker below is enough when the backend is unavailable.
    }

    renderAll();
  }

  async function savePlan(plan) {
    setPlan(plan);
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
    } catch (error) {
      // Local persistence keeps the page usable without MySQL.
    }
  }

  async function loadDiagnosisSummary() {
    try {
      const data = await fetchJson(`${API_BASE_URL}/api/diagnose?user_id=${getUserId()}`);
      const scores = data.scores || {};
      const modules = ["言语", "判断", "资料", "数量", "常识"];
      elements.recordMetric.textContent = String(data.recent_record_count || 0);
      elements.scoreGrid.innerHTML = modules.map((module) => `
        <div class="score-cell">
          <span>${module}</span>
          <strong>${Number(scores[module] ?? 0)}</strong>
        </div>
      `).join("");
    } catch (error) {
      elements.scoreGrid.innerHTML = `<p class="muted">后端暂不可用，完成情况仍会保存在本机。</p>`;
    }
  }

  function bindEvents() {
    elements.taskList.addEventListener("click", (event) => {
      const startButton = event.target.closest("[data-start-task]");
      const toggleButton = event.target.closest("[data-toggle-task]");

      if (startButton) {
        const task = state.tasks.find((item) => item.id === startButton.dataset.startTask);
        if (task) openPractice(task);
        return;
      }

      if (toggleButton) {
        const taskId = toggleButton.dataset.toggleTask;
        state.completed[taskId] = !state.completed[taskId];
        if (!state.completed[taskId]) delete state.completed[taskId];
        saveCompleted();
        renderAll();
      }
    });

    elements.planPicker.addEventListener("click", async (event) => {
      const card = event.target.closest("[data-plan-index]");
      if (!card) return;
      const plan = state.planOptions[Number(card.dataset.planIndex)];
      if (plan) await savePlan(plan);
    });

    elements.mockButton.addEventListener("click", () => {
      const mockTask = state.tasks.find((task) => task.mode === "mock") || {
        id: "mock-20",
        mode: "mock",
        limit: 20
      };
      openPractice(mockTask);
    });

    elements.changePlanButton.addEventListener("click", () => {
      window.location.href = "./index.html#plans";
    });

    elements.homeButton.addEventListener("click", () => {
      window.location.href = "./index.html";
    });
  }

  async function init() {
    loadUser();
    bindEvents();
    await loadPlanOptions();
    await loadSelectedPlan();
    await loadDiagnosisSummary();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
