<template>
  <section class="student-assignment-work">
    <header>
      <RouterLink to="/assignments">← 我的作业</RouterLink>
      <div><small>{{ detail.assignment?.class_name }}</small><strong>{{ detail.assignment?.title || "正在加载" }}</strong></div>
      <span v-if="canEdit && remainingSeconds !== null" class="student-assignment-countdown">剩余 {{ remainingText }}</span>
      <span v-else-if="detail.assignment?.due_at">截止 {{ formatTime(detail.assignment.due_at) }}</span>
      <UserAccountButton />
    </header>

    <main v-if="loading" class="student-assignment-empty">正在准备试卷…</main>
    <main v-else-if="error" class="student-assignment-empty"><h2>无法打开作业</h2><p>{{ error }}</p><button @click="load">重试</button></main>
    <main v-else-if="!detail.attempt" class="student-start-assignment">
      <small>{{ detail.assignment.teacher_name }} · {{ detail.assignment.course }}</small>
      <h1>{{ detail.assignment.title }}</h1><p>{{ detail.assignment.description || "请独立完成全部题目并按时提交。" }}</p>
      <dl><div><dt>题目数量</dt><dd>{{ detail.questions.length }} 题</dd></div><div><dt>总分</dt><dd>{{ detail.assignment.total_score }} 分</dd></div><div><dt>限时</dt><dd>{{ detail.assignment.time_limit_minutes ? `${detail.assignment.time_limit_minutes} 分钟` : "不限时" }}</dd></div></dl>
      <button @click="start">开始作业</button>
    </main>

    <main v-else class="student-paper-layout">
      <aside>
        <h2>题目导航</h2>
        <div><button v-for="(question, index) in detail.questions" :key="question.id" :class="{ active: index === currentIndex, done: question.saved_answer?.id }" @click="switchQuestion(index)">{{ index + 1 }}</button></div>
        <p>已完成 {{ answeredCount }}/{{ detail.questions.length }}</p>
        <button v-if="canEdit" class="submit-all" :disabled="answeredCount < detail.questions.length" @click="submitAll">提交整份作业</button>
        <button v-else-if="detail.attempt.status === 'returned'" class="submit-all correction" @click="start">开始订正</button>
        <button v-else-if="canRetry" class="submit-all" @click="start">再次作答</button>
        <RouterLink v-else to="/assignments">返回作业列表</RouterLink>
      </aside>

      <article v-if="current" class="student-assignment-paper">
        <header><span>第 {{ currentIndex + 1 }} / {{ detail.questions.length }} 题</span><em>{{ current.type_label }} · {{ current.points }} 分</em><small>{{ current.knowledge_tag }}</small></header>
        <h2>{{ current.question_text }}</h2>
        <div v-if="current.attachments?.question?.length" class="student-question-figures"><img v-for="file in current.attachments.question" :key="file.id" :src="file.url" :alt="file.name" /></div>

        <div v-if="current.question_type === 'choice'" class="student-assignment-options">
          <button v-for="(option, key) in current.options" :key="key" :disabled="!canEdit" :class="{ selected: answer.selected_answer === key, correct: detail.answers_revealed && current.correct_answer === key, wrong: detail.answers_revealed && answer.selected_answer === key && current.correct_answer !== key }" @click="answer.selected_answer = key"><b>{{ key }}</b>{{ option }}</button>
        </div>
        <textarea v-else v-model="answer.answer_text" :disabled="!canEdit" rows="8" placeholder="写出答案和关键步骤，也可以上传手写作答图片。"></textarea>

        <section v-if="current.question_type !== 'choice' && canEdit" class="answer-upload-box">
          <div><strong>上传手写答案</strong><span>支持 JPG、PNG、WebP，最多 5 张</span></div>
          <button :disabled="uploading || attachments.length >= 5" @click="imageInput?.click()">{{ uploading ? "上传中…" : "+ 选择图片" }}</button>
          <input ref="imageInput" hidden type="file" multiple accept="image/jpeg,image/png,image/webp" @change="uploadImages" />
        </section>
        <div v-if="attachments.length" class="answer-image-grid"><article v-for="file in attachments" :key="file.id"><img :src="file.previewUrl" :alt="file.name" /><span>{{ file.name }}</span><button v-if="canEdit" type="button" @click="removeAttachment(file)">×</button></article></div>
        <p v-if="message" class="student-save-message">{{ message }}</p>

        <section v-if="detail.answers_revealed" class="student-assignment-analysis">
          <h3>标准答案与解析</h3><p><strong>得分：</strong>{{ current.saved_answer.score ?? "待评" }} / {{ current.points }}</p>
          <p v-if="current.saved_answer.teacher_feedback"><strong>教师评语：</strong>{{ current.saved_answer.teacher_feedback }}</p>
          <p><strong>标准答案：</strong>{{ current.standard_answer }}</p><ol><li v-for="step in current.key_steps" :key="step">{{ step }}</li></ol><p>{{ current.analysis_text }}</p>
          <div v-if="current.attachments?.analysis?.length" class="student-question-figures analysis"><img v-for="file in current.attachments.analysis" :key="file.id" :src="file.url" :alt="file.name" /></div>
        </section>

        <footer><button :disabled="currentIndex <= 0" @click="switchQuestion(currentIndex - 1)">上一题</button><button v-if="canEdit" class="save-answer" :disabled="saving" @click="saveAnswer">{{ saving ? "保存中…" : "保存本题" }}</button><button :disabled="currentIndex >= detail.questions.length - 1" @click="switchQuestion(currentIndex + 1)">下一题</button></footer>
      </article>
    </main>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { apiDelete, apiGet, apiPost, apiPut, apiUpload } from "../api/client";
import { useUserStore } from "../stores/user";
import UserAccountButton from "../components/UserAccountButton.vue";

const route = useRoute(); const user = useUserStore();
const loading = ref(true); const error = ref(""); const detail = ref({ assignment: null, attempt: null, questions: [], answers_revealed: false });
const currentIndex = ref(0); const saving = ref(false); const uploading = ref(false); const message = ref(""); const imageInput = ref(null); const attachments = ref([]);
const remainingSeconds = ref(null); const timerId = ref(null); const timeoutSubmitting = ref(false); const questionOpenedAt = ref(Date.now());
const answer = reactive({ selected_answer: "", answer_text: "", attachment_ids: [] });
const current = computed(() => detail.value.questions[currentIndex.value]);
const canEdit = computed(() => detail.value.attempt?.status === "in_progress");
const canRetry = computed(() => detail.value.attempt?.status === "graded" && detail.value.assignment?.status === "published" && Number(detail.value.attempt?.attempt_no || 1) < Number(detail.value.assignment?.max_attempts || 1));
const answeredCount = computed(() => detail.value.questions.filter((question) => question.saved_answer?.answered_at).length);
const remainingText = computed(() => { const seconds = Math.max(0, Number(remainingSeconds.value || 0)); const minutes = Math.floor(seconds / 60); return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`; });

function hydrateAnswer() { const saved = current.value?.saved_answer || {}; answer.selected_answer = saved.selected_answer || ""; answer.answer_text = saved.answer_text || ""; answer.attachment_ids = saved.attachment_ids || []; attachments.value = answer.attachment_ids.map((id) => ({ id, name: `作答图片 ${id}`, previewUrl: `/api/files/${id}` })); questionOpenedAt.value = Date.now(); message.value = ""; }
watch(currentIndex, hydrateAnswer);
function formatTime(value) { return new Date(value).toLocaleString("zh-CN"); }
function switchQuestion(index) { currentIndex.value = index; }
function stopTimer() { if (timerId.value) window.clearInterval(timerId.value); timerId.value = null; }
function hasAnswer() { return Boolean(answer.selected_answer || answer.answer_text.trim() || answer.attachment_ids.length); }
function startTimer() { stopTimer(); const remaining = detail.value.attempt?.remaining_seconds; remainingSeconds.value = remaining === null || remaining === undefined ? null : Number(remaining); if (!canEdit.value || remainingSeconds.value === null) return; if (remainingSeconds.value <= 0) { submitForTimeout(); return; } timerId.value = window.setInterval(async () => { remainingSeconds.value = Math.max(0, remainingSeconds.value - 1); if (remainingSeconds.value === 3 && hasAnswer()) await saveAnswer(true); if (remainingSeconds.value === 0) { stopTimer(); await submitForTimeout(); } }, 1000); }

async function load() { loading.value = true; error.value = ""; try { detail.value = await apiGet(`/api/assignments/${route.params.assignmentId}`); hydrateAnswer(); startTimer(); } catch (e) { error.value = e.message; } finally { loading.value = false; } }
async function start() { try { detail.value = await apiPost(`/api/assignments/${route.params.assignmentId}/start`); hydrateAnswer(); startTimer(); } catch (e) { message.value = e.message; } }
async function uploadImages(event) { const files = [...(event.target.files || [])]; if (!files.length) return; uploading.value = true; try { const form = new FormData(); form.append("user_id", user.userId); files.forEach((file) => form.append("files", file)); const data = await apiUpload("/api/uploads/answer-images", form); for (const file of data.files || []) { attachments.value.push({ ...file, previewUrl: file.url }); answer.attachment_ids.push(file.id); } } catch (e) { message.value = e.message; } finally { uploading.value = false; event.target.value = ""; } }
async function removeAttachment(file) { if (!current.value.saved_answer?.id) { try { await apiDelete(`/api/uploads/${file.id}`); } catch (e) { message.value = e.message; return; } } attachments.value = attachments.value.filter((item) => item.id !== file.id); answer.attachment_ids = answer.attachment_ids.filter((id) => id !== file.id); }
async function saveAnswer(silent = false) { saving.value = true; if (!silent) message.value = ""; try { await apiPut(`/api/assignments/${route.params.assignmentId}/answers`, { assignment_question_id: current.value.assignment_question_id, ...answer, time_spent_seconds: Math.max(1, Math.floor((Date.now() - questionOpenedAt.value) / 1000)) }); detail.value = await apiGet(`/api/assignments/${route.params.assignmentId}`); hydrateAnswer(); if (!silent) message.value = "本题已保存。"; } catch (e) { message.value = e.message; } finally { saving.value = false; } }
async function submitAll() { if (!window.confirm("提交后不能修改答案，确定交卷吗？")) return; try { detail.value = await apiPost(`/api/assignments/${route.params.assignmentId}/submit`); stopTimer(); hydrateAnswer(); } catch (e) { message.value = e.message; } }
async function submitForTimeout() { if (timeoutSubmitting.value || !canEdit.value) return; timeoutSubmitting.value = true; message.value = "作业限时已结束，正在自动交卷…"; try { detail.value = await apiPost(`/api/assignments/${route.params.assignmentId}/submit`); hydrateAnswer(); message.value = "已自动交卷。"; } catch (e) { message.value = e.message; } finally { timeoutSubmitting.value = false; } }
onMounted(load);
onBeforeUnmount(stopTimer);
</script>
