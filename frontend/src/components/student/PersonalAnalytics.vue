<template>
  <article class="glass-panel personal-analytics profile-wide">
    <header><div><small>仅统计正式练习</small><h2>我的错题画像</h2></div><span>{{ analytics.mastery_evidence?.formal || 0 }} 条证据</span></header>
    <p v-if="error" class="analytics-empty is-error">{{ error }}</p>
    <div v-else-if="loading" class="analytics-loading"><i v-for="item in 4" :key="item"></i></div>
    <template v-else>
      <div class="analytics-grid">
        <section class="trend-panel">
          <h3>近期正确率</h3>
          <svg v-if="trendPoints" viewBox="0 0 640 180" preserveAspectRatio="none" aria-label="近期正确率趋势">
            <path d="M20 25H620M20 90H620M20 155H620" fill="none" stroke="#e4ddd2" stroke-width="1" vector-effect="non-scaling-stroke" />
            <polyline :points="trendPoints" fill="none" stroke="#2e7d8c" stroke-width="3" vector-effect="non-scaling-stroke" />
          </svg>
          <p v-else class="analytics-empty">完成正式练习后显示趋势。</p>
          <div v-if="analytics.accuracy_trend?.length" class="trend-labels"><span>{{ analytics.accuracy_trend[0].date.slice(5) }}</span><span>{{ analytics.accuracy_trend.at(-1).date.slice(5) }}</span></div>
        </section>
        <section class="type-panel">
          <h3>题型表现</h3>
          <div v-if="analytics.by_type?.length" class="accuracy-list">
            <div v-for="item in analytics.by_type" :key="item.name"><span><b>{{ typeLabel(item.name) }}</b><small>{{ item.attempts }} 题</small></span><i><em :style="{ width: `${item.accuracy}%` }"></em></i><strong>{{ item.accuracy }}%</strong></div>
          </div>
          <p v-else class="analytics-empty">暂无题型统计。</p>
        </section>
        <section class="knowledge-panel">
          <h3>优先补强</h3>
          <div v-if="analytics.by_knowledge?.length" class="knowledge-list">
            <RouterLink v-for="item in analytics.by_knowledge.slice(0, 6)" :key="item.name" :to="{ path: '/practice', query: { knowledge_tag: item.name, limit: 8 } }"><span>{{ item.name }}</span><b>{{ item.accuracy }}%</b><small>{{ item.attempts }} 次 ›</small></RouterLink>
          </div>
          <p v-else class="analytics-empty">暂无知识点统计。</p>
        </section>
        <section class="reason-panel">
          <h3>主要错因</h3>
          <div v-if="analytics.mistake_distribution?.length" class="reason-cloud"><span v-for="item in analytics.mistake_distribution.slice(0, 8)" :key="item.reason">{{ item.reason }} <b>{{ item.count }}</b></span></div>
          <p v-else class="analytics-empty">暂无错因记录。</p>
        </section>
      </div>
      <section class="practice-calendar">
        <header><h3>近 90 天做题热力</h3><small>颜色越深，当日作答越多</small></header>
        <div class="calendar-grid"><i v-for="day in calendarDays" :key="day.date" :style="{ opacity: day.count ? Math.min(.3 + day.count / 10, 1) : .09 }" :title="`${day.date}：${day.count} 题`"></i></div>
      </section>
    </template>
  </article>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { apiGet } from "../../api/client";

const analytics = ref({ by_type: [], by_knowledge: [], mistake_distribution: [], accuracy_trend: [], practice_heatmap: [], mastery_evidence: {} });
const loading = ref(true);
const error = ref("");
const trendPoints = computed(() => {
  const rows = analytics.value.accuracy_trend || [];
  if (rows.length < 2) return "";
  return rows.map((item, index) => `${20 + index * 600 / (rows.length - 1)},${155 - Number(item.accuracy || 0) * 1.3}`).join(" ");
});
const calendarDays = computed(() => {
  const counts = new Map((analytics.value.practice_heatmap || []).map((item) => [item.date, Number(item.count || 0)]));
  const result = [];
  const today = new Date();
  for (let offset = 89; offset >= 0; offset -= 1) {
    const day = new Date(today); day.setDate(today.getDate() - offset);
    const key = day.toISOString().slice(0, 10);
    result.push({ date: key, count: counts.get(key) || 0 });
  }
  return result;
});
function typeLabel(value) { return ({ choice: "选择题", blank: "填空题", calculation: "计算题", proof: "证明题", comprehensive: "综合题" })[value] || value; }
onMounted(async () => { try { analytics.value = await apiGet("/api/profile/analytics"); } catch (exception) { error.value = exception.message || "个人学习画像加载失败。"; } finally { loading.value = false; } });
</script>

<style scoped>
.personal-analytics{display:grid;gap:18px}.personal-analytics>header,.practice-calendar>header{display:flex;align-items:end;justify-content:space-between;gap:10px}.personal-analytics header small{color:#817a70;font-size:11px}.personal-analytics h2,.personal-analytics h3{margin:0;color:#33302b}.personal-analytics>header>span{color:#287381;font-size:12px;font-weight:800}.analytics-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:1px;border:1px solid #ded7cb;background:#ded7cb}.analytics-grid>section{min-width:0;padding:16px;background:#fff}.trend-panel svg{width:100%;height:150px;margin-top:8px}.trend-labels{display:flex;justify-content:space-between;color:#898278;font-size:10px}.accuracy-list,.knowledge-list{display:grid;gap:9px;margin-top:13px}.accuracy-list>div{display:grid;grid-template-columns:minmax(86px,1fr) minmax(70px,1fr) 40px;align-items:center;gap:8px}.accuracy-list span{display:grid}.accuracy-list small{color:#898278;font-size:10px}.accuracy-list i{height:6px;background:#eee8df}.accuracy-list em{display:block;height:100%;background:#2e7d8c}.accuracy-list strong{font-size:11px;text-align:right}.knowledge-list>a{display:grid;grid-template-columns:1fr 42px 54px;gap:8px;padding:8px 0;color:#33302b;border-bottom:1px solid #eee8df;text-decoration:none;font-size:12px}.knowledge-list b{color:#ad5046;text-align:right}.knowledge-list small{color:#817a70;text-align:right}.reason-cloud{display:flex;flex-wrap:wrap;gap:7px;margin-top:13px}.reason-cloud span{padding:7px 9px;color:#5c564e;border:1px solid #ded7cb;background:#f8f4ec;font-size:11px}.reason-cloud b{color:#ad5046}.practice-calendar{display:grid;gap:10px}.calendar-grid{display:grid;grid-template-columns:repeat(30,minmax(5px,1fr));gap:4px}.calendar-grid i{aspect-ratio:1;background:#2e7d8c}.analytics-loading{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.analytics-loading i{height:110px;background:#eee9df}.analytics-empty{margin:15px 0 0;color:#898278;font-size:12px}.analytics-empty.is-error{color:#ad5046}@media(max-width:760px){.analytics-grid{grid-template-columns:1fr}.calendar-grid{grid-template-columns:repeat(18,minmax(5px,1fr))}}
</style>
