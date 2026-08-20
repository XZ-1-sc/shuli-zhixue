<template>
  <section class="knowledge-ref-page">
    <header class="knowledge-topbar">
      <RouterLink class="knowledge-logo" to="/">
        <span>✣</span>
        <strong>数理智学</strong>
        <small>大学数学智能学习系统</small>
      </RouterLink>
      <nav>
        <RouterLink to="/">学习看板</RouterLink>
        <RouterLink to="/roadmap">课程学习</RouterLink>
        <RouterLink to="/practice">智能练习</RouterLink>
        <RouterLink class="active" to="/knowledge">知识图谱</RouterLink>
        <RouterLink to="/review">学习报告</RouterLink>
      </nav>
      <label class="knowledge-search">
        ⌕
        <input v-model="searchText" placeholder="搜索知识点 / 课程 / 阶段" />
      </label>
      <button class="round-icon" type="button" @click="loadAll">↻</button>
      <UserAccountButton />
    </header>

    <main class="knowledge-ref-main">
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
            <div v-show="visibleNodes.length" ref="graphEl" class="graph-canvas"></div>
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
    </main>
  </section>
</template>

<script setup>
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import UserAccountButton from "../components/UserAccountButton.vue";
import { apiGet } from "../api/client";
import { useUserStore } from "../stores/user";

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
  if (status === "good") return "#6ed991";
  if (status === "medium") return "#54d8ea";
  if (status === "weak") return "#f3ad49";
  return "#8b9aa3";
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

function renderGraph() {
  if (!graphEl.value || !visibleNodes.value.length) {
    chart?.dispose();
    chart = null;
    return;
  }
  if (!chart) {
    chart = echarts.init(graphEl.value);
    chart.on("click", (event) => {
      if (event.dataType === "node") {
        selectedNode.value = event.data.raw;
      }
    });
  }
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
        layout: "force",
        left: "4%",
        right: "4%",
        top: "10%",
        bottom: "6%",
        roam: true,
        draggable: true,
        zoom: graphZoom.value,
        categories: [{ name: "stage" }, { name: "course" }, { name: "knowledge" }],
        force: { repulsion: 110, edgeLength: [54, 112], gravity: 0.22, layoutAnimation: false },
        label: { show: true, color: "#edf9fa", fontSize: 11, fontWeight: 700, overflow: "truncate", width: 76 },
        labelLayout: { hideOverlap: true },
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: 7,
        lineStyle: { color: "rgba(191, 220, 226, 0.36)", curveness: 0.12 },
        data: visibleNodes.value.map((node) => ({
          id: node.id,
          name: node.name,
          category: node.category,
          symbolSize: node.category === "stage" ? 44 : node.category === "course" ? 34 : Math.min(28, node.symbolSize || 24),
          value: node.mastery,
          raw: node,
          itemStyle: {
            color: nodeColor(node.mastery_status),
            borderColor: "rgba(238, 247, 246, 0.72)",
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
  const data = await apiGet("/api/knowledge-graph", {
    stage: selectedStage.value,
    course: selectedCourse.value
  });
  graphData.value = data;
  selectedNode.value = null;
  loadingGraph.value = false;
  await nextTick();
  renderGraph();
}

async function loadAll() {
  const stageData = await apiGet("/api/stages");
  stages.value = stageData.stages || [];
  await loadGraph();
  if (user.userId) {
    const [diagnoseData, wrongData] = await Promise.all([
      apiGet("/api/diagnose"),
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
  chart?.resize();
}

watch([searchText, showLinks], () => nextTick(renderGraph));
watch(() => user.userId, loadAll);

onMounted(() => {
  loadAll();
  window.addEventListener("resize", resize);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resize);
  chart?.dispose();
});
</script>
