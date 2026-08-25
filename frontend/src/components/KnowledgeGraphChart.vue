<template>
  <div ref="chartEl" class="chart-box graph-box"></div>
</template>

<script setup>
import * as echarts from "echarts";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  links: { type: Array, default: () => [] }
});

const chartEl = ref(null);
let chart;

function nodeColor(node) {
  if (node.category === "stage") return "#2e7d8c";
  if (node.category === "course") return "#3f8f66";
  if ((node.mastery || 0) < 50) return "#b07d1e";
  return "#2e7d8c";
}

function render() {
  if (!chartEl.value) {
    return;
  }
  if (!chart) {
    chart = echarts.init(chartEl.value);
  }
  const nodes = props.nodes.map((node) => ({
    ...node,
    itemStyle: { color: nodeColor(node), borderColor: "rgba(100,90,70,.35)", borderWidth: 1 },
    label: { color: "#33302b", fontSize: node.category === "knowledge" ? 11 : 13 }
  }));
  chart.setOption({
    tooltip: {},
    animationDurationUpdate: 450,
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        force: { repulsion: 180, edgeLength: [70, 150] },
        label: { show: true },
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: [0, 8],
        lineStyle: { color: "rgba(60, 55, 45, 0.28)", width: 1.2, curveness: 0.08 },
        data: nodes,
        links: props.links
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
watch(() => [props.nodes, props.links], render, { deep: true });
onBeforeUnmount(() => {
  window.removeEventListener("resize", resize);
  chart?.dispose();
});
</script>
