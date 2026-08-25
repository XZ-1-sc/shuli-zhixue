<template>
  <button class="assistant-orb" :class="orbStateClass" type="button" :aria-expanded="open" aria-controls="xiaoluo-drawer" @click="openDrawer">
    <span class="assistant-orb-face" aria-hidden="true"><i></i><i></i></span>
    <span>小逻</span>
    <small v-if="unreadCount">{{ unreadCount }}</small>
  </button>
  <button v-if="showNudge && !open" class="assistant-nudge" type="button" @click="openDrawer">
    <span>小逻有话对你说</span><small>{{ notificationSummary.latest?.title }}</small>
  </button>

  <aside id="xiaoluo-drawer" class="assistant-drawer ai-partner-drawer" :class="{ 'is-open': open, 'has-history': historyOpen }" :aria-label="identityLabel">
    <header class="assistant-head">
      <div class="assistant-identity">
        <span class="assistant-mini-face" aria-hidden="true"><i></i><i></i></span>
        <div><p>{{ identityLabel }}</p><h2>小逻 <small>在线</small></h2></div>
      </div>
      <div class="drawer-actions">
        <button class="icon-button" type="button" :class="{ active: historyOpen }" @click="toggleHistory">历史</button>
        <button class="icon-button" type="button" aria-label="关闭小逻" @click="open = false">关闭</button>
      </div>
    </header>

    <section v-if="historyOpen" class="history-box">
      <header><strong>对话历史</strong><small>按最近时间排列</small></header>
      <button v-for="session in sessions" :key="session.session_id" type="button" @click="loadSession(session.session_id)"><span>{{ formatTime(session.last_message_at) }}</span><small>{{ session.message_count }} 条消息</small></button>
      <p v-if="!sessions.length" class="muted">暂无历史对话。</p>
    </section>

    <div ref="messageList" class="message-list" aria-live="polite">
      <div v-for="message in messages" :key="message.id" class="message-row" :class="message.role">
        <AICard v-if="message.type === 'card'" :card="message.card" @action="runAction" />
        <div v-else-if="message.type === 'action'" class="assistant-action-row"><button type="button" @click="runAction(message.action)">{{ message.action.label }}</button></div>
        <div v-else class="message-bubble" :class="{ thinking: message.thinking }">
          <span v-if="message.thinking" class="thinking-dot" aria-hidden="true"></span>
          <LightMarkdown v-if="message.content && message.role === 'assistant'" :text="message.content" />
          <span v-else>{{ message.content || message.thinkingText || "正在整理思路…" }}</span>
        </div>
      </div>
    </div>

    <details v-if="isStudent" class="negotiation-panel" @toggle="handleTimelineToggle">
      <summary>小逻是怎么分析的 <span v-if="negotiation.available">{{ negotiation.rounds }} 轮协商</span></summary>
      <p v-if="timelineLoading">正在读取最近一次分析过程…</p>
      <p v-else-if="!negotiation.available">{{ negotiation.message || "完成首测后即可查看。" }}</p>
      <template v-else>
        <div class="negotiation-meta"><span>置信度 {{ confidenceLabel }}</span><span>耗时 {{ durationLabel }}</span></div>
        <ol><li v-for="(item, index) in negotiation.items" :key="`${item.round}-${item.message_type}-${index}`"><i></i><div><small>第 {{ item.round }} 轮 · {{ speakerLabel(item.speaker) }}</small><strong>{{ messageTypeLabel(item.message_type) }}</strong><p>{{ timelineSummary(item) }}</p></div></li></ol>
      </template>
    </details>

    <div class="quick-row ai-capability-menu">
      <button v-for="item in visibleQuickActions" :key="item.label" type="button" @click="runQuick(item)">{{ item.icon }} {{ item.label }}</button>
    </div>

    <form class="chat-form" @submit.prevent="send">
      <label class="sr-only" for="xiaoluo-input">向小逻提问</label>
      <input id="xiaoluo-input" v-model="draft" :disabled="sending" :placeholder="isTeacher ? '问小逻：帮我解读这个班的学情' : '问小逻：这道题为什么错？'" />
      <button class="primary-button" :disabled="sending || !draft.trim()" type="submit">发送</button>
    </form>
  </aside>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { apiGet, apiPost, streamChat } from "../api/client";
import { useUserStore } from "../stores/user";
import AICard from "./ui/AICard.vue";
import LightMarkdown from "./ui/LightMarkdown.vue";

const props = defineProps({
  role: { type: String, default: "student" },
  notificationSummary: { type: Object, default: () => ({ unread_count: 0, latest: null, activity: {}, preference: { notify_xiaoluo: true } }) }
});
const user = useUserStore();
const router = useRouter();
const route = useRoute();
const open = ref(false);
const unread = ref(0);
const historyOpen = ref(false);
const sending = ref(false);
const draft = ref("");
const sessions = ref([]);
const messageList = ref(null);
const pendingContext = ref(null);
const hasRecords = ref(null);
const timelineLoading = ref(false);
const negotiation = ref({ available: false, items: [] });
const isTeacher = computed(() => props.role === "teacher");
const isStudent = computed(() => !isTeacher.value);
const identityLabel = computed(() => (isTeacher.value ? "AI 教学助手" : "AI 学习伙伴"));
const unreadCount = computed(() => Math.max(unread.value, Number(props.notificationSummary?.unread_count || 0)));
const showNudge = computed(() => Boolean(props.notificationSummary?.should_nudge && props.notificationSummary?.latest));
const orbStateClass = computed(() => ({
  "has-ai-unread": unreadCount.value > 0,
  "is-learned": Boolean(props.notificationSummary?.activity?.today_learned),
  "is-inactive": Number(props.notificationSummary?.activity?.days_inactive || 0) >= 3,
  "is-quiet": Boolean(props.notificationSummary?.quiet_hours)
}));
const messages = ref([
  { id: "hello", role: "assistant", type: "text", content: isTeacher.value ? "你好，我是教师端小逻。我可以协助解读学情、起草批改评语和规划组卷；所有结果都需要你确认后才会使用。" : "你好，我是小逻。做题后我会主动生成复盘卡，也可以结合当前题目、错题和学习计划给出建议。" }
]);

const studentQuickActions = [
  { label: "今日怎么学", icon: "◎", prompt: "根据我的最近记录，今天应该先学哪一块？", context: { type: "plan" } },
  { label: "分析错因", icon: "◇", prompt: "分析我最近错题的共同原因，并给出改进方法", context: { type: "diagnosis" } },
  { label: "回炉练习", icon: "↻", prompt: "按我的薄弱点安排一组回炉练习", context: { type: "diagnosis" } },
  { label: "考前冲刺", icon: "↗", prompt: "根据我的目标和薄弱点生成一份 7 天冲刺安排", context: { type: "plan" } },
  { label: "讲一道题", icon: "∑", prompt: "请告诉我如何从做题页携带题目来提问" },
  { label: "生成周计划", icon: "▦", prompt: "结合我的目标生成本周学习计划", context: { type: "plan" } }
];
const teacherQuickActions = [
  { label: "解读班级", icon: "◎", prompt: "请根据我名下班级概览指出教学重点和风险。" },
  { label: "关注学生", icon: "◇", prompt: "请告诉我应如何根据正确率、活跃度和待批改量筛选需要关注的学生。" },
  { label: "批改建议", icon: "✓", prompt: "请给我一套鼓励点、问题点、下一步建议清晰的数学评语模板。" },
  { label: "组卷思路", icon: "▦", prompt: "请说明如何按班级薄弱点安排题量和难度梯度。" }
];
const visibleQuickActions = computed(() => {
  if (isTeacher.value) return teacherQuickActions;
  if (hasRecords.value === false) return [{ label: "先做首测", icon: "→", action: { type: "navigate", target: "/practice", query: { mode: "assessment", limit: 12 } } }];
  if (route.path === "/knowledge") return [{ label: "问这个知识点", icon: "∑", prompt: "结合我当前的知识图谱和薄弱点，讲清这个知识点与先修内容的关系。", context: { type: "diagnosis" } }, ...studentQuickActions.slice(1)];
  if (route.path === "/review") return [{ label: "帮我看这批错题", icon: "◇", prompt: "请分析我当前这批错题的共同错因，并给出回炉顺序。", context: { type: "diagnosis" } }, ...studentQuickActions.slice(1)];
  if (route.path === "/roadmap") return [{ label: "调整本周安排", icon: "▦", prompt: "结合最新做题结果调整我的本周安排。", context: { type: "plan" } }, ...studentQuickActions.slice(1)];
  return studentQuickActions;
});
const confidenceLabel = computed(() => (negotiation.value.confidence === null || negotiation.value.confidence === undefined ? "—" : `${Math.round(Number(negotiation.value.confidence) * 100)}%`));
const durationLabel = computed(() => `${(Number(negotiation.value.duration_ms || 0) / 1000).toFixed(1)} 秒`);

function formatTime(value) { return value ? new Date(value).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : "刚刚"; }
async function scrollToLatest() { await nextTick(); if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight; }
async function announceLatest() {
  const latest = props.notificationSummary?.latest;
  if (!latest || messages.value.some((message) => message.notificationId === latest.id)) return;
  messages.value.push({ id: `notice-${latest.id}`, notificationId: latest.id, role: "assistant", type: "text", content: latest.content });
  if (!latest.is_read) {
    await apiPost(`/api/notifications/${latest.id}/read`, {}).catch(() => null);
    window.dispatchEvent(new CustomEvent("xiaoluo:notification-read"));
  }
  await scrollToLatest();
}
async function openDrawer() { open.value = true; unread.value = 0; if (isStudent.value && hasRecords.value === null) loadStudentState(); await announceLatest(); await scrollToLatest(); }
async function loadStudentState() { const data = await apiGet("/api/profile/summary").catch(() => null); if (data) hasRecords.value = Number(data.stats?.practice_count || 0) > 0; }
async function toggleHistory() { historyOpen.value = !historyOpen.value; if (historyOpen.value) await loadSessions(); }
async function loadSessions() { if (!user.userId) return; const data = await apiGet("/api/chat/sessions", { limit: 20 }).catch(() => ({ sessions: [] })); sessions.value = data.sessions || []; }
async function loadSession(sessionId) { const data = await apiGet("/api/chat/history", { session_id: sessionId, limit: 100 }); messages.value = [...(data.messages || [])].reverse().map((item) => ({ ...item, type: "text", id: item.id || `${item.role}-${Math.random()}` })); user.saveSessionId(sessionId); historyOpen.value = false; await scrollToLatest(); }

async function runAction(action) {
  if (!action) return;
  if (action.type === "prompt") { draft.value = action.prompt || action.label; pendingContext.value = action.context || null; await send(); return; }
  if (action.type === "navigate" || action.target) { open.value = false; await router.push({ path: action.target || "/", query: action.query || {} }); }
}
async function runQuick(item) { if (item.action) return runAction(item.action); draft.value = item.prompt; pendingContext.value = item.context || null; await send(); }

async function send() {
  const content = draft.value.trim();
  if (!content || sending.value || !user.userId) return;
  draft.value = "";
  sending.value = true;
  const context = pendingContext.value;
  pendingContext.value = null;
  const assistantMessage = { id: `a-${Date.now()}`, role: "assistant", type: "text", content: "", thinking: true, thinkingText: "正在连接分析管线…" };
  messages.value.push({ id: `u-${Date.now()}`, role: "user", type: "text", content });
  messages.value.push(assistantMessage);
  await scrollToLatest();
  try {
    await streamChat(
      { message: content, session_id: user.sessionId(), context },
      {
        onSession: (sessionId) => user.saveSessionId(sessionId),
        onThinking: (event) => { assistantMessage.thinking = true; assistantMessage.thinkingText = event.text || "正在分析…"; scrollToLatest(); },
        onDelta: (delta) => { assistantMessage.thinking = false; assistantMessage.content += delta; scrollToLatest(); },
        onCard: (card) => { messages.value.push({ id: `card-${Date.now()}-${messages.value.length}`, role: "assistant", type: "card", card }); scrollToLatest(); },
        onAction: (action) => {
          const lastCard = [...messages.value].reverse().find((message) => message.type === "card");
          if (!(lastCard?.card?.actions || []).some((item) => item.label === action.label && item.target === action.target)) messages.value.push({ id: `action-${Date.now()}`, role: "assistant", type: "action", action });
        }
      }
    );
    await loadSessions();
  } catch (error) {
    assistantMessage.thinking = false;
    assistantMessage.content = error.message || "我暂时没能连上分析服务。你的数据已经保存，可以稍后再试。";
  } finally { sending.value = false; await scrollToLatest(); }
}

function assessmentCard(report) {
  return {
    type: "assessment", title: report.plan?.headline || "首测分析已生成", summary: report.summary,
    metrics: [{ label: "正确率", value: `${report.accuracy || 0}%` }, { label: "优先课程", value: report.plan?.focus_course || "待生成" }, { label: "待复核", value: `${report.pending_review_count || 0} 题` }],
    weekly_plan: report.plan?.weekly_plan || [],
    actions: [{ label: "开始第一组练习", type: "navigate", target: report.plan?.next_action?.path || "/practice", query: report.plan?.next_action?.query || { mode: "daily", limit: 8 } }, { label: "查看完整规划", type: "navigate", target: "/roadmap" }]
  };
}
function pushProactiveCard(card, id) { messages.value.push({ id, role: "assistant", type: "card", card }); open.value = true; historyOpen.value = false; unread.value = 0; scrollToLatest(); }
function handleAssessmentComplete(event) { const report = event.detail; if (!report?.task_id) return; if (report.chat_session_id) user.saveSessionId(report.chat_session_id); pushProactiveCard(assessmentCard(report), `assessment-${report.task_id}`); loadSessions(); }
function handlePracticeComplete(event) { const brief = event.detail; if (!brief?.title) return; pushProactiveCard(brief, `review-${Date.now()}`); }
async function handleOpenRequest(event) {
  const detail = event?.detail || {};
  await openDrawer();
  if (detail.card) pushProactiveCard(detail.card, `external-card-${Date.now()}`);
  if (detail.context) pendingContext.value = detail.context;
  if (detail.prompt) { draft.value = detail.prompt; if (detail.autoSend !== false) { await nextTick(); await send(); } }
}
async function handleTimelineToggle(event) { if (!event.currentTarget.open || timelineLoading.value || negotiation.value.available) return; timelineLoading.value = true; try { negotiation.value = await apiGet("/api/negotiation/recent"); } finally { timelineLoading.value = false; } }
function speakerLabel(value) { return ({ diagnostician: "诊断智能体", strategist: "策略智能体" })[value] || "学习智能体"; }
function messageTypeLabel(value) { return ({ diagnosis: "形成诊断", clarity_review: "检查诊断完整性", rediagnosis: "补充诊断", final_strategy: "制定学习策略" })[value] || value; }
function timelineSummary(item) { const value = item.content || {}; if (value.feedback) return value.feedback; if (value.focus_course) return `重点课程：${value.focus_course}；重点知识：${value.focus_knowledge || "待确认"}`; if (Array.isArray(value.weak_points)) return value.weak_points.length ? `识别 ${value.weak_points.length} 个优先薄弱点` : "当前记录不足，建议先完成首测"; return item.needs_rediagnosis ? "信息仍不完整，进入下一轮诊断" : "结构检查通过"; }

onMounted(() => { loadSessions(); if (isStudent.value) loadStudentState(); window.addEventListener("xiaoluo:assessment-complete", handleAssessmentComplete); window.addEventListener("xiaoluo:practice-complete", handlePracticeComplete); window.addEventListener("xiaoluo:open", handleOpenRequest); });
onUnmounted(() => { window.removeEventListener("xiaoluo:assessment-complete", handleAssessmentComplete); window.removeEventListener("xiaoluo:practice-complete", handlePracticeComplete); window.removeEventListener("xiaoluo:open", handleOpenRequest); });
watch(
  () => props.notificationSummary?.latest?.id,
  (notificationId) => {
    if (!notificationId || !props.notificationSummary?.should_nudge) return;
    if (route.path === "/" && props.notificationSummary.latest?.type === "daily_greeting") {
      window.setTimeout(() => { openDrawer(); }, 900);
    }
  }
);
</script>

<style scoped>
.ai-partner-drawer { grid-template-rows:auto minmax(0,1fr) auto auto auto; }
.ai-partner-drawer.has-history { grid-template-rows:auto auto minmax(0,1fr) auto auto auto; }
.thinking-dot { width:7px; height:7px; display:inline-block; margin-right:8px; border-radius:50%; background:#2e7d8c; box-shadow:0 0 0 0 rgba(46, 125, 140, 0.5); animation:ai-pulse 1.15s infinite; }
.assistant-action-row button { min-height:36px; padding:0 13px; border:1px solid rgba(46, 125, 140, 0.32); border-radius:10px; color:#33302b; background:rgba(46, 125, 140, 0.08); font-weight:800; }
.negotiation-panel { margin:0 18px 10px; padding:10px 12px; border:1px solid rgba(46, 125, 140, 0.14); border-radius:11px; color:#706b62; background:rgba(255,255,255,.025); font-size:11px; }
.negotiation-panel summary { cursor:pointer; color:#33302b; font-weight:800; }
.negotiation-panel summary span { float:right; color:#287381; }
.negotiation-panel > p { margin:9px 0 0; line-height:1.55; }
.negotiation-meta { display:flex; gap:12px; margin:9px 0; color:#287381; }
.negotiation-panel ol { display:grid; gap:8px; margin:0; padding:0; list-style:none; }
.negotiation-panel li { position:relative; display:grid; grid-template-columns:10px 1fr; gap:8px; }
.negotiation-panel li i { width:7px; height:7px; margin-top:5px; border-radius:50%; background:#2e7d8c; box-shadow:0 0 0 3px rgba(46, 125, 140, 0.1); }
.negotiation-panel li div { padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,.05); }
.negotiation-panel li small,.negotiation-panel li strong { display:block; }
.negotiation-panel li strong { margin:2px 0; color:#33302b; }
.negotiation-panel li p { margin:0; line-height:1.45; }
.ai-capability-menu { max-height:78px; overflow:auto; }
.assistant-nudge{position:fixed;right:84px;bottom:34px;z-index:58;max-width:220px;display:grid;gap:2px;padding:10px 13px;border:1px solid rgba(46, 125, 140, 0.3);border-radius:12px;color:#33302b;background: rgba(255, 255, 255, 0.94);box-shadow:0 14px 34px rgba(90, 75, 50, 0.14);text-align:left;animation:nudge-in .28s ease-out}.assistant-nudge span{font-weight:850}.assistant-nudge small{color:#287381;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.assistant-orb.has-ai-unread{box-shadow:0 0 0 5px rgba(46, 125, 140, 0.1),0 0 28px rgba(46, 125, 140, 0.38)}.assistant-orb.is-learned:not(.has-ai-unread){animation:orb-learned 2.6s ease-in-out infinite}.assistant-orb.is-inactive:not(.has-ai-unread){border-color:#8f5f0e;color:#8f5f0e;box-shadow:0 0 22px rgba(176, 125, 30, 0.22)}.assistant-orb.is-quiet{opacity:.66;animation:none}.assistant-orb:focus-visible,.assistant-nudge:focus-visible{outline:2px solid #2e7d8c;outline-offset:3px}
@keyframes ai-pulse { 0%{box-shadow:0 0 0 0 rgba(46, 125, 140, 0.45)} 70%{box-shadow:0 0 0 7px rgba(100,215,232,0)} 100%{box-shadow:0 0 0 0 rgba(100,215,232,0)} }
@keyframes orb-learned{0%,100%{box-shadow:0 0 0 0 rgba(63, 143, 102, 0.1)}50%{box-shadow:0 0 0 7px rgba(63, 143, 102, 0.12),0 0 24px rgba(63, 143, 102, 0.22)}}@keyframes nudge-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@media (max-width:520px) { .ai-partner-drawer { right:8px; width:calc(100vw - 16px); height:calc(100dvh - 82px); } .negotiation-panel { margin-right:12px; margin-left:12px; } .assistant-nudge{right:72px;bottom:82px;max-width:190px} }
@media (prefers-reduced-motion:reduce){.assistant-orb,.assistant-nudge{animation:none!important}}
</style>
