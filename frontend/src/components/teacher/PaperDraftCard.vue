<template>
  <section class="paper-draft-card teacher-panel">
    <header>
      <div><small>一句话出卷 · 只生成草稿</small><strong>告诉小逻你想要什么卷</strong></div>
      <span>教师审核后才能发布</span>
    </header>
    <div class="paper-command">
      <select v-model="classId"><option value="" disabled>选择班级</option><option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }} · {{ item.course }}</option></select>
      <input v-model.trim="message" placeholder="例如：出份极限周测，中等偏难 20 题，限时 45 分钟" @keyup.enter="parseIntent" />
      <button type="button" :disabled="parsing || !classId || message.length < 2" @click="parseIntent">{{ parsing ? "解析中…" : "解析意图" }}</button>
    </div>
    <p v-if="error" class="paper-message is-error">{{ error }}</p>
    <section v-if="intent" class="intent-editor">
      <header><strong>请确认组卷意图</strong><small>缺失项可以在这里补齐</small></header>
      <div>
        <label><span>试卷标题</span><input v-model="intent.title" maxlength="160" /></label>
        <label><span>题量</span><input v-model.number="intent.count" type="number" min="1" max="100" /></label>
        <label><span>限时（分钟）</span><input v-model.number="intent.timed_minutes" type="number" min="5" max="600" placeholder="不限时" /></label>
        <label><span>知识点（逗号分隔）</span><input v-model="knowledgeText" placeholder="极限, 连续" /></label>
      </div>
      <fieldset><legend>题型</legend><label v-for="item in typeOptions" :key="item.value"><input v-model="intent.types" type="checkbox" :value="item.value" />{{ item.label }}</label></fieldset>
      <div class="difficulty-mix"><label><span>基础</span><input v-model.number="intent.difficulty_mix.easy" type="number" min="0" max="1" step="0.1" /></label><label><span>中等</span><input v-model.number="intent.difficulty_mix.medium" type="number" min="0" max="1" step="0.1" /></label><label><span>挑战</span><input v-model.number="intent.difficulty_mix.hard" type="number" min="0" max="1" step="0.1" /></label></div>
      <label class="supplement-switch"><input v-model="allowSupplement" type="checkbox" /><span>题库不足时让小逻补充待审核题目草稿（不会自动加入试卷）</span></label>
      <button class="create-draft" type="button" :disabled="creating" @click="createDraft">{{ creating ? "正在匹配题库…" : "生成作业草稿" }}</button>
    </section>
  </section>
</template>

<script setup>
import { ref, watch } from "vue";
import { apiPost } from "../../api/client";

const props = defineProps({ classes: { type: Array, default: () => [] }, initialClassId: { type: [Number, String], default: "" } });
const emit = defineEmits(["created"]);
const classId = ref(props.initialClassId || "");
const message = ref("");
const intent = ref(null);
const knowledgeText = ref("");
const allowSupplement = ref(false);
const parsing = ref(false);
const creating = ref(false);
const error = ref("");
const typeOptions = [{ value: "choice", label: "选择" }, { value: "blank", label: "填空" }, { value: "calculation", label: "计算" }, { value: "proof", label: "证明" }, { value: "comprehensive", label: "综合" }];

watch(() => props.initialClassId, (value) => { if (value) classId.value = value; });
async function parseIntent() {
  parsing.value = true; error.value = "";
  try {
    const data = await apiPost("/api/teacher/ai/assignment-intent", { message: message.value, class_id: Number(classId.value) });
    intent.value = data.intent;
    knowledgeText.value = (data.intent.knowledge_tags || []).join(", ");
  } catch (exception) { error.value = exception.message || "组卷意图解析失败。"; }
  finally { parsing.value = false; }
}
async function createDraft() {
  creating.value = true; error.value = "";
  try {
    const tags = knowledgeText.value.split(/[,，、]/).map((item) => item.trim()).filter(Boolean);
    const data = await apiPost("/api/teacher/ai/assignment-draft", { ...intent.value, class_id: Number(classId.value), knowledge_tags: tags, allow_ai_supplement: allowSupplement.value, note: "由一句话组卷生成，发布前须教师逐题审核。" });
    emit("created", data);
  } catch (exception) { error.value = exception.message || "作业草稿生成失败。"; }
  finally { creating.value = false; }
}
</script>

<style scoped>
.paper-draft-card{display:grid;gap:14px;margin-bottom:16px}.paper-draft-card>header,.intent-editor>header{display:flex;align-items:center;justify-content:space-between;gap:12px}.paper-draft-card>header>div{display:grid;gap:4px}.paper-draft-card>header small{color:#287381;font-size:11px;font-weight:800;letter-spacing:.08em}.paper-draft-card>header strong{color:#33302b;font-size:18px}.paper-draft-card>header>span,.intent-editor small{color:#777067;font-size:11px}.paper-command{display:grid;grid-template-columns:220px 1fr auto;gap:8px}.paper-command select,.paper-command input,.intent-editor input{min-width:0;min-height:40px;padding:0 11px;color:#33302b;border:1px solid #ded7cb;background:#fff}.paper-command button,.create-draft{min-height:40px;padding:0 15px;color:#fff;border:1px solid #2e7d8c;background:#2e7d8c;font-weight:850}.intent-editor{display:grid;gap:13px;padding:15px;border:1px solid #ded7cb;background:#faf7f0}.intent-editor>div:not(.difficulty-mix){display:grid;grid-template-columns:2fr .6fr .8fr 1.6fr;gap:9px}.intent-editor label{display:grid;gap:6px;color:#5d574f;font-size:11px}.intent-editor fieldset{display:flex;flex-wrap:wrap;gap:13px;margin:0;padding:10px 12px;border:1px solid #ded7cb}.intent-editor fieldset label,.supplement-switch{display:flex;align-items:center;gap:6px}.intent-editor fieldset input,.supplement-switch input{min-height:auto}.difficulty-mix{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.create-draft{justify-self:end}.paper-message{margin:0;color:#5d574f}.paper-message.is-error{color:#ad5046}@media(max-width:820px){.paper-command{grid-template-columns:1fr}.intent-editor>div:not(.difficulty-mix){grid-template-columns:1fr 1fr}}@media(max-width:520px){.intent-editor>div:not(.difficulty-mix),.difficulty-mix{grid-template-columns:1fr}.paper-draft-card>header{align-items:flex-start;flex-direction:column}.create-draft{width:100%}}
</style>
