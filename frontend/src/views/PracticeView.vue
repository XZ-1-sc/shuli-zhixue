<template>
  <section class="practice-ref-page" :class="{ 'is-assessment': isAssessment }">
    <section class="practice-toolbar" aria-label="练习控制栏">
      <div class="practice-title-block">
        <strong>{{ isAssessment ? "数学基础首测" : "做题训练" }}</strong>
        <small v-if="isAssessment">完成后由小逻生成学习计划</small>
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
            <section class="answer-step-editor">
              <header><strong>分步作答</strong><small>逐步填写，便于小逻定位第一处偏差</small></header>
              <label v-for="(_, index) in answerSteps" :key="index"><span>{{ index + 1 }}</span><input v-model="answerSteps[index]" :disabled="Boolean(result)" :placeholder="`第 ${index + 1} 步`" /><button v-if="!result && answerSteps.length > 1" type="button" @click="answerSteps.splice(index, 1)">×</button></label>
              <button v-if="!result && answerSteps.length < 20" type="button" @click="answerSteps.push('')">＋ 添加步骤</button>
            </section>

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
            <div v-if="result.review_brief" class="ai-result-summary">
              <span>小逻复盘 · {{ result.review_brief.metrics?.[0]?.value }}</span>
              <p>{{ result.review_brief.suggestion }}</p>
              <button type="button" @click="openQuestionAssistant">问小逻</button>
            </div>
            <p v-if="result.companion_signal?.message" class="companion-result-line" :class="`tone-${result.companion_signal.tone}`">{{ result.companion_signal.message }}</p>
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
          <button class="tool-button" :disabled="!currentQuestion || !result" type="button" @click="shareCurrentQuestion">↗ 分享给老师 / 同学</button>
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
          <StepSolution
            :question-id="Number(currentQuestion.id)"
            :record-id="Number(result.record_id)"
            :initial-steps="result.solution_steps || []"
            :step-feedback="result.step_feedback"
            :source="result.solution_steps_source"
            :knowledge-tag="currentQuestion.knowledge_tag"
          />
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
          <button class="ask-xiaoluo-button" type="button" @click="openQuestionAssistant">◉ 问小逻：这题为什么错？</button>
          <button v-if="result.is_correct === false" class="chain-recovery-button" type="button" :disabled="recoveryLoading" @click="loadChainRecovery">
            {{ recoveryLoading ? "正在分析前置知识…" : "◎ 小逻推荐补根路径" }}
          </button>
          <section v-if="recovery" class="chain-recovery-card">
            <small>{{ recovery.strategy === "repair_prerequisite" ? "先补前置" : "继续加固" }}</small>
            <strong>{{ recovery.target.knowledge_tag || recovery.target.course }}</strong>
            <p>{{ recovery.reason }}</p>
            <RouterLink :to="{ path: '/practice', query: { course: recovery.target.course, knowledge_tag: recovery.target.knowledge_tag, limit: 3 } }">按推荐练 3 题 ›</RouterLink>
          </section>
          <button class="ai-similar-button" type="button" :disabled="similarLoading" @click="generateSimilarQuestions">
            {{ similarLoading ? "小逻正在出题…" : "✦ AI 出题" }}
          </button>
          <section v-if="similarQuestions.length" class="ai-similar-practice">
            <header><div><small>AI 变式训练</small><strong>不计入诊断统计</strong></div><span>AI 生成，仅供参考</span></header>
            <article v-for="(question, index) in similarQuestions" :key="question.id">
              <small>变式 {{ index + 1 }} · {{ question.knowledge_tag }}</small>
              <p>{{ question.question_text }}</p>
              <div v-if="question.question_type === 'choice'" class="ai-similar-options">
                <button v-for="(option, key) in question.options" :key="key" type="button" :disabled="Boolean(similarChecked[question.id])" :class="{ selected: similarAnswers[question.id] === key }" @click="similarAnswers[question.id] = key"><b>{{ key }}</b>{{ option }}</button>
              </div>
              <textarea v-else v-model="similarAnswers[question.id]" :disabled="Boolean(similarChecked[question.id])" placeholder="写下你的思路或关键步骤"></textarea>
              <button v-if="!similarChecked[question.id]" type="button" :disabled="!similarAnswers[question.id]" @click="checkSimilar(question)">核对答案</button>
              <div v-else class="ai-similar-answer" :class="{ correct: similarChecked[question.id].correct === true }">
                <strong>{{ similarChecked[question.id].label }}</strong><p>参考答案：{{ question.standard_answer }}</p><small>{{ question.analysis_text }}</small>
              </div>
            </article>
          </section>
          <section class="question-discussion">
            <header><div><small>答后讨论</small><strong>同题思路与教师精选</strong></div><span>{{ comments.length }} 条</span></header>
            <p v-if="commentsLoading">正在加载讨论…</p>
            <article v-for="comment in comments" :key="comment.id" :class="{ best: comment.is_best }">
              <header><strong>{{ comment.author }}</strong><em v-if="comment.is_best">教师精选</em><small>{{ comment.author_role === 'teacher' ? '教师' : '同学' }}</small></header>
              <p>{{ comment.content }}</p><div v-if="comment.images?.length" class="comment-images"><a v-for="image in comment.images" :key="image.id" :href="image.url" target="_blank"><img :src="image.url" alt="评论图片" /></a></div>
              <footer><button type="button" :disabled="comment.liked" @click="upvoteComment(comment)">△ {{ comment.upvotes }}</button><button type="button" @click="askAboutComment(comment)">问小逻</button></footer>
            </article>
            <form @submit.prevent="postComment"><textarea v-model="commentText" maxlength="3000" placeholder="分享你的解题思路或提出具体疑问"></textarea><div v-if="commentImages.length" class="comment-image-chips"><span v-for="file in commentImages" :key="file.id">{{ file.name }}</span></div><footer><button type="button" @click="commentImageInput?.click()">上传图片</button><input ref="commentImageInput" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden @change="uploadCommentImages" /><button type="submit" :disabled="commentPosting || (!commentText.trim() && !commentImages.length)">{{ commentPosting ? '发布中…' : '发布讨论' }}</button></footer></form>
          </section>
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
import StepSolution from "../components/student/StepSolution.vue";
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
const answerSteps = ref([""]);
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
const similarLoading = ref(false);
const recoveryLoading = ref(false);
const recovery = ref(null);
const similarQuestions = ref([]);
const similarAnswers = reactive({});
const similarChecked = reactive({});
const comments = ref([]), commentsLoading = ref(false), commentText = ref(""), commentImages = ref([]), commentPosting = ref(false), commentImageInput = ref(null);
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
  answerSteps.value = [""];
  result.value = null;
  uploadError.value = "";
  noteSaved.value = false;
  similarQuestions.value = [];
  recovery.value = null;
  Object.keys(similarAnswers).forEach((key) => delete similarAnswers[key]);
  Object.keys(similarChecked).forEach((key) => delete similarChecked[key]);
  startedAt.value = Date.now();
  const saved = currentQuestionId.value ? attempts[currentQuestionId.value] : null;
  if (saved) {
    selectedAnswer.value = saved.selected_answer || "";
    answerText.value = saved.answer_text || "";
    answerSteps.value = saved.answer_steps?.length ? [...saved.answer_steps] : [""];
    result.value = saved;
    loadComments();
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
      answer_steps: answerSteps.value.map(step => step.trim()).filter(Boolean),
      attachment_ids: attachments.value.map((file) => file.id),
      time_spent_seconds: elapsedSeconds.value,
      practice_mode: filters.mode
    });
    const saved = { ...response, selected_answer: selectedAnswer.value || null, answer_text: answerText.value || null };
    attempts[currentQuestion.value.id] = saved;
    result.value = saved;
    await loadComments();
    if (response.assessment_complete && response.assessment_report) {
      assessmentReport.value = response.assessment_report;
      window.dispatchEvent(new CustomEvent("xiaoluo:assessment-complete", { detail: response.assessment_report }));
    }
    if (!isAssessment.value && response.review_brief) {
      window.dispatchEvent(new CustomEvent("xiaoluo:practice-complete", { detail: response.review_brief }));
    }
    if (response.celebration_card) window.dispatchEvent(new CustomEvent("xiaoluo:practice-complete", { detail: response.celebration_card }));
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

function openQuestionAssistant() {
  if (!currentQuestion.value || !result.value) return openXiaoluo();
  window.dispatchEvent(new CustomEvent("xiaoluo:open", {
    detail: {
      prompt: "请结合我的答案和解析，说明这题错在哪里，并给我一个可执行的改进步骤。",
      context: { type: "question", question_id: currentQuestion.value.id, record_id: result.value.record_id },
      autoSend: true
    }
  }));
}

async function shareCurrentQuestion() {
  if (!currentQuestion.value) return;
  sessionStorage.setItem("pending_message_question_ref", JSON.stringify({
    question_id: currentQuestion.value.id,
    record_id: result.value?.record_id || null
  }));
  await router.push("/messages");
}

async function generateSimilarQuestions() {
  if (!currentQuestion.value) return;
  similarLoading.value = true;
  pageError.value = "";
  try {
    const data = await apiPost("/api/practice/ai-similar", { question_id: currentQuestion.value.id, count: 2 });
    similarQuestions.value = data.questions || [];
    Object.keys(similarAnswers).forEach((key) => delete similarAnswers[key]);
    Object.keys(similarChecked).forEach((key) => delete similarChecked[key]);
  } catch (error) { pageError.value = error.message || "AI 变式题生成失败。"; }
  finally { similarLoading.value = false; }
}

async function loadComments() {
  if (!currentQuestion.value || !result.value) { comments.value = []; return; }
  commentsLoading.value = true;
  try { const data = await apiGet(`/api/questions/${currentQuestion.value.id}/comments`); comments.value = data.items || []; }
  catch { comments.value = []; }
  finally { commentsLoading.value = false; }
}
async function uploadCommentImages(event) {
  const files = Array.from(event.target.files || []).slice(0, Math.max(0, 5 - commentImages.value.length));
  if (!files.length) return;
  const form = new FormData(); files.forEach(file => form.append("files", file));
  try { const data = await apiUpload("/api/uploads/comment-images", form); commentImages.value.push(...(data.files || [])); }
  catch (error) { pageError.value = error.message; }
  finally { if (commentImageInput.value) commentImageInput.value.value = ""; }
}
async function postComment() {
  if (!currentQuestion.value) return; commentPosting.value = true;
  try { await apiPost(`/api/questions/${currentQuestion.value.id}/comments`, { content: commentText.value, image_ids: commentImages.value.map(item => item.id) }); commentText.value = ""; commentImages.value = []; await loadComments(); }
  catch (error) { pageError.value = error.message; }
  finally { commentPosting.value = false; }
}
async function upvoteComment(comment) { try { const data = await apiPost(`/api/comments/${comment.id}/upvote`); comment.liked = true; comment.upvotes = data.upvotes; } catch (error) { pageError.value = error.message; } }
function askAboutComment(comment) { window.dispatchEvent(new CustomEvent("xiaoluo:open", { detail: { prompt: `请判断这条同题讨论是否合理，并结合标准解法解释：${comment.content || '图片思路'}`, context: { type: "question", question_id: currentQuestion.value.id, record_id: result.value.record_id }, autoSend: true } })); }

async function checkSimilar(question) {
  const answer = String(similarAnswers[question.id] || "").trim();
  try {
    const data = await apiPost("/api/practice/ai-selfcheck/submit", {
      task_id: `transfer-${Date.now()}`,
      source_question_id: currentQuestion.value.id,
      generated_question: question.question_text,
      selected_answer: question.question_type === "choice" ? answer : null,
      answer_text: question.question_type === "choice" ? null : answer,
      expected_answer: question.correct_answer || question.standard_answer,
      knowledge_tag: question.knowledge_tag || currentQuestion.value.knowledge_tag,
      evidence_type: "transfer",
      time_spent_seconds: 0
    });
    similarChecked[question.id] = { ...data, correct: data.is_correct, label: data.is_correct ? "回答正确，已形成迁移证据" : "先对照解析找出第一处差异" };
  } catch (exception) { pageError.value = exception.message || "迁移证据保存失败。"; }
}

async function loadChainRecovery() {
  if (!result.value?.record_id) return;
  recoveryLoading.value = true; pageError.value = "";
  try { recovery.value = await apiPost("/api/recommend/chain-recovery", { record_id: result.value.record_id }); }
  catch (exception) { pageError.value = exception.message || "补根路径分析失败。"; }
  finally { recoveryLoading.value = false; }
}

function handleKeydown(event) {
  if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
  const map = { "1": "A", "2": "B", "3": "C", "4": "D", a: "A", b: "B", c: "C", d: "D" };
  if (map[event.key.toLowerCase()] && currentQuestion.value?.question_type === "choice") selectChoice(map[event.key.toLowerCase()]);
  if (event.key === "ArrowLeft") jumpTo(currentIndex.value - 1);
  if (event.key === "ArrowRight") nextQuestion();
}

watch(scratchText, (value) => localStorage.setItem("math_brain_scratch", value));
watch(resultForCurrent, (value) => { result.value = value; if (value) loadComments(); else comments.value = []; });

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
