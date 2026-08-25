<template>
  <div v-if="items.length >= 3" ref="chartEl" class="chart-box"></div>
  <div v-else-if="items.length" class="radar-sparse-list" role="list" aria-label="课程掌握度">
    <div v-for="item in items" :key="item.name" role="listitem">
      <span>{{ item.name }}</span>
      <b>{{ normalizedScore(item.score) }}%</b>
      <i aria-hidden="true"><em :style="{ width: `${normalizedScore(item.score)}%` }"></em></i>
    </div>
  </div>
  <div v-else class="chart-empty">
    <strong>尚未生成雷达图</strong>
    <span>完成首测后，这里会按课程显示真实掌握度。</span>
  </div>
</template>

<script setup>
import { RadarChart as EChartsRadarChart } from "echarts/charts";
import { RadarComponent, TooltipComponent } from "echarts/components";
import { init, use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

use([EChartsRadarChart, RadarComponent, TooltipComponent, CanvasRenderer]);

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  }
});

const chartEl = ref(null);
let chart;

function normalizedScore(value) {
  return Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
}

function render() {
  if (!chartEl.value || props.items.length < 3) {
    chart?.dispose();
    chart = null;
    return;
  }
  if (!chart) {
    chart = init(chartEl.value);
  }
  const values = props.items;

  chart.setOption({
    color: ["#2e7d8c"],
    tooltip: { trigger: "item" },
    radar: {
      indicator: values.map((item) => ({ name: item.name, max: 100 })),
      radius: "66%",
      splitNumber: 4,
      axisName: { color: "#55503f", fontSize: 12 },
      axisLine: { lineStyle: { color: "rgba(60, 55, 45, 0.2)" } },
      splitLine: { lineStyle: { color: "rgba(60, 55, 45, 0.14)" } },
      splitArea: { areaStyle: { color: ["rgba(46, 125, 140, 0.03)", "rgba(46, 125, 140, 0.08)"] } }
    },
    series: [
      {
        type: "radar",
        data: [
          {
            value: values.map((item) => normalizedScore(item.score)),
            name: "掌握度",
            areaStyle: { color: "rgba(46, 125, 140, 0.28)" },
            lineStyle: { width: 2 },
            symbolSize: 5
          }
        ]
      }
    ]
  });
}

function resize() {
  chart?.resize();
}

onMounted(() => {
  render();
  window.addEventListener("resize", resize);
});
watch(
  () => props.items,
  async () => {
    await nextTick();
    render();
  },
  { deep: true }
);
onBeforeUnmount(() => {
  window.removeEventListener("resize", resize);
  chart?.dispose();
});
</script>

<style scoped>
.radar-sparse-list {
  min-height: 220px;
  display: grid;
  align-content: center;
  gap: 18px;
  padding: 28px;
}

.radar-sparse-list > div {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px 16px;
}

.radar-sparse-list span {
  min-width: 0;
  overflow: hidden;
  color: #55503f;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.radar-sparse-list b {
  color: #287381;
  font-variant-numeric: tabular-nums;
}

.radar-sparse-list i {
  grid-column: 1 / -1;
  height: 7px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(60, 55, 45, 0.12);
}

.radar-sparse-list em {
  height: 100%;
  display: block;
  border-radius: inherit;
  background: #2e7d8c;
}
</style>
