<template>
  <section class="student-page knowledge-ref-main">
      <section class="knowledge-map-area">
        <header>
          <h1>知识图谱与错题复盘</h1>
          <span>{{ coveredStages }} / 4</span>
        </header>
        <div class="knowledge-map-grid">
          <aside class="map-legend-panel">
            <label>显示关系 <input v-model="showLinks" type="checkbox" /></label>
            <div class="line-legend"><i></i>阶段到课程</div>
            <div class="line-legend dashed"><i></i>课程到知识点</div>
            <hr />
            <strong>掌握度</strong>
            <p><b class="green"></b>良好（80% 以上）</p>
            <p><b class="cyan"></b>中等（50% ~ 80%）</p>
            <p><b class="amber"></b>薄弱（50% 以下）</p>
            <p><b></b>未测评</p>
            <button type="button" @click="resetFilters">重置筛选</button>
          </aside>

          <article class="graph-board dynamic-graph-board">
            <div class="graph-toolbar">
              <select v-model="selectedStage" class="knowledge-select" @change="onStageChange">
                <option value="">全部阶段</option>
                <option v-for="stage in stages" :key="stage.stage_name" :value="stage.stage_name">{{ stage.stage_name }}</option>
              </select>
              <select v-model="selectedCourse" class="knowledge-select" @change="loadGraph">
                <option value="">全部课程</option>
                <option v-for="course in courseOptions" :key="course.course_name" :value="course.course_name">{{ course.course_name }}</option>
              </select>
              <span>{{ visibleNodes.length }} 个节点</span>
              <button type="button" @click="zoomGraph(1.18)">⊕ 放大</button>
              <button type="button" @click="zoomGraph(0.84)">⊖ 缩小</button>
              <button type="button" @click="resetGraph">↻ 重置</button>
            </div>

            <div v-if="!visibleNodes.length && !loadingGraph" class="knowledge-empty graph-empty-state">
              <strong>暂无可展示节点</strong>
              <p>换一个阶段或课程筛选试试。</p>
            </div>
            <div v-if="visibleNodes.length" ref="graphEl" class="graph-canvas"></div>
            <footer>ⓘ 点击节点查看课程、阶段和掌握状态。未做题前所有节点均为未测评。</footer>
          </article>
        </div>
      </section>

      <aside class="wrong-review-panel">
        <header>
          <h2>错题复盘</h2>
          <div>
            <RouterLink to="/review">全部错题</RouterLink>
            <RouterLink to="/practice?mode=wrong_book&limit=10">回炉练习</RouterLink>
          </div>
        </header>
        <div v-if="wrongItems.length" class="wrong-ref-list">
          <article v-for="(item, index) in wrongItems" :key="`${item.question_id}-${index}`">
            <span>{{ index + 1 }}</span>
            <div>
              <strong>{{ item.course }} > {{ item.knowledge_tag }}</strong>
              <p>{{ trimQuestion(item.question_text) }}</p>
              <em>错因：{{ mistakeLabel(item) }}</em>
              <RouterLink :to="`/practice?mode=wrong_book&knowledge_tag=${item.knowledge_tag}&limit=10`">再练一组</RouterLink>
            </div>
            <aside>
              <b>{{ item.is_correct ? "已订正" : "待复盘" }}</b>
              <RouterLink to="/review">查看解析</RouterLink>
            </aside>
          </article>
        </div>
        <div v-else class="knowledge-empty">
          <strong>暂无错题</strong>
          <p>做题并提交后，错误题目会进入这里。</p>
          <RouterLink to="/practice?mode=daily&limit=12">开始首测</RouterLink>
        </div>
      </aside>

      <section class="heatmap-panel">
        <h2>薄弱热力图 <span>ⓘ</span></h2>
        <div v-if="heatItems.length" class="heatmap-cards">
          <article v-for="weak in heatItems" :key="`${weak.course}-${weak.fine_tag}`">
            <strong>{{ weak.course }}</strong>
            <small>{{ weak.fine_tag || weak.knowledge_tag }} · 掌握度 {{ weak.score }}%</small>
            <div class="mini-heat">
              <i v-for="n in 35" :key="n" :class="heatClass(n, weak.score)"></i>
            </div>
          </article>
        </div>
        <div v-else class="knowledge-empty heat-empty">
          <strong>暂无薄弱热力图</strong>
          <p>完成首测后，系统会按知识点正确率生成热力图。</p>
        </div>
        <footer>
          <span><i class="green"></i>良好（≥80%）</span>
          <span><i class="cyan"></i>中等（50%~80%）</span>
          <span><i class="amber"></i>薄弱（＜50%）</span>
          <span><i></i>未测评</span>
        </footer>
      </section>

      <section class="recovery-card">
        <template v-if="topWeak">
          <h2>推荐：{{ topWeak.fine_tag || topWeak.knowledge_tag }} 10 题</h2>
          <p>基于你的薄弱点分析，建议优先巩固 {{ topWeak.course }} 的 {{ topWeak.knowledge_tag }}。</p>
          <div>
            <span>题量：10 题</span>
            <span>预计用时：15 分钟</span>
            <span>当前掌握度：{{ topWeak.score }}%</span>
          </div>
          <RouterLink :to="`/practice?stage=${topWeak.stage}&course=${topWeak.course}&knowledge_tag=${topWeak.knowledge_tag}&limit=10`">开始练习</RouterLink>
          <RouterLink to="/practice?mode=daily&limit=10">换一组</RouterLink>
        </template>
        <template v-else>
          <h2>等待首测结果</h2>
          <p>现在还没有个人薄弱点，不会展示假推荐。</p>
          <RouterLink to="/practice?mode=daily&limit=12">开始首测</RouterLink>
        </template>
      </section>

      <aside v-if="selectedNode" class="node-detail-card">
        <small>{{ selectedNode.category === "stage" ? "阶段" : selectedNode.category === "course" ? "课程" : "知识点" }}</small>
        <h2>{{ selectedNode.name }}</h2>
        <p>{{ selectedNode.description || "暂无说明" }}</p>
        <span :class="`status-${selectedNode.mastery_status}`">{{ statusText(selectedNode.mastery_status) }}</span>
        <RouterLink
          v-if="selectedNode.category !== 'stage'"
          :to="`/practice?stage=${selectedNode.stage || selectedStage}&course=${selectedNode.course || selectedNode.name}&knowledge_tag=${selectedNode.name}&limit=10`"
        >
          去练习
        </RouterLink>
      </aside>
  </section>
</template>

<script setup>
import { GraphChart } from "echarts/charts";
import { TooltipComponent } from "echarts/components";
import { init, use } from "echarts/core";
import { LabelLayout } from "echarts/features";
import { CanvasRenderer } from "echarts/renderers";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import { apiGet } from "../api/client";
import { useUserStore } from "../stores/user";

use([GraphChart, TooltipComponent, LabelLayout, CanvasRenderer]);

const user = useUserStore();
const graphEl = ref(null);
const graphData = ref({ nodes: [], links: [] });
const diagnosis = ref({ weak_points: [] });
const wrongRecords = ref([]);
const stages = ref([]);
const selectedNode = ref(null);
const selectedStage = ref("");
const selectedCourse = ref("");
const searchText = ref("");
const showLinks = ref(true);
const loadingGraph = ref(false);
const graphZoom = ref(1);
let chart;
let graphResizeObserver;
let observedGraphEl;

const courseOptions = computed(() => {
  if (!selectedStage.value) {
    return stages.value.flatMap((stage) => stage.courses || []);
  }
  return stages.value.find((stage) => stage.stage_name === selectedStage.value)?.courses || [];
});

const visibleNodes = computed(() => {
  const keyword = searchText.value.trim().toLowerCase();
  if (!keyword) {
    return graphData.value.nodes || [];
  }
  return (graphData.value.nodes || []).filter((node) =>
    [node.name, node.stage, node.course, node.description].some((value) => String(value || "").toLowerCase().includes(keyword))
  );
});

const visibleLinks = computed(() => {
  if (!showLinks.value) {
    return [];
  }
  const ids = new Set(visibleNodes.value.map((node) => node.id));
  return (graphData.value.links || []).filter((link) => ids.has(link.source) && ids.has(link.target));
});

const coveredStages = computed(() => new Set((graphData.value.nodes || []).filter((node) => node.category === "stage").map((node) => node.name)).size);
const wrongItems = computed(() => wrongRecords.value.slice(0, 3));
const heatItems = computed(() => (diagnosis.value.weak_points || []).slice(0, 5));
const topWeak = computed(() => heatItems.value[0]);

function nodeColor(status) {
  if (status === "good") return "#3f8f66";
  if (status === "medium") return "#2e7d8c";
  if (status === "weak") return "#b07d1e";
  return "#7d786e";
}

function statusText(status) {
  return {
    good: "掌握良好",
    medium: "中等掌握",
    weak: "薄弱",
    untested: "未测评"
  }[status] || "未测评";
}

function trimQuestion(text) {
  return String(text || "").replace(/\s+/g, " ").slice(0, 72);
}

function mistakeLabel(item) {
  const tags = item.record_mistake_tags || item.mistake_tags || [];
  return Array.isArray(tags) && tags.length ? tags[0] : "待分析";
}

function heatClass(index, score) {
  if (index > Math.round(Number(score || 0) / 3)) return "";
  if (score >= 80) return "green";
  if (score >= 50) return "cyan";
  return "amber";
}

function buildGraphLayout(nodes) {
  const stageNames = [...new Set(nodes.map((node) => node.stage || (node.category === "stage" ? node.name : "")).filter(Boolean))];
  const coursesByStage = new Map(stageNames.map((stage) => [stage, []]));
  const knowledgeByCourse = new Map();

  nodes.forEach((node) => {
    const stage = node.stage || (node.category === "stage" ? node.name : "");
    const course = node.course || (node.category === "course" ? node.name : "");
    if (course && !coursesByStage.get(stage)?.includes(course)) {
      coursesByStage.get(stage)?.push(course);
    }
    if (node.category === "knowledge") {
      const key = `${stage}\u0000${course}`;
      const group = knowledgeByCourse.get(key) || [];
      group.push(node);
      knowledgeByCourse.set(key, group);
    }
  });

  const positions = new Map();
  const stageCount = Math.max(stageNames.length, 1);
  const stageSpan = (Math.PI * 2) / stageCount;

  stageNames.forEach((stage, stageIndex) => {
    const stageAngle = -Math.PI / 2 + (stageIndex + 0.5) * stageSpan;
    nodes
      .filter((node) => node.category === "stage" && (node.stage || node.name) === stage)
      .forEach((node) => positions.set(node.id, [Math.cos(stageAngle) * 90, Math.sin(stageAngle) * 90]));

    const courses = coursesByStage.get(stage) || [];
    const courseSpan = stageSpan / Math.max(courses.length, 1);
    courses.forEach((course, courseIndex) => {
      const courseAngle = stageAngle - stageSpan / 2 + (courseIndex + 0.5) * courseSpan;
      nodes
        .filter((node) => node.category === "course" && (node.course || node.name) === course && node.stage === stage)
        .forEach((node) => positions.set(node.id, [Math.cos(courseAngle) * 230, Math.sin(courseAngle) * 230]));

      const knowledgeNodes = knowledgeByCourse.get(`${stage}\u0000${course}`) || [];
      knowledgeNodes.forEach((node, knowledgeIndex) => {
        const offset = ((knowledgeIndex + 0.5) / Math.max(knowledgeNodes.length, 1) - 0.5) * courseSpan * 0.82;
        const angle = courseAngle + offset;
        const radius = 370 + (knowledgeIndex % 3) * 42;
        positions.set(node.id, [Math.cos(angle) * radius, Math.sin(angle) * radius]);
      });
    });
  });

  return positions;
}

function observeGraphSize() {
  if (!graphEl.value || observedGraphEl === graphEl.value) {
    return;
  }
  graphResizeObserver?.disconnect();
  observedGraphEl = graphEl.value;
  graphResizeObserver = new ResizeObserver(() => resize());
  graphResizeObserver.observe(observedGraphEl);
}

function renderGraph() {
  if (!graphEl.value || !visibleNodes.value.length) {
    graphResizeObserver?.disconnect();
    observedGraphEl = null;
    chart?.dispose();
    chart = null;
    return;
  }
  const width = graphEl.value.clientWidth;
  const height = graphEl.value.clientHeight;
  if (!width || !height) {
    window.requestAnimationFrame(renderGraph);
    return;
  }
  observeGraphSize();
  if (!chart) {
    chart = init(graphEl.value, null, { width, height });
    chart.on("click", (event) => {
      if (event.dataType === "node") {
        selectedNode.value = event.data.raw;
      }
    });
  }
  const compact = width < 720;
  const positions = buildGraphLayout(visibleNodes.value);
  chart.setOption({
    tooltip: {
      formatter: (params) => {
        const node = params.data?.raw;
        return node ? `${node.name}<br/>${statusText(node.mastery_status)}${node.mastery ? ` · ${node.mastery}%` : ""}` : "";
      }
    },
    series: [
      {
        type: "graph",
        layout: "none",
        left: compact ? "12%" : "4%",
        right: compact ? "12%" : "4%",
        top: compact ? "8%" : "10%",
        bottom: compact ? "8%" : "6%",
        roam: true,
        draggable: true,
        zoom: graphZoom.value,
        categories: [{ name: "stage" }, { name: "course" }, { name: "knowledge" }],
        label: {
          show: true,
          color: "#edf9fa",
          fontSize: compact ? 9 : 11,
          fontWeight: 700,
          overflow: "truncate",
          width: compact ? 52 : 76,
          formatter: (params) => (params.data.raw.category === "knowledge" ? "" : params.name)
        },
        labelLayout: { hideOverlap: true },
        emphasis: { focus: "adjacency", label: { show: true, formatter: "{b}" } },
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: 7,
        lineStyle: { color: "rgba(100, 90, 70, 0.36)", curveness: 0.12 },
        data: visibleNodes.value.map((node) => ({
          x: positions.get(node.id)?.[0] || 0,
          y: positions.get(node.id)?.[1] || 0,
          id: node.id,
          name: node.name,
          category: node.category,
          symbolSize: compact
            ? node.category === "stage"
              ? 24
              : node.category === "course"
                ? 16
                : 5
            : node.category === "stage"
              ? 32
              : node.category === "course"
                ? 20
                : 7,
          value: node.mastery,
          raw: node,
          itemStyle: {
            color: nodeColor(node.mastery_status),
            borderColor: "rgba(51, 48, 43, 0.72)",
            borderWidth: node.category === "stage" ? 2 : 1
          }
        })),
        links: visibleLinks.value
      }
    ]
  });
}

async function loadGraph() {
  loadingGraph.value = true;
  try {
    const data = await apiGet("/api/knowledge-graph", {
      stage: selectedStage.value,
      course: selectedCourse.value
    });
    graphData.value = data;
    selectedNode.value = null;
    await nextTick();
    renderGraph();
  } finally {
    loadingGraph.value = false;
  }
}

async function loadAll() {
  const stageData = await apiGet("/api/stages").catch(() => ({ stages: [] }));
  stages.value = stageData.stages || [];
  await loadGraph().catch(() => null);
  if (user.userId) {
    const [diagnoseData, wrongData] = await Promise.all([
      apiGet("/api/diagnose").catch(() => ({ weak_points: [], recent_record_count: 0 })),
      apiGet("/api/review/wrong-questions", { limit: 10 }).catch(() => ({ items: [] }))
    ]);
    diagnosis.value = diagnoseData;
    wrongRecords.value = wrongData.items || [];
  } else {
    diagnosis.value = { weak_points: [], recent_record_count: 0 };
    wrongRecords.value = [];
  }
}

function onStageChange() {
  if (selectedCourse.value && !courseOptions.value.some((course) => course.course_name === selectedCourse.value)) {
    selectedCourse.value = "";
  }
  loadGraph();
}

function resetFilters() {
  selectedStage.value = "";
  selectedCourse.value = "";
  searchText.value = "";
  loadGraph();
}

function zoomGraph(scale) {
  graphZoom.value = Math.max(0.45, Math.min(2.2, graphZoom.value * scale));
  renderGraph();
}

function resetGraph() {
  graphZoom.value = 1;
  renderGraph();
}

function resize() {
  if (chart && graphEl.value?.clientWidth && graphEl.value?.clientHeight) {
    chart.resize();
  }
}

watch([searchText, showLinks], () => nextTick(renderGraph));
watch(() => user.userId, loadAll);

onMounted(() => {
  loadAll();
  window.addEventListener("resize", resize);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resize);
  graphResizeObserver?.disconnect();
  chart?.dispose();
});
</script>

<style scoped src="../styles/views/knowledge.css"></style>
