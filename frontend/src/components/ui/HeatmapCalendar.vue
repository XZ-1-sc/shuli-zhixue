<template>
  <article class="learning-insight-card">
    <header>
      <div><small>最近 12 周</small><h2>学习热力与掌握趋势</h2></div>
      <span>{{ activeDays }} 天有学习记录</span>
    </header>
    <div class="insight-layout">
      <section>
        <h3>学习热力</h3>
        <div class="heatmap-grid" role="img" :aria-label="`最近十二周共有 ${activeDays} 天学习`">
          <i v-for="item in calendar" :key="item.date" :class="intensity(item.attempts)" :title="`${item.date}：${item.attempts} 次作答，${item.study_minutes} 分钟`"></i>
        </div>
        <div class="heatmap-legend"><span>少</span><i></i><i class="level-1"></i><i class="level-2"></i><i class="level-3"></i><i class="level-4"></i><span>多</span></div>
      </section>
      <section>
        <h3>近 30 天掌握度</h3>
        <svg v-if="trend.length" viewBox="0 0 600 120" role="img" :aria-label="trendDescription" preserveAspectRatio="none">
          <path d="M0 30H600M0 60H600M0 90H600" class="grid-line" />
          <polyline :points="trendPoints" class="trend-line" vector-effect="non-scaling-stroke" />
          <circle v-for="point in plottedTrend" :key="point.date" :cx="point.x" :cy="point.y" r="4"><title>{{ point.date }}：{{ point.mastery }}%</title></circle>
        </svg>
        <div v-else class="trend-empty">完成已评分练习后，这里会显示掌握度变化。</div>
      </section>
    </div>
  </article>
</template>

<script setup>
import { computed } from "vue";
const props = defineProps({ calendar: { type: Array, default: () => [] }, trend: { type: Array, default: () => [] } });
const activeDays = computed(() => props.calendar.filter((item) => Number(item.attempts) > 0).length);
const plottedTrend = computed(() => props.trend.map((item, index) => ({ ...item, x: props.trend.length <= 1 ? 300 : Math.round(index / (props.trend.length - 1) * 590 + 5), y: Math.round(110 - Math.max(0, Math.min(100, Number(item.mastery || 0))) * 1) })));
const trendPoints = computed(() => plottedTrend.value.map((item) => `${item.x},${item.y}`).join(" "));
const trendDescription = computed(() => { if (!props.trend.length) return "暂无掌握度趋势"; const first = props.trend[0].mastery; const last = props.trend.at(-1).mastery; return `掌握度从 ${first}% 变化到 ${last}%`; });
function intensity(value) { const count = Number(value || 0); return count >= 12 ? "level-4" : count >= 7 ? "level-3" : count >= 3 ? "level-2" : count >= 1 ? "level-1" : ""; }
</script>

<style scoped>
.learning-insight-card{padding:20px;border:1px solid rgba(46, 125, 140, 0.15);border-radius:16px;background:#ffffff}.learning-insight-card>header{display:flex;justify-content:space-between;gap:16px;align-items:end}.learning-insight-card small{color:#287381}.learning-insight-card h2{margin:4px 0 0;font-size:19px}.learning-insight-card>header>span{color:#706b62;font-size:12px}.insight-layout{display:grid;grid-template-columns:minmax(260px,.75fr) minmax(320px,1.25fr);gap:22px;margin-top:18px}.insight-layout h3{margin:0 0 10px;color:#33302b;font-size:12px}.heatmap-grid{display:grid;grid-template-rows:repeat(7,11px);grid-auto-flow:column;grid-auto-columns:11px;gap:4px;overflow:hidden}.heatmap-grid i,.heatmap-legend i{border-radius:3px;background:rgba(100, 90, 70, 0.09)}.heatmap-grid .level-1,.heatmap-legend .level-1{background:#d5e4df}.heatmap-grid .level-2,.heatmap-legend .level-2{background:#aacdc6}.heatmap-grid .level-3,.heatmap-legend .level-3{background:#6fa89f}.heatmap-grid .level-4,.heatmap-legend .level-4{background:#2e7d8c}.heatmap-legend{display:flex;justify-content:flex-end;align-items:center;gap:4px;margin-top:9px;color:#706b62;font-size:10px}.heatmap-legend i{width:10px;height:10px}.insight-layout svg{width:100%;height:112px;overflow:visible}.grid-line{fill:none;stroke:rgba(46, 125, 140, 0.1);stroke-width:1}.trend-line{fill:none;stroke:#3f8f66;stroke-width:3}.insight-layout circle{fill:#3f8f66}.trend-empty{height:112px;display:grid;place-items:center;color:#706b62;border:1px dashed rgba(46, 125, 140, 0.16);border-radius:10px;font-size:12px}@media(max-width:760px){.insight-layout{grid-template-columns:1fr}.learning-insight-card{padding:16px}.heatmap-grid{grid-auto-columns:10px;grid-template-rows:repeat(7,10px);gap:3px}}
</style>
