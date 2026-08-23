<template>
  <section class="practice-ref-page" :class="{ 'is-assessment': isAssessment }">
    <section class="practice-toolbar" aria-label="练习控制栏">
      <div class="practice-title-block">
        <strong>{{ isAssessment ? "数学基础首测" : "做题训练" }}</strong>
        <small v-if="isAssessment">{{ assessmentStage }} · 完成后由小逻生成学习计划</small>
      </div>
      <div class="practice-mode-switch">
        <button :class="{ active: !isAssessment && filters.mode !== 'mock' }" type="button" @click="setMode('daily')">随机练习</button>
        <button :class="{ active: filters.mode === 'mock' }" type="button" @click="startMock">模拟测试</button>
      </div>
      <div class="practice-clock">◷ {{ elapsedLongLabel }}</div>
      <button class="practice-top-button" :class="{ active: scratchOpen }" type="button" @click="scratchOpen = !scratchOpen">▤ 草稿纸</button>
      <button class="xiaoluo-chip" type="button" @click="openXiaoluo">◉ 小逻</button>
    </section>

    <div v-if="pageError" class="practice-alert" role="alert">
      <strong>暂时无法继续</strong>
      <span>{{ pageError }}</span>
      <button type="button" @click="loadQuestions">重试</button>
    </div>

    <main class="practice-ref-layout">
      <aside class="practice-ref-left">
        <section class="ref-filter-card">
          <h2>{{ isAssessment ? "首测范围" : "题型与知识点" }}</h2>
          <p v-if="isAssessment" class="assessment-note">题目按五类题型混合抽取，提交后不能修改。图片作答将进入教师复核。</p>
          <select v-else v-model="filters.course" @change="loadQuestions">
            <option value="">全部知识点</option>
            <option v-for="course in courses" :key="course.course_name" :value="course.course_name">{{ course.course_name }}</option>
          </select>
          <div class="ref-type-list">
            <button
              v-for="type in typeOptions"
              :key="type.value"
              :class="{ active: !isAssessment && filters.question_type === type.value }"
              :disabled="isAssessment"
              type="button"
              @click="chooseType(type.value)"
            >
              <span>{{ type.icon }}</span>
              <strong>{{ type.label }}</strong>
              <em>({{ countByType(type.value) }})</em>
            </button>
          </div>
        </section>

        <section class="progress-card">
          <div class="progress-head">
            <h2>{{ isAssessment ? "首测进度" : "练习进度" }}</h2>
            <span>{{ completionPercent }}%</span>
          </div>
          <div class="small-ring" :style="{ '--completion': `${completionPercent}%` }">
            <strong>{{ completedCount }} / {{ questions.length || filters.limit }}</strong>
            <span>正确率 {{ accuracyLabel }}</span>
          </div>
          <ul>
            <li><i class="done"></i>已完成 <b>{{ completedCount }}</b></li>
            <li><i class="right"></i>正确 <b>{{ correctCount }}</b></li>
            <li><i class="wrong"></i>错误 <b>{{ wrongCount }}</b></li>
            <li><i class="pending"></i>待复核 <b>{{ pendingCount }}</b></li>
            <li><i></i>未做 <b>{{ remainingCount }}</b></li>
          </ul>
        </section>

        <section class="question-nav-card">
          <h2>题目导航</h2>
          <div class="number-grid">
            <button
              v-for="number in navNumbers"
              :key="number"
              :class="navClass(number - 1)"
              type="button"
              @click="jumpTo(number - 1)"
            >
              {{ number }}
            </button>
          </div>
          <p><i class="right"></i>答对 <i class="wrong"></i>答错 <i class="pending"></i>待复核 <i></i>未作答</p>
        </section>
      </aside>

      <article class="practice-paper-wrap">
        <div class="paper-sheet">
          <header>
            <button class="bookmark" :class="{ active: isBookmarked }" type="button" aria-label="收藏本题" @click="toggleBookmark">{{ isBookmarked ? "★" : "☆" }}</button>
            <strong>第 {{ currentIndex + 1 }} / {{ questions.length || 0 }} 题</strong>
            <em>{{ currentQuestion?.type_label || "题型" }}</em>
            <small>难度 {{ currentQuestion?.difficulty || 1 }}</small>
            <b>{{ currentQuestion?.fine_tag || currentQuestion?.knowledge_tag || "等待抽题" }}</b>
          </header>

          <p class="paper-question">{{ displayQuestionText }}</p>

          <div v-if="loading" class="question-loading">正在为你准备中文题目...</div>
          <div v-else-if="currentQuestion?.question_type === 'choice'" class="paper-options">
            <button
              v-for="(option, key) in displayOptions"
              :key="key"
              type="button"
              :disabled="Boolean(result)"
              :class="{
                selected: selectedAnswer === key,
                correct: result?.correct_answer === key,
                wrong: result && selectedAnswer === key && result.correct_answer !== key
              }"
              @click="selectChoice(key)"
            >
              <span>{{ key }}</span>
              {{ option }}
              <b v-if="result && selectedAnswer === key && result.correct_answer !== key">×</b>
            </button>
          </div>
          <div v-else-if="currentQuestion" class="subjective-answer-block">
            <textarea v-model="answerText" :disabled="Boolean(result)" placeholder="在这里写出关键步骤或证明思路，也可以上传纸面作答图片。"></textarea>

            <section class="answer-upload-box" :class="{ 'is-dragging': dragging }" @dragenter.prevent="dragging = true" @dragover.prevent @dragleave.prevent="dragging = false" @drop.prevent="handleDrop">
              <div>
                <strong>上传作答图片</strong>
                <span>适合计算题、证明题和手写草稿。支持 JPG、PNG、WebP，单张不超过 8 MB。</span>
              </div>
              <button :disabled="Boolean(result) || uploading || attachments.length >= 5" type="button" @click="imageInput?.click()">
                {{ uploading ? "上传中..." : "+ 选择图片" }}
              </button>
              <input ref="imageInput" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden @change="handleFileInput" />
            </section>

            <div v-if="attachments.length" class="answer-image-grid">
              <article v-for="file in attachments" :key="file.id">
                <img :src="file.previewUrl" :alt="file.name" />
                <div>
                  <span>{{ file.name }}</span>
                  <small>{{ formatBytes(file.size_bytes) }}</small>
                </div>
                <button v-if="!result" type="button" aria-label="移除图片" @click="removeAttachment(file)">×</button>
              </article>
            </div>
            <p v-if="uploadError" class="upload-error" role="alert">{{ uploadError }}</p>
          </div>

          <div v-if="result" class="inline-result-card" :class="resultTone">
            <strong>{{ resultTitle }}</strong>
            <span v-if="result.pending_review">图片作答已安全保存，教师复核后会更新分数和诊断。</span>
            <span v-else>正确答案：{{ result.correct_answer || result.standard_answer }}</span>
            <small v-if="selectedAnswer">你的答案：{{ selectedAnswer }}</small>
          </div>

          <section v-if="assessmentReport" class="assessment-complete-card">
            <small>首测完成</small>
            <h2>{{ assessmentReport.plan?.headline }}</h2>
            <p>{{ assessmentReport.summary }}</p>
            <div>
              <span>自动评分正确率 <b>{{ assessmentReport.accuracy }}%</b></span>
              <span v-if="assessmentReport.pending_review_count">待教师复核 <b>{{ assessmentReport.pending_review_count }} 题</b></span>
            </div>
            <button type="button" @click="openXiaoluo">查看小逻完整分析</button>
          </section>
        </div>

        <footer class="paper-actions">
          <button class="tool-button" :class="{ active: isBookmarked }" type="button" @click="toggleBookmark">{{ isBookmarked ? "★ 已收藏" : "☆ 收藏本题" }}</button>
          <button class="tool-button" type="button" @click="noteOpen = !noteOpen">✎ {{ noteOpen ? "收起笔记" : "题目笔记" }}</button>
          <button class="submit-button" :disabled="!canSubmit || submitting" type="button" @click="submitAnswer">{{ submitting ? "提交中..." : "提交答案" }}</button>
          <button class="next-button" :disabled="currentIndex >= questions.length - 1 || (isAssessment && !result)" type="button" @click="nextQuestion">下一题 ▶</button>
        </footer>

        <form v-if="noteOpen" class="quick-note-editor" @submit.prevent="saveNote">
          <textarea v-model="noteText" placeholder="记录这道题的关键方法、卡点或复盘结论。"></textarea>
          <button :disabled="savingNote || !noteText.trim()" type="submit">{{ savingNote ? "保存中..." : "保存到笔记本" }}</button>
          <span v-if="noteSaved">已保存，可在“笔记本”中查看。</span>
        </form>
      </article>

      <aside class="analysis-ref-panel">
        <header>
          <h2>▥ 解析与错因</h2>
          <span>{{ result ? "已生成" : "待提交" }}</span>
        </header>
        <template v-if="result && !result.pending_review">
          <section class="standard-answer">
            <h3>标准答案</h3>
            <p>{{ result.standard_answer }}</p>
          </section>
          <section class="key-steps-ref">
            <h3>关键步骤</h3>
            <ol>
              <li v-for="step in result.key_steps" :key="step">{{ step }}</li>
            </ol>
          </section>
          <section class="mistake-box">
            <h3>解析与常见错误</h3>
            <p>{{ result.analysis_text }}</p>
            <ul v-if="result.common_errors?.length">
              <li v-for="item in result.common_errors" :key="item">{{ item }}</li>
            </ul>
          </section>
          <RouterLink class="next-recommend-card" :to="recommendationLink">
            下一组推荐：{{ result.next_recommendation?.title || "同知识点巩固练习" }}
            <span>›</span>
          </RouterLink>
        </template>
        <section v-else-if="result?.pending_review" class="review-pending-panel">
          <span>⌛</span>
          <h3>等待教师复核</h3>
          <p>图片作答已绑定当前题目。复核完成后，系统会把得分、教师反馈和错因更新到学习档案。</p>
          <small>参考答案暂不用于自动判分，避免误判手写过程。</small>
        </section>
        <p v-else class="analysis-empty">提交后显示标准答案、关键步骤、常见错误和下一组推荐。图片作答会进入教师复核。</p>
      </aside>
    </main>

    <aside v-if="scratchOpen" class="scratch-drawer">
      <header><strong>临时草稿纸</strong><button type="button" @click="scratchOpen = false">关闭</button></header>
      <textarea v-model="scratchText" placeholder="这里的草稿只保存在当前浏览器，不会作为答案提交。"></textarea>
      <small>已自动保存在当前浏览器。</small>
    </aside>

    <footer class="practice-shortcut-bar">
      <span>课程：{{ currentQuestion?.course || "等待抽题" }}</span>
      <span>题型：{{ currentQuestion?.type_label || "-" }}</span>
      <span>知识点：{{ currentQuestion?.fine_tag || currentQuestion?.knowledge_tag || "-" }}</span>
      <small>快捷键：1/A、2/B、3/C、4/D、← 上一题、→ 下一题</small>
    </footer>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { onBeforeRouteUpdate, RouterLink, useRoute, useRouter } from "vue-router";

import { apiDelete, apiGet, apiPost, apiUpload } from "../api/client";
import { useUserStore } from "../stores/user";

const emit = defineEmits(["open-auth"]);
const route = useRoute();
const router = useRouter();
const user = useUserStore();
const stages = ref([]);
const courses = ref([]);
const questions = ref([]);
const currentIndex = ref(0);
const selectedAnswer = ref("");
const answerText = ref("");
const result = ref(null);
const attempts = reactive({});
const attachmentsByQuestion = reactive({});
const submitting = ref(false);
const loading = ref(false);
const uploading = ref(false);
const uploadError = ref("");
const pageError = ref("");
const dragging = ref(false);
const imageInput = ref(null);
const assessmentReport = ref(null);
const assessmentStage = ref("");
const startedAt = ref(Date.now());
const sessionStartedAt = ref(Date.now());
const now = ref(Date.now());
const scratchOpen = ref(false);
const scratchText = ref(localStorage.getItem("math_brain_scratch") || "");
const noteOpen = ref(false);
const noteText = ref("");
const noteSaved = ref(false);
const savingNote = ref(false);
const bookmarks = ref(new Set(JSON.parse(localStorage.getItem("math_brain_bookmarks") || "[]")));
let timer;

const filters = reactive({
  stage: route.query.stage || "",
  course: route.query.course || "",
  knowledge_tag: route.query.knowledge_tag || "",
  question_type: route.query.question_type || "",
  mode: route.query.mode || "custom",
  limit: Number(route.query.limit || 12),
  task_id: ""
});

const typeOptions = [
  { value: "", label: "全部题型", icon: "⌄" },
  { value: "choice", label: "选择题", icon: "▣" },
  { value: "blank", label: "填空题", icon: "▤" },
  { value: "calculation", label: "计算题", icon: "▧" },
  { value: "proof", label: "证明题", icon: "✎" },
  { value: "comprehensive", label: "综合题", icon: "▥" }
];

const isAssessment = computed(() => filters.mode === "assessment");
const currentQuestion = computed(() => questions.value[currentIndex.value] || null);
const currentQuestionId = computed(() => currentQuestion.value?.id);
const resultForCurrent = computed(() => currentQuestionId.value ? attempts[currentQuestionId.value] || null : null);
const attachments = computed(() => currentQuestionId.value ? attachmentsByQuestion[currentQuestionId.value] || [] : []);
const navNumbers = computed(() => Array.from({ length: questions.value.length }, (_, index) => index + 1));
const elapsedSeconds = computed(() => Math.max(0, Math.round((now.value - startedAt.value) / 1000)));
const elapsedLongLabel = computed(() => {
  const total = Math.max(0, Math.round((now.value - sessionStartedAt.value) / 1000));
  const hours = String(Math.floor(total / 3600)).padStart(2, "0");
  const minutes = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  const seconds = String(total % 60).padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
});
const completedAttempts = computed(() => Object.values(attempts));
const completedCount = computed(() => completedAttempts.value.length);
const correctCount = computed(() => completedAttempts.value.filter((item) => item.is_correct === true).length);
const wrongCount = computed(() => completedAttempts.value.filter((item) => item.is_correct === false).length);
const pendingCount = computed(() => completedAttempts.value.filter((item) => item.pending_review || item.review_status === "pending").length);
const gradedCount = computed(() => correctCount.value + wrongCount.value);
const remainingCount = computed(() => Math.max(questions.value.length - completedCount.value, 0));
const completionPercent = computed(() => questions.value.length ? Math.round(completedCount.value / questions.value.length * 100) : 0);
const accuracyLabel = computed(() => gradedCount.value ? Math.round(correctCount.value / gradedCount.value * 100) : 0);
const displayQuestionText = computed(() => normalizeQuestionText(currentQuestion.value?.question_text || (loading.value ? "正在抽题..." : "暂无可用题目")));
const displayOptions = computed(() => Object.fromEntries(Object.entries(currentQuestion.value?.options || {}).map(([key, value]) => [key, normalizeQuestionText(value)])));
const canSubmit = computed(() => {
  if (!currentQuestion.value || result.value || uploading.value) return false;
  if (currentQuestion.value.question_type === "choice") return Boolean(selectedAnswer.value);
  return Boolean(answerText.value.trim() || attachments.value.length);
});
const resultTitle = computed(() => {
  if (result.value?.pending_review) return "已提交，等待复核";
  return result.value?.is_correct ? "回答正确" : "回答错误";
});
const resultTone = computed(() => ({ correct: result.value?.is_correct === true, pending: result.value?.pending_review }));
const isBookmarked = computed(() => currentQuestionId.value ? bookmarks.value.has(currentQuestionId.value) : false);
const recommendationLink = computed(() => ({
  path: "/practice",
  query: {
    mode: "wrong_book",
    stage: result.value?.next_recommendation?.stage,
    course: result.value?.next_recommendation?.course,
    knowledge_tag: result.value?.next_recommendation?.knowledge_tag,
    limit: 8
  }
}));

function normalizeQuestionText(value) {
  return String(value || "").replace(/[□▢◻]/g, "____").replace(/^#+\s*/gm, "").replace(/\s{3,}/g, "  ").trim();
}

function countByType(type) {
  return type ? questions.value.filter((question) => question.question_type === type).length : questions.value.length;
}

function resetCurrentDraft() {
  selectedAnswer.value = "";
  answerText.value = "";
  result.value = null;
  uploadError.value = "";
  noteSaved.value = false;
  startedAt.value = Date.now();
  const saved = currentQuestionId.value ? attempts[currentQuestionId.value] : null;
  if (saved) {
    selectedAnswer.value = saved.selected_answer || "";
    answerText.value = saved.answer_text || "";
    result.value = saved;
  }
}

async function loadStages() {
  const data = await apiGet("/api/stages");
  stages.value = data.stages || [];
  await loadCourses();
}

async function loadCourses() {
  const data = await apiGet("/api/courses", { stage: filters.stage });
  courses.value = data.courses || [];
}

function hydrateAssessmentAttempts(data) {
  for (const question of data.questions || []) {
    if (!question.attempt) continue;
    const attempt = {
      ...question.attempt,
      question_id: question.id,
      pending_review: question.attempt.review_status === "pending"
    };
    attempts[question.id] = attempt;
  }
}

async function loadQuestions() {
  if (!user.userId) {
    emit("open-auth");
    return;
  }
  loading.value = true;
  pageError.value = "";
  assessmentReport.value = null;
  Object.keys(attempts).forEach((key) => delete attempts[key]);
  try {
    let data;
    if (isAssessment.value) {
      data = await apiPost("/api/assessment/start", {
        stage: filters.stage || null,
        limit: filters.limit,
        restart: false
      });
      assessmentStage.value = data.stage;
      hydrateAssessmentAttempts(data);
      if (data.report) assessmentReport.value = data.report;
      const unfinishedIndex = (data.questions || []).findIndex((question) => !question.answered);
      currentIndex.value = unfinishedIndex >= 0 ? unfinishedIndex : Math.max((data.questions || []).length - 1, 0);
    } else {
      const endpoint = filters.mode === "mock" ? "/api/mock-exam" : "/api/practice/random";
      data = await apiGet(endpoint, {
        stage: filters.stage,
        course: filters.course,
        knowledge_tag: filters.knowledge_tag,
        question_type: filters.question_type,
        mode: filters.mode,
        limit: filters.limit
      });
      currentIndex.value = 0;
    }
    questions.value = data.questions || [];
    filters.task_id = data.task_id || "";
    sessionStartedAt.value = data.started_at ? new Date(data.started_at).getTime() : Date.now();
    resetCurrentDraft();
    if (!questions.value.length) pageError.value = "当前筛选条件下暂无中文题目，请调整课程或题型。";
  } catch (error) {
    pageError.value = error.message || "题目加载失败。";
    questions.value = [];
  } finally {
    loading.value = false;
  }
}

async function chooseType(type) {
  if (isAssessment.value) return;
  filters.question_type = type;
  filters.limit = type ? 8 : Number(route.query.limit || 12);
  await loadQuestions();
}

async function setMode(mode) {
  if (filters.mode === mode) return;
  filters.mode = mode;
  filters.limit = mode === "mock" ? 20 : 12;
  await router.replace({ path: "/practice", query: { mode, limit: filters.limit } });
}

function startMock() {
  setMode("mock");
}

function selectChoice(key) {
  if (!result.value) selectedAnswer.value = key;
}

function validateFiles(files) {
  const allowed = new Set(["image/jpeg", "image/png", "image/webp"]);
  if (!files.length) return [];
  if (attachments.value.length + files.length > 5) throw new Error("每道题最多上传 5 张图片。");
  for (const file of files) {
    if (!allowed.has(file.type)) throw new Error("仅支持 JPG、PNG 或 WebP 图片。");
    if (file.size > 8 * 1024 * 1024) throw new Error(`${file.name} 超过 8 MB，请压缩后重试。`);
  }
  return files;
}

async function uploadFiles(fileList) {
  uploadError.value = "";
  let files;
  try {
    files = validateFiles(Array.from(fileList || []));
  } catch (error) {
    uploadError.value = error.message;
    return;
  }
  if (!files.length || !currentQuestionId.value) return;
  uploading.value = true;
  try {
    const formData = new FormData();
    formData.append("user_id", String(user.userId));
    files.forEach((file) => formData.append("files", file));
    const data = await apiUpload("/api/uploads/answer-images", formData);
    const uploaded = (data.files || []).map((file) => ({ ...file, previewUrl: file.url }));
    attachmentsByQuestion[currentQuestionId.value] = [...attachments.value, ...uploaded];
  } catch (error) {
    uploadError.value = error.message || "图片上传失败。";
  } finally {
    uploading.value = false;
    if (imageInput.value) imageInput.value.value = "";
  }
}

function handleFileInput(event) {
  uploadFiles(event.target.files);
}

function handleDrop(event) {
  dragging.value = false;
  if (!result.value) uploadFiles(event.dataTransfer.files);
}

async function removeAttachment(file) {
  try {
    await apiDelete(`/api/uploads/${file.id}`);
    attachmentsByQuestion[currentQuestionId.value] = attachments.value.filter((item) => item.id !== file.id);
  } catch (error) {
    uploadError.value = error.message;
  }
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function submitAnswer() {
  if (!canSubmit.value || !currentQuestion.value) return;
  submitting.value = true;
  pageError.value = "";
  try {
    const response = await apiPost("/api/practice/submit", {
      task_id: filters.task_id || "local-task",
      question_id: currentQuestion.value.id,
      selected_answer: selectedAnswer.value || null,
      answer_text: answerText.value.trim() || null,
      attachment_ids: attachments.value.map((file) => file.id),
      time_spent_seconds: elapsedSeconds.value,
      practice_mode: filters.mode
    });
    const saved = { ...response, selected_answer: selectedAnswer.value || null, answer_text: answerText.value || null };
    attempts[currentQuestion.value.id] = saved;
    result.value = saved;
    if (response.assessment_complete && response.assessment_report) {
      assessmentReport.value = response.assessment_report;
      window.dispatchEvent(new CustomEvent("xiaoluo:assessment-complete", { detail: response.assessment_report }));
    }
  } catch (error) {
    pageError.value = error.message || "答案提交失败。";
  } finally {
    submitting.value = false;
  }
}

function navClass(index) {
  const question = questions.value[index];
  const attempt = question ? attempts[question.id] : null;
  return {
    current: index === currentIndex.value,
    done: attempt?.is_correct === true,
    wrong: attempt?.is_correct === false,
    pending: attempt?.pending_review || attempt?.review_status === "pending"
  };
}

function jumpTo(index) {
  if (index >= 0 && index < questions.value.length) {
    currentIndex.value = index;
    resetCurrentDraft();
  }
}

function nextQuestion() {
  if (currentIndex.value < questions.value.length - 1 && (!isAssessment.value || result.value)) jumpTo(currentIndex.value + 1);
}

function toggleBookmark() {
  if (!currentQuestionId.value) return;
  const next = new Set(bookmarks.value);
  if (next.has(currentQuestionId.value)) next.delete(currentQuestionId.value);
  else next.add(currentQuestionId.value);
  bookmarks.value = next;
  localStorage.setItem("math_brain_bookmarks", JSON.stringify([...next]));
}

async function saveNote() {
  if (!noteText.value.trim() || !currentQuestion.value) return;
  savingNote.value = true;
  try {
    await apiPost("/api/notes", {
      title: `${currentQuestion.value.fine_tag || currentQuestion.value.knowledge_tag} · 第 ${currentIndex.value + 1} 题`,
      content: noteText.value.trim(),
      course: currentQuestion.value.course,
      knowledge_tag: currentQuestion.value.knowledge_tag
    });
    noteSaved.value = true;
    noteText.value = "";
  } catch (error) {
    pageError.value = error.message || "笔记保存失败。";
  } finally {
    savingNote.value = false;
  }
}

function openXiaoluo() {
  window.dispatchEvent(new CustomEvent("xiaoluo:open"));
}

function handleKeydown(event) {
  if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
  const map = { "1": "A", "2": "B", "3": "C", "4": "D", a: "A", b: "B", c: "C", d: "D" };
  if (map[event.key.toLowerCase()] && currentQuestion.value?.question_type === "choice") selectChoice(map[event.key.toLowerCase()]);
  if (event.key === "ArrowLeft") jumpTo(currentIndex.value - 1);
  if (event.key === "ArrowRight") nextQuestion();
}

watch(scratchText, (value) => localStorage.setItem("math_brain_scratch", value));
watch(resultForCurrent, (value) => { result.value = value; });

onBeforeRouteUpdate(async (to) => {
  filters.stage = to.query.stage || "";
  filters.course = to.query.course || "";
  filters.knowledge_tag = to.query.knowledge_tag || "";
  filters.question_type = to.query.question_type || "";
  filters.mode = to.query.mode || "custom";
  filters.limit = Number(to.query.limit || 12);
  await loadCourses();
  await loadQuestions();
});

onMounted(async () => {
  timer = window.setInterval(() => { now.value = Date.now(); }, 1000);
  window.addEventListener("keydown", handleKeydown);
  await loadStages();
  await loadQuestions();
});

onUnmounted(() => {
  window.clearInterval(timer);
  window.removeEventListener("keydown", handleKeydown);
});
</script>

<style scoped src="../styles/views/practice.css"></style>
