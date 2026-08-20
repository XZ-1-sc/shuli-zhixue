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
import { apiDelete, apiGet, apiPost, apiPut, apiUpload } from "../api/client";
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
const settings = reactive({ target_stage: "大一", target_course: "高等数学上", weekly_hours: 8, exam_date: "" });
const canSaveNote = computed(() => Boolean(noteForm.title.trim() && (noteForm.content.trim() || noteAttachments.value.length)));

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
    user_id: user.userId,
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
  await apiDelete(`/api/notes/${noteId}`, { user_id: user.userId });
  if (editingNoteId.value === noteId) {
    clearNoteForm();
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
