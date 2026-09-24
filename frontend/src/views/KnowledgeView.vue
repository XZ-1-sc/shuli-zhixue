<template>
  <section class="student-page knowledge-v2">
    <header class="knowledge-v2-head">
      <div><small>课程关系网络</small><h1>知识图谱与错题复盘</h1><p>从课程全景进入单门课程，查看知识点、先修关系与真实掌握度。</p></div>
      <span>{{ visibleNodes.length }} 个节点</span>
    </header>

    <section class="knowledge-v2-shell">
      <aside class="knowledge-v2-side">
        <strong>我的课程</strong>
        <button :class="{ active: !selectedCourse }" type="button" @click="selectCourse('')"><span>◎</span>课程全景</button>
        <button v-for="course in orderedCourses" :key="course" :class="{ active: selectedCourse === course }" type="button" @click="selectCourse(course)"><span>{{ course === primaryCourse ? '★' : '◇' }}</span>{{ course }}</button>
        <RouterLink to="/settings">管理课程</RouterLink><hr />
        <strong>掌握度</strong>
        <p><i class="good"></i>良好（≥80%）</p><p><i class="medium"></i>中等（50%—79%）</p><p><i class="weak"></i>薄弱（＜50%）</p><p><i></i>尚未测评</p>
      </aside>

      <article class="knowledge-v2-board">
        <div class="knowledge-v2-toolbar">
          <label><span>搜索知识点</span><input v-model="searchText" placeholder="输入名称或说明" /></label>
          <label class="relation-switch"><input v-model="showPrerequisite" type="checkbox" />先修关系</label>
          <label class="relation-switch"><input v-model="showRelated" type="checkbox" />关联关系</label>
          <button type="button" @click="toggleDepth">{{ graphDepth >= 3 ? "收起知识点" : "展开知识点" }}</button>
          <button type="button" @click="zoom(1.2)">＋</button><button type="button" @click="zoom(0.82)">－</button><button type="button" @click="resetGraph">重置</button>
        </div>
        <div v-if="loading" class="knowledge-v2-empty">正在加载课程关系…</div>
        <div v-else-if="!visibleNodes.length" class="knowledge-v2-empty"><strong>没有匹配节点</strong><p>清空搜索词或切换课程后再试。</p></div>
        <div v-else ref="graphEl" class="knowledge-v2-canvas graph-canvas" style="padding: 0"></div>
        <footer><span>实线：包含</span><span>箭头：先修</span><span>虚线：关联</span><em>拖动节点或滚轮缩放</em></footer>
      </article>

      <aside class="knowledge-v2-detail">
        <template v-if="selectedNode">
          <small>{{ selectedNode.category === 'course' ? '课程' : selectedNode.category === 'leaf' ? '细分知识点' : '知识点' }}</small>
          <h2>{{ selectedNode.name }}</h2><p>{{ selectedNode.description || '暂无补充说明。' }}</p>
          <dl><div><dt>所属课程</dt><dd>{{ selectedNode.course || selectedNode.name }}</dd></div><div><dt>掌握状态</dt><dd :class="selectedNode.mastery_status">{{ masteryText(selectedNode) }}</dd></div></dl>
          <RouterLink :to="practiceLink(selectedNode)">按此知识点练习</RouterLink>
          <button type="button" @click="askXiaoluo(selectedNode)">让小逻讲关系</button>
        </template>
        <template v-else><small>节点详情</small><h2>选择一个节点</h2><p>点击图中的课程或知识点，这里会显示掌握状态与快捷操作。</p></template>
      </aside>
    </section>

    <section class="knowledge-v2-lower">
      <article><header><h2>薄弱知识点</h2><RouterLink to="/review">完整报告</RouterLink></header><div v-if="weakPoints.length" class="knowledge-v2-list"><RouterLink v-for="item in weakPoints" :key="`${item.course}-${item.fine_tag}`" :to="`/practice?course=${item.course}&knowledge_tag=${item.knowledge_tag}&limit=10`"><span>{{ item.course }}</span><strong>{{ item.fine_tag || item.knowledge_tag }}</strong><em>{{ item.score }}%</em></RouterLink></div><p v-else>完成练习后，这里会根据真实作答显示薄弱点。</p></article>
      <article><header><h2>最近错题</h2><RouterLink to="/review">全部错题</RouterLink></header><div v-if="wrongItems.length" class="knowledge-v2-list"><RouterLink v-for="item in wrongItems" :key="item.record_id" :to="`/practice?mode=wrong_book&course=${item.course}&knowledge_tag=${item.knowledge_tag}&limit=10`"><span>{{ item.course }}</span><strong>{{ trim(item.question_text) }}</strong><em>再练</em></RouterLink></div><p v-else>当前没有错题记录，继续保持。</p></article>
    </section>
  </section>
</template>

<script setup>
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { apiGet } from "../api/client";
import { useUserStore } from "../stores/user";

const user = useUserStore();
const graphEl = ref(null), graphData = ref({ nodes: [], links: [] }), loading = ref(true);
const selectedCourse = ref(""), selectedNode = ref(null), searchText = ref("");
const showPrerequisite = ref(true), showRelated = ref(true), graphZoom = ref(1);
const courses = ref([]), primaryCourse = ref(""), weakPoints = ref([]), wrongItems = ref([]);
const graphCourses = ref([]), graphDepth = ref(2);
let chart;
let graphObserver;
const resizeGraph = () => chart?.resize();

const orderedCourses = computed(() => graphCourses.value.length ? graphCourses.value : [...new Set([...(courses.value || []), ...(graphData.value.nodes || []).filter(n => n.category === "course").map(n => n.name)])]);
const visibleNodes = computed(() => { const keyword = searchText.value.trim().toLowerCase(); return (graphData.value.nodes || []).filter(node => !keyword || [node.name, node.course, node.description].some(value => String(value || "").toLowerCase().includes(keyword))); });
const visibleLinks = computed(() => { const ids = new Set(visibleNodes.value.map(node => node.id)); return (graphData.value.links || []).filter(link => ids.has(link.source) && ids.has(link.target) && (link.relation !== "prerequisite" || showPrerequisite.value) && (link.relation !== "related" || showRelated.value)); });

function color(node) { return node.mastery_status === "good" ? "#4d8b68" : node.mastery_status === "medium" ? "#317f8d" : node.mastery_status === "weak" ? "#ba7c24" : node.category === "course" ? "#2e6f79" : "#8b887f"; }
function masteryText(node) { return node.mastery_status === "good" ? `良好 · ${node.mastery}%` : node.mastery_status === "medium" ? `中等 · ${node.mastery}%` : node.mastery_status === "weak" ? `薄弱 · ${node.mastery}%` : "尚未测评"; }
function practiceLink(node) { const course = node.course || node.name; const tag = node.category === "course" ? "" : node.name; return `/practice?course=${encodeURIComponent(course)}&knowledge_tag=${encodeURIComponent(tag)}&limit=10`; }
function trim(text) { return String(text || "").replace(/\s+/g, " ").slice(0, 46); }

function render() {
  if (!graphEl.value || !visibleNodes.value.length) return;
  if (!chart) {
    chart = echarts.init(graphEl.value);
    chart.on("click", event => { if (event.dataType === "node") selectedNode.value = event.data.raw; });
    graphObserver?.disconnect();
    graphObserver = new ResizeObserver(() => chart?.resize());
    graphObserver.observe(graphEl.value);
  }
  chart.setOption({ tooltip: { formatter: p => p.dataType === "edge" ? (p.data.note || p.data.label || "关系") : `${p.name}<br>${masteryText(p.data.raw)}` }, series: [{ type: "graph", layout: "force", roam: true, draggable: true, zoom: graphZoom.value, force: { repulsion: selectedCourse.value ? 230 : 360, edgeLength: selectedCourse.value ? [70, 135] : [130, 230], gravity: 0.08 }, edgeSymbol: ["none", "arrow"], edgeSymbolSize: [0, 7], label: { show: true, color: "#34312c", fontWeight: 700, width: 92, overflow: "truncate" }, emphasis: { focus: "adjacency", lineStyle: { width: 3 } }, data: visibleNodes.value.map(node => ({ id: node.id, name: node.name, raw: node, symbolSize: node.category === "course" ? 54 : node.category === "leaf" ? 24 : 38, itemStyle: { color: color(node), borderColor: "#fff", borderWidth: 2 }, label: { color: node.category === "course" ? "#fff" : "#34312c", position: node.category === "course" ? "inside" : "right" } })), links: visibleLinks.value.map(link => ({ ...link, lineStyle: { color: link.relation === "prerequisite" ? "#317f8d" : link.relation === "related" ? "#ba7c24" : "rgba(67,61,52,.25)", type: link.relation === "related" ? "dashed" : "solid", curveness: link.relation === "parent" ? 0 : 0.12 }, symbol: link.relation === "prerequisite" ? ["none", "arrow"] : ["none", "none"] })) }] }, true);
}

async function loadGraph() {
  loading.value = true;
  selectedNode.value = null;
  try {
    graphData.value = await apiGet("/api/knowledge-graph-v2", { course: selectedCourse.value, depth: graphDepth.value });
    graphCourses.value = graphData.value.graph_courses || [];
  } finally {
    loading.value = false;
    await nextTick();
    graphObserver?.disconnect();
    chart?.dispose();
    chart = null;
    render();
  }
}
function selectCourse(course) { selectedCourse.value = course; graphDepth.value = course ? 2 : 3; loadGraph(); }
function toggleDepth() { graphDepth.value = graphDepth.value >= 3 ? 2 : 3; if (selectedCourse.value) loadGraph(); }
function zoom(scale) { graphZoom.value = Math.max(.45, Math.min(2.2, graphZoom.value * scale)); render(); }
function resetGraph() { searchText.value = ""; graphZoom.value = 1; selectedNode.value = null; render(); }
function askXiaoluo(node) { window.dispatchEvent(new CustomEvent("xiaoluo:open", { detail: { prompt: `请讲清“${node.name}”与前置知识的关系，并给我一个练习顺序。`, context: { type: "diagnosis" }, autoSend: true } })); }
async function loadAll() { const graphPromise = loadGraph(); const [courseData, diagnosis, wrong] = await Promise.all([apiGet("/api/user-courses").catch(() => ({ courses: [], primary_course: "" })), apiGet("/api/diagnose").catch(() => ({ weak_points: [] })), apiGet("/api/review/wrong-questions", { limit: 3 }).catch(() => ({ items: [] }))]); courses.value = courseData.courses || []; primaryCourse.value = courseData.primary_course || ""; weakPoints.value = (diagnosis.weak_points || []).slice(0, 4); wrongItems.value = wrong.items || []; await graphPromise; }
watch([searchText, showPrerequisite, showRelated], () => nextTick(render));
watch(() => user.userId, loadAll);
onMounted(() => { loadAll(); window.addEventListener("resize", resizeGraph); });
onBeforeUnmount(() => { window.removeEventListener("resize", resizeGraph); graphObserver?.disconnect(); chart?.dispose(); });
</script>

<style scoped src="../styles/views/knowledge.css"></style>
