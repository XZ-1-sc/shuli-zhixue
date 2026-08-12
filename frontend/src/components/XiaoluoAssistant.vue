<template>
  <button class="assistant-orb" type="button" :aria-expanded="open" aria-controls="xiaoluo-drawer" @click="openDrawer">
    <span class="assistant-orb-face" aria-hidden="true"><i></i><i></i></span>
    <span>小逻</span>
    <small v-if="unread">{{ unread }}</small>
  </button>

  <aside id="xiaoluo-drawer" class="assistant-drawer" :class="{ 'is-open': open, 'has-history': historyOpen }" aria-label="小逻助教">
    <header class="assistant-head">
      <div class="assistant-identity">
        <span class="assistant-mini-face" aria-hidden="true"><i></i><i></i></span>
        <div>
          <p>数学学习助教</p>
          <h2>小逻 <small>在线</small></h2>
        </div>
      </div>
      <div class="drawer-actions">
        <button class="icon-button" type="button" :class="{ active: historyOpen }" @click="toggleHistory">历史</button>
        <button class="icon-button" type="button" aria-label="关闭小逻" @click="open = false">关闭</button>
      </div>
    </header>

    <section v-if="historyOpen" class="history-box">
      <header><strong>对话历史</strong><small>按最近时间排列</small></header>
      <button v-for="session in sessions" :key="session.session_id" type="button" @click="loadSession(session.session_id)">
        <span>{{ formatTime(session.last_message_at) }}</span>
        <small>{{ session.message_count }} 条消息</small>
      </button>
      <p v-if="!sessions.length" class="muted">暂无历史对话。</p>
    </section>

    <div ref="messageList" class="message-list" aria-live="polite">
      <div v-for="message in messages" :key="message.id" class="message-row" :class="message.role">
        <article v-if="message.type === 'assessment'" class="assessment-brief-card">
          <header>
            <span>首测分析已生成</span>
            <b>{{ message.report.accuracy }}%</b>
          </header>
          <h3>{{ message.report.plan?.headline }}</h3>
          <p>{{ message.report.summary }}</p>
          <dl>
            <div>
              <dt>优先课程</dt>
              <dd>{{ message.report.plan?.focus_course }}</dd>
            </div>
            <div>
              <dt>待复核</dt>
              <dd>{{ message.report.pending_review_count || 0 }} 题</dd>
            </div>
          </dl>
          <ol>
            <li v-for="item in message.report.plan?.weekly_plan?.slice(0, 3)" :key="item.day">
              <span>{{ item.day }}</span>
              <p>{{ item.task }}</p>
              <small>{{ item.minutes }} 分钟</small>
            </li>
          </ol>
          <footer>
            <button type="button" @click="startRecommended(message.report)">开始第一组练习</button>
            <RouterLink to="/roadmap" @click="open = false">查看完整规划</RouterLink>
          </footer>
        </article>
        <div v-else class="message-bubble" :class="{ thinking: sending && !message.content }">
          {{ message.content || "正在整理思路..." }}
        </div>
      </div>
    </div>

    <div class="quick-row">
      <button type="button" @click="sendQuick('根据我的最近记录，今天应该先学哪一块？')">今日怎么学</button>
      <button type="button" @click="sendQuick('分析我最近错题的共同原因，并给出改进方法')">分析错因</button>
      <button type="button" @click="sendQuick('按我的薄弱点安排一组回炉练习')">回炉练习</button>
    </div>

    <form class="chat-form" @submit.prevent="send">
      <label class="sr-only" for="xiaoluo-input">向小逻提问</label>
      <input id="xiaoluo-input" v-model="draft" :disabled="sending" placeholder="问小逻：这道题为什么错？" />
      <button class="primary-button" :disabled="sending || !draft.trim()" type="submit">发送</button>
    </form>
  </aside>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";

import { apiGet, streamChat } from "../api/client";
import { useUserStore } from "../stores/user";

const user = useUserStore();
const router = useRouter();
const open = ref(false);
const unread = ref(0);
const historyOpen = ref(false);
const sending = ref(false);
const draft = ref("");
const sessions = ref([]);
const messageList = ref(null);
const messages = ref([
  {
    id: "hello",
    role: "assistant",
    content: "你好，我是小逻。完成数学基础首测后，我会自动分析你的薄弱点、错因和用时，并生成接下来 7 天的学习计划。"
  }
]);

function formatTime(value) {
  if (!value) return "刚刚";
  return new Date(value).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

async function scrollToLatest() {
  await nextTick();
  if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight;
}

function openDrawer() {
  open.value = true;
  unread.value = 0;
  scrollToLatest();
}

async function toggleHistory() {
  historyOpen.value = !historyOpen.value;
  if (historyOpen.value) await loadSessions();
}

async function loadSessions() {
  if (!user.userId) return;
  const data = await apiGet("/api/chat/sessions", { user_id: user.userId, limit: 20 }).catch(() => ({ sessions: [] }));
  sessions.value = data.sessions || [];
}

async function loadSession(sessionId) {
  if (!user.userId) return;
  const data = await apiGet("/api/chat/history", { user_id: user.userId, session_id: sessionId, limit: 100 });
  messages.value = [...(data.messages || [])].reverse().map((item) => ({ ...item, id: item.id || `${item.role}-${Math.random()}` }));
  user.saveSessionId(sessionId);
  historyOpen.value = false;
  await scrollToLatest();
}

async function sendQuick(text) {
  draft.value = text;
  await send();
}

async function send() {
  const content = draft.value.trim();
  if (!content || sending.value || !user.userId) return;
  draft.value = "";
  sending.value = true;
  const assistantMessage = { id: `a-${Date.now()}`, role: "assistant", content: "" };
  messages.value.push({ id: `u-${Date.now()}`, role: "user", content });
  messages.value.push(assistantMessage);
  await scrollToLatest();
  try {
    await streamChat(
      { user_id: user.userId, message: content, session_id: user.sessionId() },
      {
        onSession: (sessionId) => user.saveSessionId(sessionId),
        onDelta: (delta) => {
          assistantMessage.content += delta;
          scrollToLatest();
        }
      }
    );
    await loadSessions();
  } catch (error) {
    assistantMessage.content = "我暂时没能连上分析服务。你的做题记录已经保存，可以稍后再让我生成建议。";
  } finally {
    sending.value = false;
    await scrollToLatest();
  }
}

function handleAssessmentComplete(event) {
  const report = event.detail;
  if (!report?.task_id) return;
  if (report.chat_session_id) user.saveSessionId(report.chat_session_id);
  messages.value.push({
    id: `assessment-${report.task_id}`,
    role: "assistant",
    type: "assessment",
    report
  });
  open.value = true;
  historyOpen.value = false;
  unread.value = 0;
  scrollToLatest();
  loadSessions();
}

function handleOpenRequest() {
  openDrawer();
}

async function startRecommended(report) {
  const action = report.plan?.next_action;
  open.value = false;
  await router.push({ path: action?.path || "/practice", query: action?.query || { mode: "daily", limit: 8 } });
}

onMounted(() => {
  loadSessions();
  window.addEventListener("xiaoluo:assessment-complete", handleAssessmentComplete);
  window.addEventListener("xiaoluo:open", handleOpenRequest);
});

onUnmounted(() => {
  window.removeEventListener("xiaoluo:assessment-complete", handleAssessmentComplete);
  window.removeEventListener("xiaoluo:open", handleOpenRequest);
});
</script>
