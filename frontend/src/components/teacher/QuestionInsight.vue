<template>
  <section class="question-insight">
    <button type="button" :aria-expanded="open" @click="toggle">{{ open ? "收起学情" : "查看学情与沉淀经验" }}</button>
    <div v-if="open">
      <p v-if="loading">正在聚合本人班级的正式作答…</p>
      <p v-else-if="error" class="is-error">{{ error }}</p>
      <template v-else-if="insight">
        <dl><div><dt>作答</dt><dd>{{ insight.attempts }}</dd></div><div><dt>正确率</dt><dd>{{ insight.correct_rate }}%</dd></div><div><dt>平均用时</dt><dd>{{ insight.average_seconds }} 秒</dd></div></dl>
        <p :class="{ warning: insight.concept_blind_spot }">{{ insight.insight }}</p>
        <div class="insight-tags"><span v-for="item in insight.wrong_options" :key="item.option">错误选项 {{ item.option }} · {{ item.count }}</span><span v-for="item in insight.mistake_distribution" :key="item.reason">{{ item.reason }} · {{ item.count }}</span></div>
      </template>
      <form @submit.prevent="saveExperience">
        <label><span>教给小逻的经验</span><textarea v-model.trim="experience" maxlength="4000" placeholder="例如：学生常把充分条件和必要条件混淆，讲解时先用反例区分。"></textarea></label>
        <button type="submit" :disabled="saving || experience.length < 2">{{ saving ? "保存中…" : "保存为教学经验" }}</button>
        <small v-if="saved">已保存。此后讲解本题时会自动带上这条经验。</small>
      </form>
    </div>
  </section>
</template>

<script setup>
import { ref } from "vue";
import { apiGet, apiPost } from "../../api/client";
const props = defineProps({ question: { type: Object, required: true } });
const open = ref(false), loading = ref(false), saving = ref(false), saved = ref(false), error = ref(""), insight = ref(null), experience = ref("");
async function toggle() { open.value = !open.value; if (!open.value || insight.value) return; loading.value = true; error.value = ""; try { insight.value = await apiGet(`/api/teacher/questions/${props.question.id}/insight`); } catch (exception) { error.value = exception.message; } finally { loading.value = false; } }
async function saveExperience() { saving.value = true; saved.value = false; error.value = ""; try { await apiPost("/api/teacher/experiences", { question_id: props.question.id, knowledge_tag: props.question.knowledge_tag, experience_text: experience.value }); experience.value = ""; saved.value = true; } catch (exception) { error.value = exception.message; } finally { saving.value = false; } }
</script>

<style scoped>
.question-insight{border-top:1px solid #e6dfd4}.question-insight>button{min-height:34px;padding:0;color:#287381;background:transparent;font-size:11px;font-weight:850}.question-insight>div{display:grid;gap:10px;padding:12px;background:#faf7f0}.question-insight p{margin:0;color:#6a645b;font-size:11px;line-height:1.6}.question-insight p.warning{padding:8px;border-left:3px solid #b17d1e;background:#fbf4e6}.question-insight p.is-error{color:#ad5046}.question-insight dl{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;margin:0;background:#ded7cb}.question-insight dl>div{display:grid;gap:3px;padding:8px;background:#fff}.question-insight dt{color:#817a70;font-size:9px}.question-insight dd{margin:0;font-weight:900}.insight-tags{display:flex;flex-wrap:wrap;gap:6px}.insight-tags span{padding:5px 7px;background:#fff;font-size:10px}.question-insight form{display:grid;grid-template-columns:1fr auto;align-items:end;gap:8px}.question-insight form label{display:grid;gap:5px}.question-insight textarea{min-height:66px;padding:8px;resize:vertical;border:1px solid #ded7cb;background:#fff}.question-insight form button{min-height:36px;padding:0 10px;color:#fff;background:#2e7d8c;font-weight:850}.question-insight form small{grid-column:1/-1;color:#347a56}@media(max-width:560px){.question-insight form{grid-template-columns:1fr}}
</style>
