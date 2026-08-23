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
.toast-item { display: grid; grid-template-columns: 24px 1fr 28px; align-items: start; gap: 10px; padding: 14px 15px; color: #edf6f5; border: 1px solid rgba(120, 205, 215, 0.25); border-left: 3px solid #f07575; border-radius: 10px; background: rgba(7, 23, 32, 0.97); box-shadow: 0 16px 44px rgba(0, 0, 0, 0.28); pointer-events: auto; }
.toast-item[data-tone="success"] { border-left-color: #65d6a2; }
.toast-item[data-tone="warning"] { border-left-color: #f0bb61; }
.toast-item > span { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; color: #071820; background: #f07575; font-weight: 900; }
.toast-item[data-tone="success"] > span { background: #65d6a2; }
.toast-item[data-tone="warning"] > span { background: #f0bb61; }
.toast-item p { margin: 1px 0 0; line-height: 1.55; }
.toast-item button { color: #a9bdc0; border: 0; background: transparent; font-size: 20px; cursor: pointer; }
</style>
