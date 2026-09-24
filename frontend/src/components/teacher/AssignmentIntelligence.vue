<template>
  <section class="assignment-intelligence teacher-panel">
    <header>
      <div><small>统计可审计 · AI 只产草稿</small><strong>逐题透视与智能讲评</strong></div>
      <div><button type="button" :disabled="commentaryLoading" @click="generateCommentary">{{ commentaryLoading ? "生成中…" : "✦ 生成讲评稿" }}</button><button type="button" :disabled="similarityLoading" @click="loadSimilarity">雷同提示</button></div>
    </header>
    <p v-if="error" class="intelligence-error">{{ error }}</p>
    <div v-if="loading" class="intelligence-loading">正在统计每题作答…</div>
    <div v-else-if="stats.length" class="question-stat-list">
      <article v-for="item in stats" :key="item.question_id">
        <b>{{ item.sort_order }}</b>
        <div><strong>{{ item.question_text }}</strong><small>{{ item.knowledge_tag }} · {{ item.answered_count }} 人作答 · 平均 {{ item.average_seconds }} 秒</small></div>
        <span :class="accuracyTone(item.correct_rate)">{{ item.correct_rate }}%</span>
        <details><summary>错误选项与错因</summary><p v-if="!item.wrong_options.length && !item.mistake_distribution.length">暂无稳定错误分布。</p><div><em v-for="option in item.wrong_options" :key="option.option">选项 {{ option.option }} · {{ option.count }} 人</em><em v-for="reason in item.mistake_distribution" :key="reason.reason">{{ reason.reason }} · {{ reason.count }}</em></div></details>
      </article>
    </div>
    <p v-else-if="!loading" class="intelligence-empty">暂无已作答统计。</p>

    <section v-if="commentary" class="commentary-draft">
      <header><div><small>AI 辅助草稿 · 教师审阅后使用</small><strong>{{ commentary.title }}</strong></div></header>
      <div><section><h4>教学目标</h4><ol><li v-for="item in commentary.objectives" :key="item">{{ item }}</li></ol></section><section><h4>课堂流程</h4><ol><li v-for="item in commentary.teaching_flow" :key="item">{{ item }}</li></ol></section><section><h4>即时自测</h4><ol><li v-for="item in commentary.quick_checks" :key="item">{{ item }}</li></ol></section></div>
    </section>
    <section v-if="similarity" class="similarity-hints">
      <header><strong>文本相似提示</strong><small>只提供线索，不构成抄袭判定</small></header>
      <p v-if="!similarity.length">未发现达到提示阈值的长文本答案。</p>
      <article v-for="item in similarity" :key="`${item.assignment_question_id}-${item.students.join('-')}`"><span>{{ item.students.join(" / ") }}</span><b>{{ Math.round(item.similarity * 100) }}%</b><small>{{ item.notice }}</small></article>
    </section>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import { apiGet, apiPost } from "../../api/client";
const props = defineProps({ assignmentId: { type: Number, required: true } });
const loading = ref(true), commentaryLoading = ref(false), similarityLoading = ref(false), error = ref("");
const stats = ref([]), commentary = ref(null), similarity = ref(null);
function accuracyTone(value) { return value >= 80 ? "good" : value >= 60 ? "medium" : "weak"; }
async function load() { loading.value = true; error.value = ""; try { const data = await apiGet(`/api/teacher/assignments/${props.assignmentId}/question-stats`); stats.value = data.items || []; } catch (exception) { error.value = exception.message; } finally { loading.value = false; } }
async function generateCommentary() { commentaryLoading.value = true; error.value = ""; try { const data = await apiPost("/api/teacher/ai/assignment-commentary", { assignment_id: props.assignmentId }); commentary.value = data.draft; } catch (exception) { error.value = exception.message; } finally { commentaryLoading.value = false; } }
async function loadSimilarity() { similarityLoading.value = true; error.value = ""; try { const data = await apiGet(`/api/teacher/assignments/${props.assignmentId}/similarity-hints`); similarity.value = data.hints || []; } catch (exception) { error.value = exception.message; } finally { similarityLoading.value = false; } }
watch(() => props.assignmentId, load); onMounted(load);
</script>

<style scoped>
.assignment-intelligence{display:grid;gap:14px;margin-top:16px}.assignment-intelligence>header,.commentary-draft>header,.similarity-hints>header{display:flex;align-items:center;justify-content:space-between;gap:12px}.assignment-intelligence>header>div:first-child{display:grid;gap:4px}.assignment-intelligence>header small{color:#777067;font-size:11px}.assignment-intelligence>header>div:last-child{display:flex;gap:7px}.assignment-intelligence button{min-height:35px;padding:0 11px;color:#287381;border:1px solid rgba(46,125,140,.32);background:#fff;font-weight:800}.question-stat-list{display:grid;gap:1px;border:1px solid #ded7cb;background:#ded7cb}.question-stat-list>article{display:grid;grid-template-columns:30px minmax(0,1fr) 56px;align-items:center;gap:10px;padding:12px;background:#fff}.question-stat-list>article>b{display:grid;place-items:center;width:28px;height:28px;color:#fff;border-radius:50%;background:#706b62}.question-stat-list>article>div{display:grid;min-width:0;gap:4px}.question-stat-list>article>div>strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.question-stat-list>article small{color:#777067;font-size:10px}.question-stat-list>article>span{text-align:right;font-weight:900}.question-stat-list>article>span.good{color:#347a56}.question-stat-list>article>span.medium{color:#8f6b16}.question-stat-list>article>span.weak{color:#ad5046}.question-stat-list details{grid-column:2/-1}.question-stat-list summary{color:#287381;font-size:11px;cursor:pointer}.question-stat-list details div{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.question-stat-list details em{padding:5px 7px;color:#615b53;background:#f6f2e9;font-size:10px}.commentary-draft,.similarity-hints{display:grid;gap:12px;padding:14px;border-left:3px solid #2e7d8c;background:#edf6f5}.commentary-draft>div{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.commentary-draft section{padding:10px;background:#fff}.commentary-draft h4{margin:0 0 7px}.commentary-draft ol{margin:0;padding-left:18px;color:#575149;font-size:11px;line-height:1.65}.similarity-hints{border-left-color:#b17d1e;background:#fbf4e6}.similarity-hints article{display:grid;grid-template-columns:1fr auto;gap:4px;padding:9px;background:#fff}.similarity-hints article small{grid-column:1/-1}.intelligence-loading,.intelligence-empty{padding:20px;color:#817a70;text-align:center}.intelligence-error{margin:0;color:#ad5046}@media(max-width:700px){.assignment-intelligence>header{align-items:flex-start;flex-direction:column}.commentary-draft>div{grid-template-columns:1fr}}
</style>
