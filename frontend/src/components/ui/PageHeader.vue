<template>
  <header class="page-header">
    <div>
      <small v-if="eyebrow">{{ eyebrow }}</small>
      <h1>{{ title }}</h1>
      <p v-if="description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="page-header-actions"><slot name="actions" /></div>
  </header>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  eyebrow: { type: String, default: "" },
  description: { type: String, default: "" }
});
</script>

<style scoped>
.page-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
.page-header small { color: #64d7e8; font-size: 12px; font-weight: 800; }
.page-header h1 { margin: 7px 0 0; color: #f2f7f6; font-size: clamp(30px, 3vw, 44px); line-height: 1.12; }
.page-header p { max-width: 66ch; margin: 9px 0 0; color: #91a7ac; line-height: 1.7; }
.page-header-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
@media (max-width: 760px) { .page-header { align-items: stretch; flex-direction: column; gap: 16px; } .page-header-actions { width: 100%; } }
</style>
