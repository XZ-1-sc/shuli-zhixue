// Test-only API boundary. Never imported by production code; no live writes.
(() => {
  const user = { user_id: 999999, username: "AI弹窗回归测试", role: "teacher" };
  localStorage.setItem("math_brain_current_user", JSON.stringify(user));
  localStorage.setItem("xiaoluo_voice", "0");
  const state = window.__aiTest = { requests: [], queries: [], items: [], mode: "success", hold: false };
  const realFetch = window.fetch.bind(window);
  window.fetch = async (input, options = {}) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (!url.pathname.startsWith("/api/")) return realFetch(input, options);
    const reply = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
    if (url.pathname === "/api/teacher/ai/generate-question") {
      const body = JSON.parse(options.body);
      state.requests.push(body);
      if (state.hold) await new Promise(resolve => { state.release = resolve; });
      if (state.mode === "error") return reply({ detail: "测试：模型服务不可用" }, 503);
      if (state.mode === "zero") return reply({ items: [], created_count: 0, errors: [{ index: 1, reason: "选项不完整" }], notice: "未保存任何草稿" });
      const items = Array.from({ length: body.count }, (_, i) => ({
        id: 1000 + state.items.length + i, ...body, question_text: "浏览器测试题 " + (i + 1) + "：求函数的极限并说明所使用的条件。",
        standard_answer: "1", correct_answer: "A", option_a: "1", option_b: "2", option_c: "3", option_d: "4",
        analysis_text: "使用极限运算法则。", stage: "大一", fine_tag: body.knowledge_tag, type_label: "测试题型",
        key_steps: [], common_errors: [], mistake_tags: [], attachments: [], analysis_attachments: [],
        visibility: "class", publish_status: "draft", editable: true, ai_generated: true, source_name: "教师自建题库"
      }));
      state.items.push(...items);
      return reply({ items, created_count: items.length, errors: [], notice: "请逐题审核后发布。" });
    }
    if (url.pathname === "/api/teacher/questions") {
      state.queries.push(Object.fromEntries(url.searchParams));
      return reply({ items: state.items, total: state.items.length, summary: { total: state.items.length, mine: state.items.length, drafts: state.items.length, ai_drafts: state.items.length, published: 0 } });
    }
    if (/^\/api\/teacher\/questions\/\d+$/.test(url.pathname)) return reply(state.items.find(item => item.id === Number(url.pathname.split("/").at(-1))) || {});
    const classItem = { id: 1, name: "回归测试班", stage: "大一", course: "高等数学上", student_count: 0, active_today: 0, invite_code: "TEST0001" };
    const data = {
      "/api/auth/me": user,
      "/api/courses": { courses: [{ course_name: "高等数学上", stage_name: "大一" }] },
      "/api/stages": { stages: [{ stage_name: "大一", title: "基础", stage_order: 1 }] },
      "/api/question-types": { counts: [{ course: "高等数学上", knowledge_tag: "函数与极限" }] },
      "/api/notifications/summary": { unread_count: 0, latest: null },
      "/api/chat/sessions": { sessions: [] },
      "/api/teacher/classes": { items: [classItem] },
      "/api/teacher/classes/1": { class: classItem, members: [], student_count: 0, summary: {} },
      "/api/teacher/classes/1/delete-impact": { member_count: 0, assignment_count: 0, record_count: 0, has_data: false, has_published_assignment: false },
    };
    return reply(data[url.pathname] || {});
  };
})();
