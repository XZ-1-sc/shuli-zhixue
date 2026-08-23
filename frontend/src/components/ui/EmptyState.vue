<template><section class="empty-state"><strong>{{ title }}</strong><p>{{ description }}</p><slot /></section></template>
<script setup>defineProps({ title:{type:String,required:true}, description:{type:String,default:""} });</script>
<style scoped>.empty-state{min-height:240px;display:grid;place-content:center;justify-items:center;gap:10px;padding:28px;text-align:center;border:1px solid rgba(145,185,194,.16);border-radius:14px;background:#0a1c28}.empty-state strong{font-size:22px}.empty-state p{max-width:48ch;margin:0;color:#8da4a9;line-height:1.7}</style>
