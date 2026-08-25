<template>
  <RouterLink class="question-ref-card" :to="target">
    <span>题目引用</span>
    <strong>{{ reference.knowledge_tag || reference.course || "练习题" }}</strong>
    <p>{{ reference.text || `题目 #${reference.question_id}` }}</p>
    <small>{{ reference.record_id ? "查看本次作答与复盘" : "打开题目" }} ›</small>
  </RouterLink>
</template>

<script setup>
import { computed } from "vue";
import { RouterLink } from "vue-router";

const props = defineProps({ reference: { type: Object, required: true } });
const target = computed(() =>
  props.reference.record_id
    ? `/review?record_id=${props.reference.record_id}`
    : `/practice?question_id=${props.reference.question_id}`
);
</script>

<style scoped>
.question-ref-card{min-width:0;display:grid;gap:5px;margin-top:9px;padding:11px 12px;color:#33302b;border:1px solid rgba(46, 125, 140, 0.2);background: rgba(255, 255, 255, 0.82);transition:border-color .2s ease,transform .2s ease}.question-ref-card:hover{border-color:rgba(46, 125, 140, 0.5);transform:translateY(-1px)}.question-ref-card span,.question-ref-card small{color:#287381;font-size:10px;font-weight:800}.question-ref-card strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.question-ref-card p{display:-webkit-box;overflow:hidden;margin:0;color:#33302b;font-size:12px;line-height:1.55;-webkit-box-orient:vertical;-webkit-line-clamp:2}
</style>
