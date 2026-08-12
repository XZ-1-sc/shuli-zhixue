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
  if (node.category === "stage") return "#4fa8ff";
  if (node.category === "course") return "#70e0aa";
  if ((node.mastery || 0) < 50) return "#f4b84e";
  return "#64d7e8";
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
    itemStyle: { color: nodeColor(node), borderColor: "rgba(255,255,255,.5)", borderWidth: 1 },
    label: { color: "#f4f0e8", fontSize: node.category === "knowledge" ? 11 : 13 }
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
        lineStyle: { color: "rgba(220,213,200,.28)", width: 1.2, curveness: 0.08 },
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
