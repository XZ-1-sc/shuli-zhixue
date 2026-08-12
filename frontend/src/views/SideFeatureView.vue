<template>
  <section class="ref-shell feature-shell">
    <header class="ref-topbar">
      <RouterLink class="ref-brand" to="/">
        <span class="shield-mark">Σ</span>
        <strong>数理智学</strong>
      </RouterLink>

      <nav class="ref-topnav" aria-label="主导航">
        <RouterLink v-for="item in topNav" :key="item.to" :to="item.to">
          <span>{{ item.icon }}</span>
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="ref-actions">
        <RouterLink class="ghost-action" to="/">返回中控台</RouterLink>
        <UserAccountButton />
      </div>
    </header>

    <aside class="ref-sidebar">
      <nav class="side-menu" aria-label="学习菜单">
        <RouterLink v-for="item in sideNav" :key="item.to" :to="item.to">
          <span>{{ item.icon }}</span>
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>

    <main class="ref-main side-feature-main">
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

      <section v-else-if="mode === 'messages'" class="feature-grid messages-grid">
        <div v-if="!messages.length" class="glass-panel feature-empty feature-grid-empty">
          <strong>暂无消息</strong>
          <p>新账号不会自动生成个人通知。完成首测或保存学习目标后，这里会出现学习提醒。</p>
          <RouterLink to="/practice?mode=daily&limit=12">开始首测</RouterLink>
        </div>
        <article v-for="message in messages" :key="message.id" class="glass-panel message-card" :class="{ unread: !message.is_read }">
          <small>{{ typeLabel(message.type) }} · {{ formatTime(message.created_at) }}</small>
          <h2>{{ message.title }}</h2>
          <p>{{ message.content }}</p>
        </article>
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
          <textarea v-model="noteForm.content" rows="8" placeholder="写下定义、错因、证明思路或下一次复习提醒" required></textarea>
          <div class="note-actions">
            <button type="submit">{{ editingNoteId ? "保存修改" : "新增笔记" }}</button>
            <button v-if="editingNoteId" type="button" @click="resetNoteForm">取消编辑</button>
          </div>
        </form>
        <div class="note-list">
          <div v-if="!notes.length" class="glass-panel feature-empty">
            <strong>还没有笔记</strong>
            <p>可以先记录一个定义、错因或证明思路，后续复盘会更省力。</p>
          </div>
          <article v-for="note in notes" :key="note.id" class="glass-panel note-card">
            <small>{{ note.course || "未分类" }} · {{ note.knowledge_tag || "自由笔记" }}</small>
            <h2>{{ note.title }}</h2>
            <p>{{ note.content }}</p>
            <div>
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
          <button type="submit">保存设置</button>
          <p v-if="settingsSaved">已保存，回到首页后阶段信息会同步更新。</p>
        </form>
      </section>
    </main>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import UserAccountButton from "../components/UserAccountButton.vue";
import { apiDelete, apiGet, apiPost, apiPut } from "../api/client";
import { useUserStore } from "../stores/user";

const emit = defineEmits(["open-auth"]);
const route = useRoute();
const user = useUserStore();

const topNav = [
  { to: "/", label: "首页", icon: "⌂" },
  { to: "/roadmap", label: "学习规划", icon: "▤" },
  { to: "/practice", label: "做题训练", icon: "▧" },
  { to: "/knowledge", label: "知识图谱", icon: "⟡" },
  { to: "/review", label: "错题复盘", icon: "▣" }
];

const sideNav = [
  { to: "/", label: "学习中控台", icon: "⌂" },
  { to: "/messages", label: "消息中心", icon: "✉" },
  { to: "/profile", label: "学习档案", icon: "▤" },
  { to: "/achievements", label: "成就徽章", icon: "♕" },
  { to: "/resources", label: "资源中心", icon: "▣" },
  { to: "/notebook", label: "笔记本", icon: "▥" },
  { to: "/settings", label: "设置中心", icon: "⚙" }
];

const pages = {
  messages: {
    kicker: "消息中心",
    title: "学习提醒与系统通知",
    description: "把今日任务、错题回炉、小逻建议和系统提示集中在这里。"
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
const profile = ref({});
const achievements = ref([]);
const resources = ref([]);
const notes = ref([]);
const editingNoteId = ref(null);
const settingsSaved = ref(false);

const stageOptions = ["大一", "大二", "大三", "大四"];
const resourceFilter = reactive({ stage: "", course: "" });
const noteForm = reactive({ title: "", content: "", course: "", knowledge_tag: "" });
const settings = reactive({ target_stage: "大一", target_course: "高等数学上", weekly_hours: 8, exam_date: "" });

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
    system: "系统"
  }[value] || "通知";
}

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

async function loadMessages() {
  const data = await apiGet("/api/messages", { user_id: user.userId });
  messages.value = data.items || [];
}

async function loadProfile() {
  profile.value = await apiGet("/api/profile/summary", { user_id: user.userId });
}

async function loadAchievements() {
  const data = await apiGet("/api/achievements", { user_id: user.userId });
  achievements.value = data.badges || [];
}

async function loadResources() {
  const data = await apiGet("/api/resources", resourceFilter);
  resources.value = data.items || [];
}

async function loadNotes() {
  const data = await apiGet("/api/notes", { user_id: user.userId });
  notes.value = data.items || [];
}

async function loadSettings() {
  const data = await apiGet("/api/user-goals", { user_id: user.userId });
  Object.assign(settings, {
    target_stage: data.target_stage || "大一",
    target_course: data.target_course || "高等数学上",
    weekly_hours: Number(data.weekly_hours || 8),
    exam_date: data.exam_date || ""
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

function resetNoteForm() {
  editingNoteId.value = null;
  Object.assign(noteForm, { title: "", content: "", course: "", knowledge_tag: "" });
}

function editNote(note) {
  editingNoteId.value = note.id;
  Object.assign(noteForm, {
    title: note.title,
    content: note.content,
    course: note.course || "",
    knowledge_tag: note.knowledge_tag || ""
  });
}

async function saveNote() {
  const payload = {
    user_id: user.userId,
    title: noteForm.title.trim(),
    content: noteForm.content.trim(),
    course: noteForm.course.trim() || null,
    knowledge_tag: noteForm.knowledge_tag.trim() || null
  };
  if (editingNoteId.value) {
    await apiPut(`/api/notes/${editingNoteId.value}`, payload);
  } else {
    await apiPost("/api/notes", payload);
  }
  resetNoteForm();
  await loadNotes();
}

async function removeNote(noteId) {
  await apiDelete(`/api/notes/${noteId}`, { user_id: user.userId });
  if (editingNoteId.value === noteId) {
    resetNoteForm();
  }
  await loadNotes();
}

async function saveSettings() {
  settingsSaved.value = false;
  await apiPost("/api/user-goals", {
    user_id: user.userId,
    target_stage: settings.target_stage,
    target_course: settings.target_course,
    weekly_hours: Number(settings.weekly_hours || 8),
    exam_date: settings.exam_date || null
  });
  settingsSaved.value = true;
}

watch(() => route.name, loadPage);
watch(() => user.userId, loadPage);
onMounted(loadPage);
</script>
