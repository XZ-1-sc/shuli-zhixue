<template>
  <Teleport to="body">
    <div v-if="open" class="ai-question-backdrop" @click.self="close">
      <form ref="dialog" class="teacher-ai-question-modal" role="dialog" aria-modal="true"
        aria-labelledby="ai-question-title" :aria-busy="generating" tabindex="-1"
        @submit.prevent="generate" @keydown="handleKeydown">
        <header class="ai-question-header">
          <div><small>教师 AI 工作台</small><h2 id="ai-question-title">生成待审核题目</h2></div>
          <button type="button" class="ai-question-dismiss" aria-label="关闭 AI 出题" :disabled="generating" @click="close">×</button>
        </header>
        <div class="ai-question-body">
          <p class="ai-question-intro">生成内容会保存为仅自己可见的草稿，不会直接进入学生练习。</p>
          <p v-if="loadError" class="ai-question-error" role="alert">{{ loadError }} <button type="button" @click="loadOptions">重试加载</button></p>
          <fieldset :disabled="generating || loading" class="ai-question-fields">
            <label class="ai-question-wide"><span>课程</span><select v-model="form.course" required name="course"><option value="" disabled>请选择课程</option><option v-for="item in courses" :key="item.course_name" :value="item.course_name">{{ item.course_name }}</option></select></label>
            <label class="ai-question-wide"><span>知识点</span><input v-model.trim="form.knowledge_tag" name="knowledge_tag" list="ai-question-knowledge-options" required maxlength="160" placeholder="选择题库已有知识点，或自行输入" /><datalist id="ai-question-knowledge-options"><option v-for="tag in knowledgeOptions" :key="tag" :value="tag" /></datalist></label>
            <label><span>题型</span><select v-model="form.question_type" name="question_type"><option v-for="item in types" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
            <label><span>难度（1–5）</span><input v-model.number="form.difficulty" name="difficulty" type="number" min="1" max="5" step="1" required /></label>
            <label><span>数量（1–5）</span><input v-model.number="form.count" name="count" type="number" min="1" max="5" step="1" required /></label>
            <label class="ai-question-wide"><span>补充要求</span><textarea v-model="form.requirements" name="requirements" maxlength="1000" rows="3" placeholder="可选：参数范围、考察方式等"></textarea></label>
          </fieldset>
          <section v-if="result" class="ai-question-results" aria-live="polite">
            <h3>{{ result.created_count ? `已生成 ${result.created_count} 道私有草稿` : "本次未生成题目" }}</h3>
            <p>{{ result.notice }}</p>
            <RouterLink v-if="result.items.length" :to="`/teacher/questions/${result.items[0].id}/edit`" @click="close">打开首题审核编辑</RouterLink>
            <article v-for="item in result.items" :key="item.id" class="ai-question-result">
              <small>{{ item.type_label || typeLabel(item.question_type) }} · {{ item.course }} · AI 草稿</small>
              <h4>{{ truncate(item.question_text, 140) }}</h4>
              <p>{{ item.knowledge_tag }} · 难度 {{ item.difficulty }} · 答案：{{ item.question_type === "choice" ? item.correct_answer : truncate(item.standard_answer, 50) }}</p>
              <RouterLink :to="`/teacher/questions/${item.id}/edit`" @click="close">审核编辑</RouterLink>
            </article>
            <p v-for="(error, index) in result.errors" :key="index" class="ai-question-error">第 {{ error.index }} 道未通过校验：{{ error.reason }}</p>
          </section>
          <p v-if="errorText" class="ai-question-error" role="alert">{{ errorText }}</p>
        </div>
        <footer class="ai-question-actions">
          <button type="button" :disabled="generating" @click="close">关闭</button>
          <button class="ai-question-generate" :disabled="generating || loading || !courses.length" type="submit">{{ generating ? "生成与校验中…" : result ? "再生成一批" : "生成私有草稿" }}</button>
        </footer>
      </form>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { apiGet, apiPost } from "../api/client";

const props = defineProps({ open: Boolean, initialCourse: { type: String, default: "" } });
const emit = defineEmits(["close", "generated"]);
const dialog = ref(null), generating = ref(false), loading = ref(false);
const result = ref(null), errorText = ref(""), loadError = ref("");
const courses = ref([]), knowledgeCounts = ref([]);
const form = reactive({ course: "", knowledge_tag: "", question_type: "choice", difficulty: 3, count: 1, requirements: "" });
const types = [{ value: "choice", label: "选择题" }, { value: "blank", label: "填空题" }, { value: "calculation", label: "计算题" }, { value: "proof", label: "证明题" }, { value: "comprehensive", label: "综合题" }];
const knowledgeOptions = computed(() => [...new Set(knowledgeCounts.value.filter(item => item.course === form.course).map(item => String(item.knowledge_tag || "").trim()).filter(Boolean))].slice(0, 300));
let previousFocus = null, previousOverflow = null, loadVersion = 0;

function truncate(value, limit) { const text = String(value || ""); return text.length > limit ? `${text.slice(0, limit)}…` : text; }
function typeLabel(value) { return types.find(item => item.value === value)?.label || value; }
function close() { if (!generating.value) emit("close"); }
function restorePage() {
  if (previousOverflow !== null) { document.body.style.overflow = previousOverflow; previousOverflow = null; }
  if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
  previousFocus = null;
}
function handleKeydown(event) {
  if (event.key === "Escape") { event.preventDefault(); close(); }
  if (event.key !== "Tab") return;
  const targets = [...dialog.value.querySelectorAll("button, input, select, textarea, a[href]")].filter(item => !item.matches(":disabled") && item.getClientRects().length);
  if (!targets.length) { event.preventDefault(); dialog.value.focus(); return; }
  const first = targets[0], last = targets[targets.length - 1];
  if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.value)) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.value)) { event.preventDefault(); first.focus(); }
}
async function loadOptions() {
  const version = ++loadVersion;
  loading.value = true; loadError.value = "";
  try {
    const data = await apiGet("/api/courses");
    if (version !== loadVersion) return;
    courses.value = data.courses || [];
    if (!courses.value.some(item => item.course_name === form.course)) form.course = courses.value[0]?.course_name || "";
    try {
      const knowledge = await apiGet("/api/question-types");
      if (version === loadVersion) knowledgeCounts.value = knowledge.counts || [];
    } catch { /* Knowledge suggestions are optional; manual input remains available. */ }
  } catch (error) {
    if (version === loadVersion) loadError.value = error.message || "课程加载失败，请重试。";
  } finally { if (version === loadVersion) loading.value = false; }
}
async function generate() {
  if (generating.value || loading.value || !dialog.value.reportValidity()) return;
  if (!form.knowledge_tag.trim()) { errorText.value = "请输入知识点。"; return; }
  generating.value = true; errorText.value = ""; result.value = null;
  try {
    const data = await apiPost("/api/teacher/ai/generate-question", { ...form });
    result.value = { items: data.items || [], created_count: data.created_count || 0, errors: data.errors || [], notice: data.notice || "" };
    emit("generated", result.value);
  } catch (error) { errorText.value = error.message || "生成失败，请稍后重试。"; }
  finally { generating.value = false; }
}
watch(() => props.open, async open => {
  if (!open) { ++loadVersion; restorePage(); return; }
  previousFocus = document.activeElement;
  previousOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  result.value = null; errorText.value = "";
  if (props.initialCourse) form.course = props.initialCourse;
  loadOptions();
  await nextTick();
  dialog.value?.focus({ preventScroll: true });
}, { immediate: true });
onBeforeUnmount(() => { ++loadVersion; restorePage(); });
</script>

<style scoped>
.ai-question-backdrop { position: fixed; inset: 0; z-index: 240; display: grid; place-items: center; padding: 24px; background: rgba(37, 35, 31, .38); }
.teacher-ai-question-modal { box-sizing: border-box; width: min(560px, 100%); max-height: calc(100vh - 48px); max-height: calc(100dvh - 48px); min-height: 0; min-width: 0; display: grid; grid-template-rows: auto minmax(0, 1fr) auto; overflow: hidden; color: #33302b; background: #fffdf8; border: 1px solid #dfdad0; border-radius: 18px; box-shadow: 0 20px 65px rgba(43, 37, 28, .2); }
.ai-question-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 20px 24px; border-bottom: 1px solid #e6e1d8; }
.ai-question-header small { color: #706b62; font-size: 12px; }
.ai-question-header h2 { margin: 4px 0 0; font-size: 24px; line-height: 1.3; }
.ai-question-dismiss { flex: 0 0 36px; min-height: 36px; font-size: 24px; }
.ai-question-body { min-height: 0; overflow-y: auto; overscroll-behavior: contain; padding: 20px 24px; scrollbar-gutter: stable; overflow-wrap: anywhere; }
.ai-question-intro { margin: 0 0 18px; color: #706b62; line-height: 1.6; font-size: 14px; }
.ai-question-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; min-width: 0; margin: 0; padding: 0; border: 0; }
.ai-question-fields label { display: grid; gap: 7px; min-width: 0; font-size: 14px; }
.ai-question-wide { grid-column: 1 / -1; }
.ai-question-fields input, .ai-question-fields select, .ai-question-fields textarea { box-sizing: border-box; min-width: 0; width: 100%; border: 1px solid #dcd7ce; border-radius: 8px; background: #fff; color: inherit; padding: 10px 12px; font: inherit; }
.ai-question-fields textarea { resize: vertical; min-height: 84px; }
.teacher-ai-question-modal button { border: 1px solid #dcd7ce; border-radius: 8px; background: #fff; color: inherit; font: inherit; cursor: pointer; }
.teacher-ai-question-modal button:disabled { cursor: not-allowed; opacity: .6; }
.teacher-ai-question-modal :focus-visible { outline: 2px solid #287381; outline-offset: 2px; }
.ai-question-actions { display: flex; justify-content: flex-end; gap: 12px; padding: 16px 24px; border-top: 1px solid #e6e1d8; background: #fffdf8; }
.ai-question-actions button { min-height: 44px; padding: 10px 16px; white-space: nowrap; }
.ai-question-actions .ai-question-generate { background: #287381; border-color: #287381; color: #fff; font-weight: 600; }
.ai-question-results { margin-top: 24px; border-top: 1px solid #e6e1d8; padding-top: 18px; }
.ai-question-results h3 { margin: 0 0 10px; font-size: 18px; }
.ai-question-results p { font-size: 14px; line-height: 1.6; }
.ai-question-result { margin-top: 16px; padding-top: 16px; border-top: 1px solid #e6e1d8; }
.ai-question-result small { color: #706b62; }
.ai-question-result h4 { margin: 8px 0; font-size: 16px; }
.ai-question-results a { color: #287381; text-decoration: underline; }
.ai-question-error { color: #ad3c37; font-size: 14px; line-height: 1.6; }
@media (max-width: 600px) {
  .ai-question-backdrop { padding: 12px; }
  .teacher-ai-question-modal { max-height: calc(100vh - 24px); max-height: calc(100dvh - 24px); border-radius: 12px; }
  .ai-question-header, .ai-question-body { padding: 16px; }
  .ai-question-header h2 { font-size: 21px; }
  .ai-question-fields { grid-template-columns: minmax(0, 1fr); }
  .ai-question-actions { gap: 8px; padding: 12px; }
  .ai-question-actions button { padding: 10px 12px; }
}
</style>
