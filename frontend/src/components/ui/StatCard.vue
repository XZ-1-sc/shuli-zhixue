<template><article class="stat-card"><small>{{ label }}</small><strong>{{ value }}</strong><p v-if="hint">{{ hint }}</p></article></template>
<script setup>defineProps({ label:{type:String,required:true}, value:{type:[String,Number],required:true}, hint:{type:String,default:""} });</script>
<style scoped>.stat-card{padding:18px;border:1px solid rgba(46, 125, 140, 0.16);border-radius:14px;background:#ffffff}.stat-card small,.stat-card p{color:#706b62}.stat-card strong{display:block;margin:8px 0;font-size:30px}.stat-card p{margin:0;font-size:12px}</style>
