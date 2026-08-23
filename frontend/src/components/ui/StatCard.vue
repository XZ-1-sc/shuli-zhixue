<template><article class="stat-card"><small>{{ label }}</small><strong>{{ value }}</strong><p v-if="hint">{{ hint }}</p></article></template>
<script setup>defineProps({ label:{type:String,required:true}, value:{type:[String,Number],required:true}, hint:{type:String,default:""} });</script>
<style scoped>.stat-card{padding:18px;border:1px solid rgba(145,185,194,.16);border-radius:14px;background:#0b1e2a}.stat-card small,.stat-card p{color:#8da3a8}.stat-card strong{display:block;margin:8px 0;font-size:30px}.stat-card p{margin:0;font-size:12px}</style>
