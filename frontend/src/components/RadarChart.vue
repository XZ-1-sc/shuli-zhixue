<template>
  <div v-if="items.length" ref="chartEl" class="chart-box"></div>
  <div v-else class="chart-empty">
    <strong>尚未生成雷达图</strong>
    <span>完成首测后，这里会按课程显示真实掌握度。</span>
  </div>
</template>

<script setup>
import * as echarts from "echarts";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  }
});

const chartEl = ref(null);
let chart;

function render() {
  if (!chartEl.value || !props.items.length) {
    chart?.dispose();
    chart = null;
    return;
  }
  if (!chart) {
    chart = echarts.init(chartEl.value);
  }
  const values = props.items;

  chart.setOption({
    color: ["#64d7e8"],
    tooltip: { trigger: "item" },
    radar: {
      indicator: values.map((item) => ({ name: item.name, max: 100 })),
      radius: "66%",
      splitNumber: 4,
      axisName: { color: "#dcd5c8", fontSize: 12 },
      axisLine: { lineStyle: { color: "rgba(220,213,200,.2)" } },
      splitLine: { lineStyle: { color: "rgba(220,213,200,.14)" } },
      splitArea: { areaStyle: { color: ["rgba(100,215,232,.03)", "rgba(100,215,232,.08)"] } }
    },
    series: [
      {
        type: "radar",
        data: [
          {
            value: values.map((item) => item.score),
            name: "掌握度",
            areaStyle: { color: "rgba(100,215,232,.28)" },
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
