<template>
  <section class="step-solution">
    <header><div><small>从方法到迁移</small><h3>分步解答</h3></div><span v-if="sourceLabel">{{ sourceLabel }}</span></header>
    <ol v-if="steps.length">
      <li v-for="step in steps" :key="step.step_no" :class="stepTone(step.step_no)">
        <button type="button" :aria-expanded="openSteps.includes(step.step_no)" @click="toggle(step.step_no)">
          <b>{{ step.step_no }}</b><span>{{ step.title }}</span><em>{{ openSteps.includes(step.step_no) ? "收起" : "展开" }}</em>
        </button>
        <div v-if="openSteps.includes(step.step_no)">
          <p>{{ step.explanation }}</p>
          <code v-if="step.formula">{{ step.formula }}</code>
          <small v-if="step.caution">易错提示：{{ step.caution }}</small>
          <button class="ask-step" type="button" @click="askStep(step)">上一步没看懂？问小逻这一步</button>
        </div>
      </li>
    </ol>
    <p v-else class="step-empty">暂时没有可用的结构化步骤。</p>
    <p v-if="stepFeedback?.summary" class="step-feedback">{{ stepFeedback.summary }}<span v-if="stepFeedback.wrong_steps?.length">优先检查第 {{ stepFeedback.wrong_steps.map((item) => item.step_no).join("、") }} 步。</span></p>
    <button class="selfcheck-trigger" type="button" :disabled="selfcheckLoading" @click="startSelfcheck">{{ selfcheckLoading ? "小逻正在出题…" : "听懂了吗？开始 1 分钟自测" }}</button>
    <article v-if="selfcheckQuestion" class="selfcheck-card">
      <header><strong>1 分钟自测</strong><span>不计入正式正确率</span></header>
      <p>{{ selfcheckQuestion.question_text }}</p>
      <div v-if="selfcheckQuestion.question_type === 'choice'" class="selfcheck-options">
        <button v-for="(option, key) in selfcheckQuestion.options" :key="key" type="button" :disabled="Boolean(selfcheckResult)" :class="{ selected: selfcheckAnswer === key }" @click="selfcheckAnswer = key"><b>{{ key }}</b>{{ option }}</button>
      </div>
      <textarea v-else v-model="selfcheckAnswer" :disabled="Boolean(selfcheckResult)" placeholder="写下答案或关键思路"></textarea>
      <button v-if="!selfcheckResult" type="button" :disabled="!selfcheckAnswer || selfcheckSubmitting" @click="submitSelfcheck">{{ selfcheckSubmitting ? "核对中…" : "提交自测" }}</button>
      <div v-else :class="['selfcheck-result', { correct: selfcheckResult.is_correct }]">
        <strong>{{ selfcheckResult.is_correct ? "已形成迁移证据" : "还需回看第一处差异" }}</strong>
        <small>本次结果已单独保存为自测证据，不影响正式学情统计。</small>
      </div>
    </article>
    <p v-if="error" class="step-error">{{ error }}</p>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { apiPost } from "../../api/client";

const props = defineProps({
  questionId: { type: Number, required: true },
  recordId: { type: Number, default: null },
  initialSteps: { type: Array, default: () => [] },
  stepFeedback: { type: Object, default: null },
  source: { type: String, default: "" },
  knowledgeTag: { type: String, default: "" }
});
const steps = computed(() => props.initialSteps || []);
const sourceLabel = computed(() => ({ ai: "AI 结构化 · 待教师复核", teacher: "教师已审核", legacy: "由原解析整理" })[props.source] || "");
const openSteps = ref([1]);
const selfcheckLoading = ref(false);
const selfcheckSubmitting = ref(false);
const selfcheckQuestion = ref(null);
const selfcheckAnswer = ref("");
const selfcheckResult = ref(null);
const error = ref("");

function toggle(stepNo) { openSteps.value = openSteps.value.includes(stepNo) ? openSteps.value.filter((value) => value !== stepNo) : [...openSteps.value, stepNo]; }
function stepTone(stepNo) {
  if (props.stepFeedback?.wrong_steps?.some((item) => Number(item.step_no) === Number(stepNo))) return "needs-review";
  if (props.stepFeedback?.correct_steps?.includes(stepNo)) return "is-correct";
  return "";
}
function askStep(step) {
  window.dispatchEvent(new CustomEvent("xiaoluo:open", { detail: {
    prompt: `我没理解第 ${step.step_no} 步“${step.title}”。请只讲清这一步，给出可执行操作，并用一个追问确认我是否理解。`,
    context: { type: "solution_step", question_id: props.questionId, record_id: props.recordId, step_no: step.step_no },
    autoSend: true
  } }));
}
async function startSelfcheck() {
  selfcheckLoading.value = true; error.value = ""; selfcheckResult.value = null; selfcheckAnswer.value = "";
  try { const data = await apiPost("/api/practice/ai-selfcheck", { question_id: props.questionId, count: 1 }); selfcheckQuestion.value = data.questions?.[0] || null; if (!selfcheckQuestion.value) throw new Error("暂时没有生成可用自测题。"); }
  catch (exception) { error.value = exception.message || "自测题生成失败。"; }
  finally { selfcheckLoading.value = false; }
}
async function submitSelfcheck() {
  selfcheckSubmitting.value = true; error.value = "";
  try {
    const q = selfcheckQuestion.value;
    selfcheckResult.value = await apiPost("/api/practice/ai-selfcheck/submit", {
      task_id: `selfcheck-${Date.now()}`,
      source_question_id: props.questionId,
      generated_question: q.question_text,
      expected_answer: q.correct_answer || q.standard_answer,
      selected_answer: q.question_type === "choice" ? selfcheckAnswer.value : null,
      answer_text: q.question_type === "choice" ? null : selfcheckAnswer.value,
      knowledge_tag: q.knowledge_tag || props.knowledgeTag,
      evidence_type: "selfcheck",
      time_spent_seconds: 60
    });
  } catch (exception) { error.value = exception.message || "自测结果保存失败。"; }
  finally { selfcheckSubmitting.value = false; }
}
watch(() => props.questionId, () => { openSteps.value = [1]; selfcheckQuestion.value = null; selfcheckAnswer.value = ""; selfcheckResult.value = null; error.value = ""; });
</script>

<style scoped>
.step-solution{display:grid;gap:11px}.step-solution>header,.selfcheck-card>header{display:flex;align-items:center;justify-content:space-between;gap:10px}.step-solution h3{margin:2px 0 0}.step-solution header small,.step-solution header span{color:#777067;font-size:10px}.step-solution>ol{display:grid;gap:7px;margin:0;padding:0;list-style:none}.step-solution>ol>li{border:1px solid #ded7cb;background:#fff}.step-solution>ol>li.needs-review{border-left:3px solid #b4554a}.step-solution>ol>li.is-correct{border-left:3px solid #347a56}.step-solution li>button{display:grid;grid-template-columns:28px 1fr auto;align-items:center;width:100%;min-height:42px;padding:6px 9px;color:#33302b;text-align:left;background:#f8f4ec}.step-solution li>button b{display:grid;place-items:center;width:24px;height:24px;color:#fff;border-radius:50%;background:#2e7d8c}.step-solution li>button em{color:#777067;font-size:10px}.step-solution li>div{display:grid;gap:8px;padding:12px}.step-solution li p{margin:0;color:#4f4a43;line-height:1.65}.step-solution code{padding:9px;color:#225d67;background:#edf6f5;white-space:normal}.step-solution li div>small{color:#ad5046;line-height:1.5}.ask-step,.selfcheck-trigger,.selfcheck-card>button{min-height:35px;padding:0 10px;border:1px solid rgba(46,125,140,.32);color:#287381;background:#fff;font-weight:800}.selfcheck-trigger{width:100%;background:#edf6f5}.step-feedback{display:grid;gap:3px;margin:0;padding:10px;color:#6b514e;border-left:3px solid #b4554a;background:#fbefec;font-size:11px}.selfcheck-card{display:grid;gap:10px;padding:12px;border:1px solid #ded7cb;background:#fff}.selfcheck-card>p{margin:0;line-height:1.6}.selfcheck-options{display:grid;gap:6px}.selfcheck-options button{display:flex;gap:8px;padding:9px;color:#33302b;border:1px solid #ded7cb;background:#fff;text-align:left}.selfcheck-options button.selected{border-color:#2e7d8c;background:#edf6f5}.selfcheck-card textarea{min-height:76px;padding:9px;resize:vertical;border:1px solid #ded7cb}.selfcheck-result{display:grid;gap:3px;padding:9px;color:#8e4039;background:#fbefec}.selfcheck-result.correct{color:#2f6f4d;background:#edf6ee}.step-empty,.step-error{margin:0;color:#817a70;font-size:11px}.step-error{color:#ad5046}
</style>
