<template>
  <article class="message-bubble" :class="{ mine, advice: message.message_type === 'advice' }">
    <small>{{ label }}</small>
    <p v-if="message.content">{{ message.content }}</p>
    <div v-if="message.attachments?.length" class="message-images">
      <button v-for="file in message.attachments" :key="file.id" type="button" @click="preview = file">
        <img :src="file.url" :alt="file.name || '消息图片'" />
      </button>
    </div>
    <QuestionRefCard v-if="message.question_ref" :reference="message.question_ref" />
    <time>{{ formatTime(message.created_at) }}</time>
  </article>
  <div v-if="preview" class="message-lightbox" role="dialog" aria-modal="true" aria-label="查看消息图片" @click.self="preview = null">
    <header><span>{{ preview.name || "消息图片" }}</span><button type="button" aria-label="关闭图片预览" @click="preview = null">关闭</button></header>
    <img :src="preview.url" :alt="preview.name || '消息图片'" />
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

import QuestionRefCard from "./QuestionRefCard.vue";

const props = defineProps({
  message: { type: Object, required: true },
  currentUserId: { type: [Number, String], required: true },
  otherName: { type: String, default: "对方" }
});
const preview = ref(null);
const mine = computed(() => Number(props.message.sender_id) === Number(props.currentUserId));
const label = computed(() => {
  if (props.message.message_type === "advice") return "学习调整建议";
  return mine.value ? "我" : props.otherName;
});
function formatTime(value) {
  return value ? new Date(value).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
}
</script>

<style scoped>
.message-bubble{max-width:min(78%,620px);align-self:flex-start;padding:11px 13px;border:1px solid rgba(100, 90, 70, 0.14);background:#ffffff}.message-bubble.mine{align-self:flex-end;border-color:rgba(46, 125, 140, 0.32);background:#e4efec}.message-bubble.advice{border-left:3px solid #b07d1e;background:rgba(176, 125, 30, 0.09)}.message-bubble>small,.message-bubble>time{display:block;color:#706b62;font-size:10px}.message-bubble>p{margin:5px 0;color:#33302b;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.65}.message-bubble>time{margin-top:7px;text-align:right}.message-images{display:grid;grid-template-columns:repeat(2,minmax(0,190px));gap:6px;margin-top:8px}.message-images button{aspect-ratio:4/3;overflow:hidden;padding:0;border:1px solid rgba(100, 90, 70, 0.16);background:#ffffff}.message-images img{width:100%;height:100%;object-fit:cover}.message-lightbox{position:fixed;z-index:40;inset:0;display:grid;grid-template-rows:auto minmax(0,1fr);padding:16px;background: rgba(60, 55, 45, 0.4)}.message-lightbox header{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:10px 12px;color:#33302b;border:1px solid rgba(46, 125, 140, 0.2);background:#ffffff}.message-lightbox button{min-height:34px;padding:0 12px;color:#33302b;border:1px solid rgba(46, 125, 140, 0.25);background:#ffffff}.message-lightbox>img{max-width:min(1200px,90vw);max-height:80vh;place-self:center;object-fit:contain}@media(max-width:520px){.message-bubble{max-width:92%}.message-images{grid-template-columns:1fr}.message-lightbox{padding:8px}}
</style>
