<template>
  <Teleport to="body">
    <div v-if="confirmState.open" class="confirm-backdrop" role="presentation" @click.self="settleConfirmation(false)">
      <section class="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-description">
        <small>请确认</small>
        <h2 id="confirm-title">{{ confirmState.title }}</h2>
        <p id="confirm-description">{{ confirmState.description }}</p>
        <div class="confirm-actions">
          <button type="button" class="confirm-cancel" @click="settleConfirmation(false)">取消</button>
          <button type="button" class="confirm-submit" :data-tone="confirmState.tone" autofocus @click="settleConfirmation(true)">{{ confirmState.confirmLabel }}</button>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
import { onBeforeUnmount, onMounted } from "vue";
import { confirmState, settleConfirmation } from "../../services/confirm";

function handleKeydown(event) {
  if (event.key === "Escape" && confirmState.open) settleConfirmation(false);
}

onMounted(() => window.addEventListener("keydown", handleKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", handleKeydown));
</script>

<style scoped>
.confirm-backdrop { position: fixed; inset: 0; z-index: 130; display: grid; place-items: center; padding: 20px; background: rgba(2, 10, 15, 0.72); backdrop-filter: blur(8px); }
.confirm-dialog { width: min(440px, 100%); padding: 28px; color: #edf6f5; border: 1px solid rgba(126, 208, 218, 0.25); border-radius: 14px; background: #091c27; box-shadow: 0 24px 70px rgba(0, 0, 0, 0.42); }
.confirm-dialog small { color: #62d8e7; font-weight: 800; }
.confirm-dialog h2 { margin: 8px 0 10px; font-size: 25px; }
.confirm-dialog p { margin: 0; color: #a8bbc0; line-height: 1.7; }
.confirm-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 26px; }
.confirm-actions button { min-height: 42px; padding: 0 18px; border-radius: 8px; font-weight: 800; cursor: pointer; }
.confirm-cancel { color: #d7e3e3; border: 1px solid rgba(155, 190, 195, 0.25); background: transparent; }
.confirm-submit { color: #06151c; border: 1px solid #66d8e7; background: #66d8e7; }
.confirm-submit[data-tone="danger"] { color: #fff; border-color: #d85f66; background: #bd4c54; }
</style>
