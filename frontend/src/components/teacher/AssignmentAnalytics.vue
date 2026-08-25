<template>
  <section class="teacher-panel teacher-analytics">
    <header>
      <div><strong>{{ scope === "class" ? "班级数据分析" : "作业数据分析" }}</strong><small>数据来自真实作答，AI 叙事分析请在小逻查看</small></div>
      <button type="button" :disabled="loading" @click="load">{{ loading ? "统计中…" : "刷新数据" }}</button>
    </header>
    <p v-if="error" class="teacher-form-message is-error">{{ error }}</p>
    <div v-if="loading && !loaded" class="analytics-loading"><i v-for="item in 4" :key="item"></i></div>
    <template v-else>
      <div class="analytics-grid">
        <article><h3>正确率分布</h3><div ref="distributionEl" class="analytics-chart"></div></article>
        <article><h3>知识点掌握度</h3><div ref="masteryEl" class="analytics-chart"></div></article>
        <article><h3>错因分布</h3><div ref="reasonEl" class="analytics-chart"></div></article>
        <article><h3>学生个体对比</h3><div ref="studentEl" class="analytics-chart analytics-students"></div></article>
      </div>
      <div v-if="analytics.students.length" class="teacher-table-wrap analytics-student-table">
        <table>
          <thead><tr><th>学生</th><th>正确率</th><th>作答</th><th>薄弱知识点</th><th>最近学习</th><th>操作</th></tr></thead>
          <tbody><tr v-for="student in analytics.students" :key="student.student_id"><td><strong>{{ student.nickname }}</strong><small>@{{ student.username }}</small></td><td>{{ student.accuracy }}%</td><td>{{ student.attempts }}</td><td>{{ student.weak_knowledge.join("、") || "暂无数据" }}</td><td>{{ formatTime(student.last_active) }}</td><td><RouterLink :to="`/teacher/students/${student.student_id}`">查看学情</RouterLink></td></tr></tbody>
        </table>
      </div>
      <div v-else class="teacher-inline-empty">当前范围还没有学生作答数据。</div>
    </template>
  </section>
</template>

<script setup>
import { BarChart, PieChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { init, use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRouter } from "vue-router";

import { apiGet } from "../../api/client";

use([BarChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

const props = defineProps({ scope: { type: String, required: true }, scopeId: { type: Number, required: true } });
const router = useRouter();
const loading = ref(false);
const loaded = ref(false);
const error = ref("");
const analytics = reactive({ accuracy_distribution: [], knowledge_mastery: [], reason_distribution: [], students: [] });
const distributionEl = ref(null);
const masteryEl = ref(null);
const reasonEl = ref(null);
const studentEl = ref(null);
const charts = [];
let resizeObserver = null;

function chartFor(element) {
  if (!element) return null;
  const chart = init(element);
  charts.push(chart);
  return chart;
}

function baseAxis() {
  return { axisLine: { lineStyle: { color: "#9b9386" } }, axisLabel: { color: "#7d786e", fontSize: 10 }, splitLine: { lineStyle: { color: "rgba(46, 125, 140, 0.1)" } } };
}

function renderCharts() {
  charts.splice(0).forEach((chart) => chart.dispose());
  const distribution = chartFor(distributionEl.value);
  distribution?.setOption({ tooltip: { trigger: "axis" }, grid: { left: 38, right: 12, top: 16, bottom: 32 }, xAxis: { ...baseAxis(), type: "category", data: analytics.accuracy_distribution.map((item) => item.bucket) }, yAxis: { ...baseAxis(), type: "value", minInterval: 1 }, series: [{ type: "bar", data: analytics.accuracy_distribution.map((item) => item.count), itemStyle: { color: "#2e7d8c", borderRadius: [5, 5, 0, 0] } }] });
  const mastery = chartFor(masteryEl.value);
  const masteryRows = analytics.knowledge_mastery.slice(0, 10).reverse();
  mastery?.setOption({ tooltip: { trigger: "axis" }, grid: { left: 86, right: 22, top: 12, bottom: 24 }, xAxis: { ...baseAxis(), type: "value", max: 100 }, yAxis: { ...baseAxis(), type: "category", data: masteryRows.map((item) => item.knowledge_tag), axisLabel: { color: "#7d786e", width: 76, overflow: "truncate" } }, series: [{ type: "bar", data: masteryRows.map((item) => item.accuracy), itemStyle: { color: (params) => params.value < 60 ? "#b07d1e" : params.value < 80 ? "#b07d1e" : "#3f8f66", borderRadius: [0, 5, 5, 0] } }] });
  const reason = chartFor(reasonEl.value);
  reason?.setOption({ tooltip: { trigger: "item" }, legend: { bottom: 0, textStyle: { color: "#7d786e", fontSize: 10 } }, series: [{ type: "pie", radius: ["38%", "67%"], center: ["50%", "43%"], label: { color: "#33302b", fontSize: 10 }, data: analytics.reason_distribution.slice(0, 8).map((item) => ({ name: item.reason, value: item.count })) }] });
  const student = chartFor(studentEl.value);
  const studentRows = [...analytics.students].filter((item) => item.attempts > 0).sort((a, b) => a.accuracy - b.accuracy);
  student?.setOption({ tooltip: { trigger: "axis" }, grid: { left: 78, right: 22, top: 12, bottom: 24 }, xAxis: { ...baseAxis(), type: "value", max: 100 }, yAxis: { ...baseAxis(), type: "category", data: studentRows.map((item) => item.nickname), axisLabel: { color: "#7d786e", width: 68, overflow: "truncate" } }, series: [{ type: "bar", data: studentRows.map((item) => ({ value: item.accuracy, studentId: item.student_id })), itemStyle: { color: "#2e7d8c", borderRadius: [0, 5, 5, 0] } }] });
  student?.on("click", (params) => { if (params.data?.studentId) router.push(`/teacher/students/${params.data.studentId}`); });
  resizeObserver?.disconnect();
  resizeObserver = new ResizeObserver(() => charts.forEach((chart) => chart.resize()));
  [distributionEl.value, masteryEl.value, reasonEl.value, studentEl.value].filter(Boolean).forEach((element) => resizeObserver.observe(element));
}

async function load() {
  if (!props.scopeId) return;
  loading.value = true;
  error.value = "";
  try {
    const endpoint = props.scope === "class" ? `/api/teacher/classes/${props.scopeId}/analytics` : `/api/teacher/assignments/${props.scopeId}/analytics`;
    const data = await apiGet(endpoint);
    analytics.accuracy_distribution = data.accuracy_distribution || [];
    analytics.knowledge_mastery = data.knowledge_mastery || [];
    analytics.reason_distribution = data.reason_distribution || [];
    analytics.students = data.students || [];
    loaded.value = true;
    await nextTick();
    renderCharts();
  } catch (exception) { error.value = exception.message || "分析数据加载失败。"; }
  finally { loading.value = false; }
}

function formatTime(value) { return value ? new Date(value).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "暂无"; }
watch(() => [props.scope, props.scopeId], load);
onMounted(load);
onBeforeUnmount(() => { resizeObserver?.disconnect(); charts.splice(0).forEach((chart) => chart.dispose()); });
</script>

<style scoped>
.teacher-analytics{margin-top:16px}.teacher-analytics>header>button{min-height:34px;padding:0 12px;border:1px solid rgba(46, 125, 140, 0.24);color:#287381;background:transparent}.analytics-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;padding:16px}.analytics-grid article{min-width:0;padding:14px;border:1px solid rgba(46, 125, 140, 0.12);background: rgba(255, 255, 255, 0.82)}.analytics-grid h3{margin:0 0 6px;color:#33302b;font-size:13px}.analytics-chart{width:100%;height:250px}.analytics-students{cursor:pointer}.analytics-loading{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;padding:16px}.analytics-loading i{height:270px;background:rgba(46, 125, 140, 0.06);animation:pulse 1.2s infinite alternate}.analytics-student-table{margin:0 16px 16px}.analytics-student-table td:first-child{display:grid}.analytics-student-table td small{color:#706b62}.analytics-student-table a{color:#287381}@keyframes pulse{to{opacity:.45}}@media(max-width:760px){.analytics-grid,.analytics-loading{grid-template-columns:1fr}.analytics-chart{height:230px}.analytics-student-table{overflow-x:auto}.analytics-student-table table{min-width:680px}}
</style>
