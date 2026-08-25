<template>
  <section class="student-page side-feature-main">
      <section class="feature-hero">
        <div>
          <small>{{ page.kicker }}</small>
          <h1>{{ page.title }}</h1>
          <p>{{ page.description }}</p>
        </div>
        <button v-if="page.primaryAction" class="feature-primary" type="button" @click="page.primaryAction.handler">
          {{ page.primaryAction.label }}
        </button>
      </section>

      <section v-if="authRequired" class="glass-panel feature-empty">
        <strong>需要先登录</strong>
        <p>登录后才能同步你的消息、档案、徽章、笔记和学习目标。</p>
        <button type="button" @click="user.openAuth('login')">去登录 / 注册</button>
      </section>

      <section v-else-if="loading" class="feature-skeleton">
        <span v-for="index in 6" :key="index"></span>
      </section>

      <section v-else-if="error" class="glass-panel feature-empty is-error">
        <strong>加载失败</strong>
        <p>{{ error }}</p>
        <button type="button" @click="loadPage">重新加载</button>
      </section>

      <section v-else-if="mode === 'messages'" class="student-message-center">
        <nav class="message-center-tabs" aria-label="消息分类">
          <div><button type="button" :class="{ active: messageTab === 'notifications' }" @click="switchMessageTab('notifications')">通知</button><button type="button" :class="{ active: messageTab === 'teachers' }" @click="switchMessageTab('teachers')">与老师 <b v-if="teacherUnreadCount">{{ teacherUnreadCount }}</b></button><button type="button" :class="{ active: messageTab === 'peers' }" @click="switchMessageTab('peers')">同学 <b v-if="peerUnreadCount">{{ peerUnreadCount }}</b></button></div>
          <button v-if="messageTab !== 'notifications'" class="start-message-action" type="button" @click="openMessageContacts">发起会话</button>
        </nav>
        <section v-if="messageTab === 'notifications'" class="feature-grid messages-grid">
        <div v-if="!messages.length" class="glass-panel feature-empty feature-grid-empty">
          <strong>暂无消息</strong>
          <p>新账号不会自动生成个人通知。完成首测或保存学习目标后，这里会出现学习提醒。</p>
          <RouterLink to="/practice?mode=daily&limit=12">开始首测</RouterLink>
        </div>
        <article v-for="message in messages" :key="message.id" class="glass-panel message-card" :class="{ unread: !message.is_read }">
          <small>{{ typeLabel(message.type) }} · {{ formatTime(message.created_at) }}</small>
          <h2>{{ message.title }}</h2>
          <p>{{ message.content }}</p>
          <RouterLink v-if="message.action_url" :to="message.action_url">查看详情 ›</RouterLink>
          <button v-if="message.type === 'weekly_report'" class="weekly-digest-trigger" type="button" :disabled="weeklyDigestLoading" @click="loadWeeklyDigest(message.id)">
            {{ weeklyDigestLoading ? "正在浓缩本周记录…" : "生成 AI 一页纸周报" }}
          </button>
          <section v-if="weeklyDigestMessageId === message.id && weeklyDigest" class="weekly-digest-card">
            <header><div><small>AI 一页纸周报</small><strong>{{ weeklyDigest.stats.period }}</strong></div><button type="button" @click="printWeeklyDigest">导出 / 打印</button></header>
            <dl><div><dt>作答</dt><dd>{{ weeklyDigest.stats.attempts }}</dd></div><div><dt>正确率</dt><dd>{{ weeklyDigest.stats.accuracy }}%</dd></div><div><dt>学习分钟</dt><dd>{{ weeklyDigest.stats.study_minutes }}</dd></div></dl>
            <p>{{ weeklyDigest.progress }}</p>
            <div v-if="weeklyDigest.mistakes_top3?.length" class="weekly-digest-mistakes"><b v-for="item in weeklyDigest.mistakes_top3" :key="`${item.reason}-${item.knowledge}`">{{ item.knowledge }} · {{ item.reason }}（{{ item.count }}）</b></div>
            <ol><li v-for="item in weeklyDigest.next_week" :key="item">{{ item }}</li></ol>
          </section>
        </article>
        </section>
        <section v-else class="student-teacher-messages">
          <aside class="glass-panel student-teacher-list">
            <button v-for="conversation in activeConversations" :key="conversation.id" type="button" :class="{ active: selectedConversationId === conversation.id }" @click="selectMessageConversation(conversation.id)"><i>{{ conversation.other.nickname.slice(0, 1) }}</i><span><strong>{{ conversation.other.nickname }}</strong><small>{{ conversation.other.role === 'teacher' ? '教师' : '同学' }} · @{{ conversation.other.username }}</small><p>{{ conversation.latest_message || "还没有消息" }}</p></span><b v-if="conversation.unread_count">{{ conversation.unread_count }}</b></button>
            <div v-if="!activeConversations.length" class="feature-empty"><strong>{{ messageTab === "teachers" ? "暂无教师会话" : "暂无同学会话" }}</strong><p>{{ messageTab === "teachers" ? "加入教师班级后，可在这里与老师沟通。" : "可联系同一教师网络内、包括跨班级的同学。" }}</p><button type="button" @click="openMessageContacts">选择联系人</button></div>
          </aside>
          <article class="glass-panel student-teacher-thread">
            <template v-if="selectedConversation">
              <header><div><small>{{ selectedConversation.relation === "teacher_student" ? "教师沟通" : "同学私聊" }}</small><strong>{{ selectedConversation.other.nickname }}</strong></div></header>
              <div ref="messageThreadEl" class="student-thread-list">
                <button v-if="messageHasMore" class="load-earlier" type="button" :disabled="messageThreadLoading" @click="loadEarlierMessages">{{ messageThreadLoading ? "加载中…" : "加载更早消息" }}</button>
                <div v-if="messageThreadLoading && !conversationMessages.length" class="inline-empty">正在加载会话…</div>
                <div v-else-if="!conversationMessages.length" class="inline-empty">还没有消息，可以从一个具体问题开始。</div>
                <MessageBubble v-for="message in conversationMessages" :key="message.id" :message="message" :current-user-id="user.userId" :other-name="selectedConversation.other.nickname" />
              </div>
              <MessageComposer :busy="messageSending" :question-ref="pendingQuestionRef" :placeholder="messageTab === 'teachers' ? '给老师发送消息' : '给同学发送消息'" @send="sendConversationMessage" @clear-question="clearPendingQuestion" />
            </template>
            <div v-else class="feature-empty"><strong>选择联系人</strong><p>查看历史消息或开始新的沟通。</p><button type="button" @click="openMessageContacts">发起会话</button></div>
          </article>
        </section>
        <ContactPicker :open="messageContactPickerOpen" :groups="visibleContactGroups" :loading="messageContactsLoading" @close="messageContactPickerOpen = false" @select="startMessageConversation" />
      </section>

      <section v-else-if="mode === 'profile'" class="profile-layout">
        <article class="glass-panel profile-card">
          <small>当前账户</small>
          <h2>{{ profile.user?.nickname || user.username }}</h2>
          <p>{{ profile.goal?.target_stage }} · {{ profile.goal?.target_course }}</p>
          <div class="profile-stats">
            <span><b>{{ profile.stats?.practice_count || 0 }}</b>练习题</span>
            <span><b>{{ profile.stats?.accuracy || 0 }}%</b>正确率</span>
            <span><b>{{ profile.stats?.study_hours || 0 }}</b>小时</span>
          </div>
        </article>
        <article class="glass-panel profile-card">
          <small>薄弱课程</small>
          <div class="compact-list">
            <p v-if="!profile.weak_points?.length" class="inline-empty">暂无薄弱课程。完成首测后会按知识点正确率生成。</p>
            <RouterLink
              v-for="weak in profile.weak_points || []"
              :key="`${weak.course}-${weak.knowledge_tag}`"
              :to="`/practice?stage=${weak.stage}&course=${weak.course}&knowledge_tag=${weak.knowledge_tag}&limit=10`"
            >
              <span>{{ weak.fine_tag || weak.knowledge_tag }}</span>
              <b>{{ weak.score }}%</b>
            </RouterLink>
          </div>
        </article>
        <article class="glass-panel profile-card profile-wide ability-map-card">
          <header><div><small>错因基因库</small><h2>知识点 × 题型 × 错因</h2></div><p>{{ abilityMap.advice || "完成练习后生成三维能力画像。" }}</p></header>
          <div class="ability-map-layout">
            <RadarChart :items="abilityRadar" />
            <div class="ability-heat-table">
              <p v-if="!abilityMap.cells?.length" class="inline-empty">暂无可聚合记录。</p>
              <div v-for="cell in (abilityMap.cells || []).slice(0, 16)" :key="`${cell.knowledge}-${cell.type}-${cell.reason}`" :style="{ '--ability': cell.accuracy }">
                <strong>{{ cell.knowledge }}</strong><span>{{ questionTypeLabel(cell.type) }}</span><b>{{ cell.reason }}</b><em>{{ Math.round(cell.accuracy * 100) }}%</em>
              </div>
            </div>
          </div>
        </article>
        <article class="glass-panel profile-card profile-wide">
          <small>最近记录</small>
          <div class="record-table">
            <p v-if="!profile.recent_records?.length" class="inline-empty">暂无做题记录。</p>
            <div v-for="record in profile.recent_records || []" :key="`${record.question_id}-${record.answered_at}`">
              <span>{{ record.course }}</span>
              <span>{{ record.knowledge_tag }}</span>
              <b :class="{ ok: record.is_correct }">{{ record.is_correct ? "正确" : "需复盘" }}</b>
            </div>
          </div>
        </article>
      </section>

      <section v-else-if="mode === 'achievements'" class="achievement-grid">
        <article v-for="badge in achievements" :key="badge.code" class="glass-panel badge-card" :class="{ unlocked: badge.unlocked }">
          <span>{{ badge.unlocked ? "已获得" : "未解锁" }}</span>
          <h2>{{ badge.title }}</h2>
          <p>{{ badge.description }}</p>
          <div class="target-bar"><i :style="{ width: `${badgeProgress(badge)}%` }"></i></div>
          <small>{{ badge.progress }} / {{ badge.target }}</small>
        </article>
      </section>

      <section v-else-if="mode === 'resources'" class="resources-layout">
        <form class="glass-panel resource-filter" @submit.prevent="loadResources">
          <label>
            阶段
            <select v-model="resourceFilter.stage">
              <option value="">全部阶段</option>
              <option v-for="stage in stageOptions" :key="stage" :value="stage">{{ stage }}</option>
            </select>
          </label>
          <label>
            课程
            <input v-model="resourceFilter.course" placeholder="例如：高等数学上" />
          </label>
          <button type="submit">筛选资源</button>
        </form>
        <div class="feature-grid">
          <article v-for="item in resources" :key="item.id" class="glass-panel resource-card">
            <small>{{ item.stage }} · {{ item.course }} · {{ resourceTypeLabel(item.resource_type) }}</small>
            <h2>{{ item.title }}</h2>
            <p>{{ item.description }}</p>
            <RouterLink :to="item.url || '/practice'">进入学习</RouterLink>
          </article>
        </div>
      </section>

      <section v-else-if="mode === 'notebook'" class="notebook-layout">
        <form class="glass-panel note-editor" @submit.prevent="saveNote">
          <small>{{ editingNoteId ? "编辑笔记" : "新建笔记" }}</small>
          <input v-model="noteForm.title" placeholder="标题，例如：极限错因整理" required />
          <input v-model="noteForm.course" placeholder="课程，可选" />
          <input v-model="noteForm.knowledge_tag" placeholder="知识点，可选" />
          <textarea v-model="noteForm.content" rows="8" placeholder="写下定义、错因、证明思路或下一次复习提醒（上传附件后可不填）"></textarea>
          <section
            class="note-upload-zone"
            :class="{ 'is-dragging': noteDragging }"
            @dragenter.prevent="noteDragging = true"
            @dragover.prevent
            @dragleave.prevent="noteDragging = false"
            @drop.prevent="handleNoteDrop"
          >
            <div>
              <strong>文件与图片</strong>
              <small>拖到这里，或选择图片、PDF、Word、Excel、PPT、TXT、Markdown、CSV；单次总计不超过 60 MB</small>
            </div>
            <button :disabled="uploadingNoteFiles || noteAttachments.length >= 10" type="button" @click="noteFileInput?.click()">
              {{ uploadingNoteFiles ? "上传中..." : "选择附件" }}
            </button>
            <input
              ref="noteFileInput"
              hidden
              multiple
              type="file"
              accept="image/jpeg,image/png,image/webp,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.md,.csv"
              @change="handleNoteFilePick"
            />
          </section>
          <div v-if="noteAttachments.length" class="note-attachment-editor-list">
            <article v-for="file in noteAttachments" :key="file.id">
              <img v-if="isImageFile(file)" :src="file.url" :alt="file.name" />
              <span v-else class="note-file-symbol">{{ fileTypeSymbol(file) }}</span>
              <div>
                <strong :title="file.name">{{ file.name }}</strong>
                <small>{{ fileTypeLabel(file) }} · {{ formatFileSize(file.size_bytes) }}</small>
              </div>
              <a :href="file.url" target="_blank" rel="noopener" title="查看附件">查看</a>
              <button type="button" title="移除附件" @click="removeNoteAttachment(file)">×</button>
            </article>
          </div>
          <p v-if="noteUploadError" class="note-form-error" role="alert">{{ noteUploadError }}</p>
          <div class="note-actions">
            <button :disabled="uploadingNoteFiles || !canSaveNote" type="submit">{{ editingNoteId ? "保存修改" : "新增笔记" }}</button>
            <button v-if="editingNoteId" type="button" @click="cancelNoteEdit">取消编辑</button>
          </div>
          <p v-if="noteSaveError" class="note-form-error" role="alert">{{ noteSaveError }}</p>
        </form>
        <div class="note-list">
          <div v-if="!notes.length" class="glass-panel feature-empty">
            <strong>还没有笔记</strong>
            <p>可以记录定义、错因和证明思路，也可以直接上传课堂讲义、手写笔记或习题文件。</p>
          </div>
          <article v-for="note in notes" :key="note.id" class="glass-panel note-card">
            <small>{{ note.course || "未分类" }} · {{ note.knowledge_tag || "自由笔记" }}</small>
            <h2>{{ note.title }}</h2>
            <p v-if="note.content">{{ note.content }}</p>
            <div v-if="note.attachments?.length" class="note-card-attachments">
              <a v-for="file in note.attachments" :key="file.id" :href="file.url" target="_blank" rel="noopener">
                <img v-if="isImageFile(file)" :src="file.url" :alt="file.name" />
                <span v-else>{{ fileTypeSymbol(file) }}</span>
                <div>
                  <strong :title="file.name">{{ file.name }}</strong>
                  <small>{{ formatFileSize(file.size_bytes) }}</small>
                </div>
              </a>
            </div>
            <div class="note-card-actions">
              <button type="button" @click="editNote(note)">编辑</button>
              <button type="button" @click="removeNote(note.id)">删除</button>
            </div>
          </article>
        </div>
      </section>

      <section v-else-if="mode === 'settings'" class="settings-layout">
        <form class="glass-panel settings-form" @submit.prevent="saveSettings">
          <label>
            目标阶段
            <select v-model="settings.target_stage">
              <option v-for="stage in stageOptions" :key="stage" :value="stage">{{ stage }}</option>
            </select>
          </label>
          <label>
            目标课程
            <input v-model="settings.target_course" required />
          </label>
          <label>
            每周学习时长
            <input v-model.number="settings.weekly_hours" min="0.5" max="80" step="0.5" type="number" required />
          </label>
          <label>
            目标日期
            <input v-model="settings.exam_date" type="date" />
          </label>
          <label class="settings-toggle-row">
            <span><b>小逻主动提醒</b><small>允许每日问候、学习关心和站内提示；深夜仍保持静默。</small></span>
            <input v-model="settings.notify_xiaoluo" type="checkbox" role="switch" />
          </label>
          <button type="submit">保存设置</button>
          <p v-if="settingsSaved">已保存，回到首页后阶段信息会同步更新。</p>
        </form>
      </section>
  </section>
</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { apiDelete, apiGet, apiPost, apiPut, apiUpload } from "../api/client";
import ContactPicker from "../components/messages/ContactPicker.vue";
import MessageBubble from "../components/messages/MessageBubble.vue";
import MessageComposer from "../components/messages/MessageComposer.vue";
import { useUserStore } from "../stores/user";

const RadarChart = defineAsyncComponent(() => import("../components/RadarChart.vue"));

const route = useRoute();
const router = useRouter();
const user = useUserStore();


const pages = {
  messages: {
    kicker: "消息中心",
    title: "沟通与学习提醒",
    description: "集中查看系统通知，与老师沟通，也可以联系同一教师网络内的同学。"
  },
  profile: {
    kicker: "学习档案",
    title: "你的数学学习画像",
    description: "按阶段、课程、正确率和最近记录整理学习状态。"
  },
  achievements: {
    kicker: "成就徽章",
    title: "把进步留下痕迹",
    description: "根据练习量、正确率、证明题和模拟练习自动点亮徽章。"
  },
  resources: {
    kicker: "资源中心",
    title: "课程讲义与练习入口",
    description: "按阶段和课程找到讲义、专项练习、路线图和建模模板。"
  },
  notebook: {
    kicker: "笔记本",
    title: "记录定义、错因和证明思路",
    description: "笔记与当前账号绑定，可以跨页面长期保存。"
  },
  settings: {
    kicker: "设置中心",
    title: "调整你的学习目标",
    description: "目标阶段、目标课程、每周时长和目标日期会影响首页显示。"
  }
};

const mode = computed(() => String(route.name || "messages"));
const page = computed(() => pages[mode.value] || pages.messages);
const authRequired = computed(() => mode.value !== "resources" && !user.userId);

const loading = ref(false);
const error = ref("");
const messages = ref([]);
const messageTab = ref(route.query.teacher_id || route.query.conversation_id ? "teachers" : "notifications");
const messageConversations = ref([]);
const selectedConversationId = ref(null);
const conversationMessages = ref([]);
const messageThreadLoading = ref(false);
const messageSending = ref(false);
const messageThreadEl = ref(null);
const messageHasMore = ref(false);
const messageNextBeforeId = ref(null);
const messageContactPickerOpen = ref(false);
const messageContactsLoading = ref(false);
const messageContactGroups = ref([]);
const showAllMessageContacts = ref(false);
const pendingQuestionRef = ref(null);
const profile = ref({});
const abilityMap = ref({ cells: [] });
const weeklyDigest = ref(null);
const weeklyDigestMessageId = ref(null);
const weeklyDigestLoading = ref(false);
const achievements = ref([]);
const resources = ref([]);
const notes = ref([]);
const editingNoteId = ref(null);
const noteAttachments = ref([]);
const draftAttachmentIds = ref([]);
const noteFileInput = ref(null);
const uploadingNoteFiles = ref(false);
const noteDragging = ref(false);
const noteUploadError = ref("");
const noteSaveError = ref("");
const settingsSaved = ref(false);

const stageOptions = ["大一", "大二", "大三", "大四"];
const resourceFilter = reactive({ stage: "", course: "" });
const noteForm = reactive({ title: "", content: "", course: "", knowledge_tag: "" });
const settings = reactive({ target_stage: "大一", target_course: "高等数学上", weekly_hours: 8, exam_date: "", notify_xiaoluo: true });
const canSaveNote = computed(() => Boolean(noteForm.title.trim() && (noteForm.content.trim() || noteAttachments.value.length)));
const activeConversations = computed(() => messageConversations.value.filter((item) => item.relation === (messageTab.value === "peers" ? "student_student" : "teacher_student")));
const selectedConversation = computed(() => messageConversations.value.find((item) => item.id === selectedConversationId.value) || null);
const teacherUnreadCount = computed(() => messageConversations.value.filter((item) => item.relation === "teacher_student").reduce((sum, item) => sum + Number(item.unread_count || 0), 0));
const peerUnreadCount = computed(() => messageConversations.value.filter((item) => item.relation === "student_student").reduce((sum, item) => sum + Number(item.unread_count || 0), 0));
const visibleContactGroups = computed(() => {
  if (showAllMessageContacts.value) return messageContactGroups.value;
  const key = messageTab.value === "peers" ? "peers" : "teachers";
  return messageContactGroups.value.filter((group) => group.key === key);
});
const abilityRadar = computed(() => {
  const grouped = new Map();
  for (const cell of abilityMap.value.cells || []) {
    const current = grouped.get(cell.knowledge) || { total: 0, weighted: 0 };
    current.total += Number(cell.attempts || 0);
    current.weighted += Number(cell.accuracy || 0) * Number(cell.attempts || 0);
    grouped.set(cell.knowledge, current);
  }
  return [...grouped.entries()].map(([name, value]) => ({ name, score: value.total ? Math.round(value.weighted / value.total * 100) : 0 })).slice(0, 6);
});

function formatTime(value) {
  if (!value) {
    return "刚刚";
  }
  return new Date(value).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function typeLabel(value) {
  return {
    task: "任务",
    review: "复盘",
    assistant: "小逻",
    weekly_report: "学习周报",
    care_inactive: "学习关心",
    care_regress: "学习关心",
    care_late_night: "休息提醒",
    daily_greeting: "小逻播报",
    plan_due: "计划提醒",
    practice_followup: "小逻复盘",
    ticket_reply: "教师回复",
    teacher_advice: "学习调整建议",
    teacher_message: "教师消息",
    peer_message: "同学消息",
    assignment_report: "作业分析",
    system: "系统"
  }[value] || "通知";
}

function questionTypeLabel(value) { return ({ choice: "选择题", blank: "填空题", calculation: "计算题", proof: "证明题", comprehensive: "综合题" })[value] || value; }

function resourceTypeLabel(value) {
  return {
    lecture: "讲义",
    practice: "练习",
    roadmap: "路线",
    project: "项目"
  }[value] || "资源";
}

function badgeProgress(badge) {
  if (!badge.target) {
    return badge.unlocked ? 100 : 0;
  }
  return Math.max(0, Math.min(100, Math.round((Number(badge.progress || 0) / Number(badge.target)) * 100)));
}

function isImageFile(file) {
  return Boolean(file?.is_image || String(file?.mime_type || "").startsWith("image/"));
}

function formatFileSize(value) {
  const bytes = Number(value || 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function fileTypeLabel(file) {
  const name = String(file?.name || "").toLowerCase();
  if (isImageFile(file)) return "图片";
  if (name.endsWith(".pdf")) return "PDF";
  if (/\.(doc|docx)$/.test(name)) return "Word";
  if (/\.(xls|xlsx|csv)$/.test(name)) return "表格";
  if (/\.(ppt|pptx)$/.test(name)) return "演示文稿";
  return "文本文档";
}

function fileTypeSymbol(file) {
  return { PDF: "PDF", Word: "W", 表格: "X", 演示文稿: "P", 文本文档: "TXT" }[fileTypeLabel(file)] || "FILE";
}

async function loadMessages() {
  const [data, conversationData] = await Promise.all([apiGet("/api/messages"), apiGet("/api/messages/conversations")]);
  messages.value = data.items || [];
  messageConversations.value = conversationData.items || [];
  const requestedConversationId = Number(route.query.conversation_id || 0);
  if (messageConversations.value.some((item) => item.id === requestedConversationId)) {
    await selectMessageConversation(requestedConversationId, false);
    return;
  }
  const requestedTeacherId = Number(route.query.teacher_id || 0);
  if (requestedTeacherId) {
    await loadMessageContacts();
    const contact = messageContactGroups.value.flatMap((group) => group.items || []).find((item) => item.user_id === requestedTeacherId && item.relation === "teacher_student");
    if (contact) { await startMessageConversation(contact); return; }
  }
  const storedQuestion = sessionStorage.getItem("pending_message_question_ref");
  if (storedQuestion) {
    try {
      pendingQuestionRef.value = JSON.parse(storedQuestion);
      showAllMessageContacts.value = true;
      await loadMessageContacts();
      messageContactPickerOpen.value = true;
      return;
    } catch (parseError) {
      sessionStorage.removeItem("pending_message_question_ref");
    }
  }
  if (messageTab.value !== "notifications") {
    const initial = activeConversations.value[0];
    if (initial) await selectMessageConversation(initial.id, false);
  }
}

async function loadMessageConversationList() {
  const data = await apiGet("/api/messages/conversations");
  messageConversations.value = data.items || [];
}

async function scrollMessageThread() { await nextTick(); if (messageThreadEl.value) messageThreadEl.value.scrollTop = messageThreadEl.value.scrollHeight; }

async function selectMessageConversation(conversationId, updateRoute = true) {
  const conversation = messageConversations.value.find((item) => item.id === Number(conversationId));
  if (!conversation) return;
  messageTab.value = conversation.relation === "student_student" ? "peers" : "teachers";
  selectedConversationId.value = Number(conversationId);
  conversationMessages.value = [];
  messageHasMore.value = false;
  messageThreadLoading.value = true;
  if (updateRoute) await router.replace({ query: { conversation_id: conversationId } });
  try {
    const data = await apiGet(`/api/messages/conversations/${conversationId}`, { limit: 50 });
    conversationMessages.value = data.items || [];
    messageHasMore.value = Boolean(data.has_more);
    messageNextBeforeId.value = data.next_before_id;
    await apiPost(`/api/messages/conversations/${conversationId}/read`, {});
    await loadMessageConversationList();
    await scrollMessageThread();
  } finally { messageThreadLoading.value = false; }
}

async function loadEarlierMessages() {
  if (!messageHasMore.value || !messageNextBeforeId.value) return;
  messageThreadLoading.value = true;
  const previousHeight = messageThreadEl.value?.scrollHeight || 0;
  try {
    const data = await apiGet(`/api/messages/conversations/${selectedConversationId.value}`, { limit: 50, before_id: messageNextBeforeId.value });
    conversationMessages.value.unshift(...(data.items || []));
    messageHasMore.value = Boolean(data.has_more);
    messageNextBeforeId.value = data.next_before_id;
    await nextTick();
    if (messageThreadEl.value) messageThreadEl.value.scrollTop = messageThreadEl.value.scrollHeight - previousHeight;
  } finally { messageThreadLoading.value = false; }
}

async function sendConversationMessage(payload, resetComposer) {
  messageSending.value = true;
  try {
    const message = await apiPost(`/api/messages/conversations/${selectedConversationId.value}`, payload);
    conversationMessages.value.push(message);
    resetComposer();
    await loadMessageConversationList();
    await scrollMessageThread();
  } finally { messageSending.value = false; }
}

async function loadMessageContacts() {
  if (messageContactGroups.value.length) return;
  messageContactsLoading.value = true;
  try { const data = await apiGet("/api/messages/contacts"); messageContactGroups.value = data.groups || []; }
  finally { messageContactsLoading.value = false; }
}

async function openMessageContacts() {
  showAllMessageContacts.value = false;
  await loadMessageContacts();
  messageContactPickerOpen.value = true;
}

async function startMessageConversation(contact) {
  const result = await apiPost("/api/messages/conversations/start", { target_user_id: contact.user_id, relation: contact.relation });
  messageContactPickerOpen.value = false;
  showAllMessageContacts.value = false;
  await loadMessageConversationList();
  await selectMessageConversation(result.conversation_id);
}

async function switchMessageTab(tab) {
  messageTab.value = tab;
  if (tab === "notifications") {
    selectedConversationId.value = null;
    await router.replace({ query: {} });
    return;
  }
  const initial = activeConversations.value[0];
  if (initial) await selectMessageConversation(initial.id);
  else { selectedConversationId.value = null; await router.replace({ query: {} }); }
}

function clearPendingQuestion() {
  pendingQuestionRef.value = null;
  sessionStorage.removeItem("pending_message_question_ref");
}

async function loadProfile() {
  [profile.value, abilityMap.value] = await Promise.all([apiGet("/api/profile/summary"), apiGet("/api/profile/ability-map")]);
}

async function loadWeeklyDigest(messageId) {
  weeklyDigestLoading.value = true;
  try {
    const data = await apiPost("/api/review/weekly-digest", {});
    weeklyDigest.value = data.digest;
    weeklyDigestMessageId.value = messageId;
  } finally { weeklyDigestLoading.value = false; }
}

function printWeeklyDigest() {
  document.body.classList.add("weekly-digest-print");
  const cleanup = () => document.body.classList.remove("weekly-digest-print");
  window.addEventListener("afterprint", cleanup, { once: true });
  window.print();
  window.setTimeout(cleanup, 1000);
}

async function loadAchievements() {
  const data = await apiGet("/api/achievements");
  achievements.value = data.badges || [];
}

async function loadResources() {
  const data = await apiGet("/api/resources", resourceFilter);
  resources.value = data.items || [];
}

async function loadNotes() {
  const data = await apiGet("/api/notes");
  notes.value = data.items || [];
}

async function loadSettings() {
  const [data, preferences] = await Promise.all([apiGet("/api/user-goals"), apiGet("/api/preferences")]);
  Object.assign(settings, {
    target_stage: data.target_stage || "大一",
    target_course: data.target_course || "高等数学上",
    weekly_hours: Number(data.weekly_hours || 8),
    exam_date: data.exam_date || "",
    notify_xiaoluo: preferences.notify_xiaoluo !== false
  });
}

async function loadPage() {
  error.value = "";
  settingsSaved.value = false;
  if (authRequired.value) {
    return;
  }
  loading.value = true;
  try {
    if (mode.value === "messages") await loadMessages();
    if (mode.value === "profile") await loadProfile();
    if (mode.value === "achievements") await loadAchievements();
    if (mode.value === "resources") await loadResources();
    if (mode.value === "notebook") await loadNotes();
    if (mode.value === "settings") await loadSettings();
  } catch (requestError) {
    error.value = requestError.message || "接口暂时不可用。";
  } finally {
    loading.value = false;
  }
}

function clearNoteForm() {
  editingNoteId.value = null;
  noteAttachments.value = [];
  draftAttachmentIds.value = [];
  noteUploadError.value = "";
  noteSaveError.value = "";
  Object.assign(noteForm, { title: "", content: "", course: "", knowledge_tag: "" });
}

async function cleanupDraftAttachments() {
  const ids = [...draftAttachmentIds.value];
  draftAttachmentIds.value = [];
  await Promise.allSettled(ids.map((fileId) => apiDelete(`/api/uploads/${fileId}`)));
}

async function cancelNoteEdit() {
  await cleanupDraftAttachments();
  clearNoteForm();
}

async function editNote(note) {
  await cleanupDraftAttachments();
  editingNoteId.value = note.id;
  noteAttachments.value = [...(note.attachments || [])];
  noteUploadError.value = "";
  noteSaveError.value = "";
  Object.assign(noteForm, {
    title: note.title,
    content: note.content,
    course: note.course || "",
    knowledge_tag: note.knowledge_tag || ""
  });
}

async function uploadNoteFiles(fileList) {
  const files = [...(fileList || [])];
  noteUploadError.value = "";
  if (!files.length) return;
  if (noteAttachments.value.length + files.length > 10) {
    noteUploadError.value = "每条笔记最多保留 10 个附件。";
    return;
  }
  if (files.some((file) => file.size > 20 * 1024 * 1024)) {
    noteUploadError.value = "单个附件不能超过 20 MB。";
    return;
  }
  if (files.reduce((total, file) => total + file.size, 0) > 60 * 1024 * 1024) {
    noteUploadError.value = "单次上传的附件总大小不能超过 60 MB。";
    return;
  }
  uploadingNoteFiles.value = true;
  try {
    const formData = new FormData();
    formData.append("user_id", user.userId);
    files.forEach((file) => formData.append("files", file));
    const data = await apiUpload("/api/uploads/note-files", formData);
    const uploaded = (data.files || []).map((file) => ({
      ...file,
      is_image: String(file.mime_type || "").startsWith("image/")
    }));
    noteAttachments.value.push(...uploaded);
    draftAttachmentIds.value.push(...uploaded.map((file) => file.id));
  } catch (uploadError) {
    noteUploadError.value = uploadError.message || "附件上传失败。";
  } finally {
    uploadingNoteFiles.value = false;
  }
}

async function handleNoteFilePick(event) {
  await uploadNoteFiles(event.target.files);
  event.target.value = "";
}

async function handleNoteDrop(event) {
  noteDragging.value = false;
  await uploadNoteFiles(event.dataTransfer?.files);
}

async function removeNoteAttachment(file) {
  noteUploadError.value = "";
  if (draftAttachmentIds.value.includes(file.id)) {
    try {
      await apiDelete(`/api/uploads/${file.id}`);
      draftAttachmentIds.value = draftAttachmentIds.value.filter((fileId) => fileId !== file.id);
    } catch (removeError) {
      noteUploadError.value = removeError.message || "附件移除失败。";
      return;
    }
  }
  noteAttachments.value = noteAttachments.value.filter((item) => item.id !== file.id);
}

async function saveNote() {
  noteSaveError.value = "";
  if (!canSaveNote.value) {
    noteSaveError.value = "请填写标题，并输入内容或上传至少一个附件。";
    return;
  }
  const payload = {
    title: noteForm.title.trim(),
    content: noteForm.content.trim(),
    course: noteForm.course.trim() || null,
    knowledge_tag: noteForm.knowledge_tag.trim() || null,
    attachment_ids: noteAttachments.value.map((file) => file.id)
  };
  try {
    if (editingNoteId.value) {
      await apiPut(`/api/notes/${editingNoteId.value}`, payload);
    } else {
      await apiPost("/api/notes", payload);
    }
    draftAttachmentIds.value = [];
    clearNoteForm();
    await loadNotes();
  } catch (saveError) {
    noteSaveError.value = saveError.message || "笔记保存失败。";
  }
}

async function removeNote(noteId) {
  await apiDelete(`/api/notes/${noteId}`);
  if (editingNoteId.value === noteId) {
    clearNoteForm();
  }
  await loadNotes();
}

async function saveSettings() {
  settingsSaved.value = false;
  await apiPost("/api/user-goals", {
    target_stage: settings.target_stage,
    target_course: settings.target_course,
    weekly_hours: Number(settings.weekly_hours || 8),
    exam_date: settings.exam_date || null
  });
  await apiPut("/api/preferences", { notify_xiaoluo: settings.notify_xiaoluo });
  settingsSaved.value = true;
}

watch(() => route.name, loadPage);
watch(() => user.userId, loadPage);
watch(() => route.query.conversation_id, async (value) => {
  const conversationId = Number(value || 0);
  if (mode.value === "messages" && conversationId && conversationId !== selectedConversationId.value) {
    if (!messageConversations.value.length) await loadMessageConversationList();
    await selectMessageConversation(conversationId, false);
  }
});
onMounted(loadPage);
</script>

<style scoped src="../styles/views/side-feature.css"></style>
<style>
@media print {
  body.weekly-digest-print * { visibility: hidden !important; }
  body.weekly-digest-print .weekly-digest-card,
  body.weekly-digest-print .weekly-digest-card * { visibility: visible !important; }
  body.weekly-digest-print .weekly-digest-card { position: absolute; inset: 0; margin: 0; color: #33302b; border: 0; background: #fff; }
  body.weekly-digest-print .weekly-digest-card header button { display: none; }
}
</style>
