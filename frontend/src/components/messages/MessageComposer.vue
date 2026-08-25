<template>
  <form class="message-composer" @submit.prevent="submit">
    <QuestionRefCard v-if="questionRef" :reference="questionRef" />
    <button v-if="questionRef" class="remove-question" type="button" @click="$emit('clear-question')">移除题目引用</button>
    <div v-if="images.length" class="composer-images">
      <article v-for="file in images" :key="file.id"><img :src="file.url" :alt="file.name" /><button type="button" aria-label="移除图片" @click="removeImage(file)">×</button></article>
    </div>
    <div class="composer-row">
      <textarea v-model="content" rows="3" maxlength="5000" :placeholder="placeholder" @keydown.ctrl.enter="submit"></textarea>
      <div>
        <input ref="fileInput" hidden type="file" accept="image/jpeg,image/png,image/webp" multiple @change="pickImages" />
        <button class="image-action" type="button" :disabled="busy || uploading || images.length >= 5" @click="fileInput?.click()">{{ uploading ? "上传中…" : "添加图片" }}</button>
        <button class="send-action" type="submit" :disabled="busy || uploading || !canSend">{{ busy ? "发送中…" : "发送" }}</button>
      </div>
    </div>
    <p v-if="error" class="composer-error">{{ error }}</p>
    <small class="composer-hint">支持文字、最多 5 张图片和题目引用；Ctrl + Enter 快速发送</small>
  </form>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from "vue";

import { apiDelete, apiUpload } from "../../api/client";
import QuestionRefCard from "./QuestionRefCard.vue";

const props = defineProps({
  busy: { type: Boolean, default: false },
  placeholder: { type: String, default: "输入消息" },
  questionRef: { type: Object, default: null }
});
const emit = defineEmits(["send", "clear-question"]);
const content = ref("");
const images = ref([]);
const uploading = ref(false);
const error = ref("");
const fileInput = ref(null);
const canSend = computed(() => Boolean(content.value.trim() || images.value.length || props.questionRef));

async function pickImages(event) {
  const selected = [...(event.target.files || [])].slice(0, Math.max(0, 5 - images.value.length));
  event.target.value = "";
  if (!selected.length) return;
  uploading.value = true;
  error.value = "";
  try {
    const form = new FormData();
    selected.forEach((file) => form.append("files", file));
    const result = await apiUpload("/api/uploads/message-images", form);
    images.value.push(...(result.files || []));
  } catch (uploadError) {
    error.value = uploadError.message || "图片上传失败。";
  } finally {
    uploading.value = false;
  }
}
async function removeImage(file) {
  try {
    await apiDelete(`/api/uploads/${file.id}`);
    images.value = images.value.filter((item) => item.id !== file.id);
  } catch (removeError) {
    error.value = removeError.message || "图片移除失败。";
  }
}
function reset() {
  content.value = "";
  images.value = [];
  error.value = "";
  emit("clear-question");
}
function submit() {
  if (!canSend.value || props.busy || uploading.value) return;
  emit("send", { content: content.value.trim() || null, attachment_ids: images.value.map((file) => file.id), question_ref: props.questionRef || null }, reset);
}
onBeforeUnmount(() => {
  const pendingIds = images.value.map((file) => file.id);
  if (pendingIds.length) void Promise.allSettled(pendingIds.map((id) => apiDelete(`/api/uploads/${id}`)));
});
</script>

<style scoped>
.message-composer{display:grid;gap:9px;padding:13px 14px;border-top:1px solid rgba(100, 90, 70, 0.12);background: rgba(255, 255, 255, 0.94)}.message-composer>.question-ref-card{max-width:560px}.remove-question{justify-self:start;padding:0;color:#8f5f0e;border:0;background:transparent;font-size:11px}.composer-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:9px}.composer-row textarea{min-height:72px;resize:vertical;padding:11px;color:#33302b;border:1px solid rgba(100, 90, 70, 0.18);outline:0;background:#ffffff;line-height:1.55}.composer-row textarea:focus{border-color:#287381}.composer-row>div{display:grid;grid-template-rows:1fr 1fr;gap:7px}.composer-row button{min-width:92px;padding:0 14px;border:1px solid rgba(46, 125, 140, 0.28);font-weight:800}.image-action{color:#33302b;background:#ffffff}.send-action{color:#ffffff;background:#2e7d8c}.composer-row button:disabled{cursor:not-allowed;opacity:.45}.composer-images{display:flex;flex-wrap:wrap;gap:7px}.composer-images article{position:relative;width:76px;height:60px}.composer-images img{width:100%;height:100%;object-fit:cover}.composer-images button{position:absolute;right:3px;top:3px;width:22px;height:22px;padding:0;color:#fff;border:0;background: rgba(60, 55, 45, 0.4)}.composer-error{margin:0;color:#ad5046;font-size:12px}.composer-hint{color:#706b62}@media(max-width:560px){.composer-row{grid-template-columns:1fr}.composer-row>div{grid-template-columns:1fr 1fr;grid-template-rows:auto}.composer-row button{min-height:40px}}
</style>
