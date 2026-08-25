<template>
  <div class="toast-stack" aria-live="polite" aria-atomic="true">
    <article v-for="item in toastState.items" :key="item.id" class="toast-item" :data-tone="item.tone">
      <span aria-hidden="true">{{ item.tone === "success" ? "✓" : item.tone === "warning" ? "!" : "×" }}</span>
      <p>{{ item.message }}</p>
      <button type="button" aria-label="关闭提示" @click="dismissToast(item.id)">×</button>
    </article>
  </div>
</template>

<script setup>
import { dismissToast, toastState } from "../../services/toast";
</script>

<style scoped>
.toast-stack { position: fixed; top: 84px; right: 20px; z-index: 120; display: grid; gap: 10px; width: min(380px, calc(100vw - 32px)); pointer-events: none; }
.toast-item { display: grid; grid-template-columns: 24px 1fr 28px; align-items: start; gap: 10px; padding: 14px 15px; color: #33302b; border: 1px solid rgba(46, 125, 140, 0.25); border-left: 3px solid #b4554a; border-radius: 10px; background: rgba(255, 255, 255, 0.94); box-shadow: 0 16px 44px rgba(90, 75, 50, 0.112); pointer-events: auto; }
.toast-item[data-tone="success"] { border-left-color: #347a56; }
.toast-item[data-tone="warning"] { border-left-color: #8f5f0e; }
.toast-item > span { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; color: #ffffff; background: #b4554a; font-weight: 900; }
.toast-item[data-tone="success"] > span { background: #3f8f66; }
.toast-item[data-tone="warning"] > span { background: #b07d1e; }
.toast-item p { margin: 1px 0 0; line-height: 1.55; }
.toast-item button { color: #33302b; border: 0; background: transparent; font-size: 20px; cursor: pointer; }
</style>
