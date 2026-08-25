<template>
  <article class="ai-card" :class="`type-${card.type || 'insight'}`">
    <header>
      <span class="ai-card-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24"><path d="M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Z" /><path d="M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z" /></svg>
      </span>
      <div><small>{{ typeLabel }}</small><h3>{{ card.title || "小逻建议" }}</h3></div>
      <button v-if="hasDetails" type="button" :aria-expanded="!collapsed" @click="collapsed = !collapsed">{{ collapsed ? "展开" : "收起" }}</button>
    </header>
    <p v-if="card.summary || card.suggestion">{{ card.summary || card.suggestion }}</p>
    <dl v-if="metrics.length">
      <div v-for="item in metrics" :key="`${item.label}-${item.value}`"><dt>{{ item.label }}</dt><dd>{{ item.value }}</dd></div>
    </dl>
    <div v-if="!collapsed" class="ai-card-details">
      <div v-if="mistakes.length" class="ai-card-tags"><span v-for="item in mistakes" :key="item.label">{{ item.label }} · {{ item.count }}</span></div>
      <ul v-if="details.length"><li v-for="item in details" :key="`${item.label}-${item.value}`"><strong>{{ item.label }}</strong><span>{{ item.value }}</span></li></ul>
      <ol v-if="weeklyPlan.length"><li v-for="item in weeklyPlan.slice(0, 4)" :key="item.day"><b>{{ item.day }}</b><span>{{ item.task }}</span><small>{{ item.minutes }} 分钟</small></li></ol>
    </div>
    <footer v-if="actions.length">
      <button v-for="action in actions" :key="`${action.label}-${action.target}`" type="button" @click="$emit('action', action)">{{ action.label }}</button>
    </footer>
  </article>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({ card: { type: Object, required: true } });
defineEmits(["action"]);
const collapsed = ref(false);
const typeLabel = computed(() => ({ review: "AI 复盘", assessment: "首测分析", reason: "错因分析", plan: "学习计划", insight: "AI 解读", suggestion: "组卷建议" })[props.card.type] || "小逻分析");
const metrics = computed(() => props.card.metrics || []);
const mistakes = computed(() => props.card.mistakes || []);
const details = computed(() => props.card.details || []);
const weeklyPlan = computed(() => props.card.weekly_plan || []);
const actions = computed(() => props.card.actions || []);
const hasDetails = computed(() => mistakes.value.length || details.value.length || weeklyPlan.value.length);
</script>

<style scoped>
.ai-card { width:100%; padding:16px; border:1px solid rgba(46, 125, 140, 0.28); border-left:3px solid #2e7d8c; border-radius:14px; background:#ffffff; box-shadow:0 18px 44px rgba(90, 75, 50, 0.096); }
.ai-card > header { display:grid; grid-template-columns:34px minmax(0,1fr) auto; gap:10px; align-items:center; }
.ai-card-mark { width:34px; height:34px; display:grid; place-items:center; border-radius:10px; color:#287381; background:rgba(46, 125, 140, 0.1); }
.ai-card-mark svg { width:20px; fill:none; stroke:currentColor; stroke-width:1.7; }
.ai-card h3,.ai-card p { margin:0; }
.ai-card h3 { margin-top:2px; color:#33302b; font-size:16px; line-height:1.35; }
.ai-card header small { color:#287381; font-size:11px; font-weight:800; }
.ai-card header button { color:#706b62; background:transparent; font-size:11px; }
.ai-card > p { margin-top:12px; color:#33302b; font-size:13px; line-height:1.65; }
.ai-card dl { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:7px; margin:13px 0 0; }
.ai-card dl div { min-width:0; padding:9px; border:1px solid rgba(100,90,70,.12); border-radius:9px; background:rgba(46,125,140,.04); }
.ai-card dt { color:#706b62; font-size:10px; }
.ai-card dd { margin:4px 0 0; color:#33302b; font-size:13px; font-weight:850; overflow-wrap:anywhere; }
.ai-card-details { display:grid; gap:9px; margin-top:12px; }
.ai-card-tags { display:flex; flex-wrap:wrap; gap:6px; }
.ai-card-tags span { padding:5px 8px; border-radius:999px; color:#8f5f0e; background:rgba(176, 125, 30, 0.1); font-size:11px; }
.ai-card ul,.ai-card ol { display:grid; gap:6px; margin:0; padding:0; list-style:none; }
.ai-card li { display:grid; grid-template-columns:auto minmax(0,1fr) auto; gap:8px; padding:8px 9px; border-left:2px solid rgba(46, 125, 140, 0.35); background:rgba(46,125,140,.04); font-size:11px; }
.ai-card li span { color:#33302b; overflow-wrap:anywhere; }
.ai-card li small { color:#706b62; }
.ai-card footer { display:flex; flex-wrap:wrap; gap:8px; margin-top:13px; }
.ai-card footer button { min-height:36px; padding:0 12px; border:1px solid rgba(46, 125, 140, 0.3); border-radius:9px; color:#ffffff; background:#2e7d8c; font-size:12px; font-weight:850; }
.ai-card footer button + button { color:#33302b; background:transparent; }
@media (max-width:420px) { .ai-card { padding:13px; } .ai-card dl { grid-template-columns:1fr; } .ai-card li { grid-template-columns:45px minmax(0,1fr); } .ai-card li small { grid-column:2; } }
</style>
