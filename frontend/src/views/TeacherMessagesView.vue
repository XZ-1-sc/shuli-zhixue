<template>
  <section class="teacher-view">
    <PageHeader title="消息中心" eyebrow="师生沟通" description="仅显示当前任教关系中的师生会话；学生之间的私聊不会出现在教师端。">
      <template #actions><button class="teacher-primary-action new-conversation" type="button" @click="openContacts">发起会话</button></template>
    </PageHeader>
    <p v-if="error" class="teacher-form-message is-error">{{ error }}</p>
    <section class="teacher-message-layout">
      <aside class="teacher-panel conversation-list">
        <header><div><strong>学生会话</strong><small>{{ conversations.length }} 个会话</small></div><button type="button" @click="loadConversations">刷新</button></header>
        <div v-if="loadingConversations" class="conversation-loading"><span v-for="index in 5" :key="index"></span></div>
        <div v-else-if="conversations.length">
          <button v-for="item in conversations" :key="item.id" type="button" :class="{ active: selectedConversationId === item.id }" @click="selectConversation(item.id)">
            <i>{{ item.other.nickname.slice(0, 1) }}</i><span><strong>{{ item.other.nickname }}</strong><small>@{{ item.other.username }}</small><p>{{ item.latest_message || "还没有消息，点击开始沟通" }}</p></span><b v-if="item.unread_count">{{ item.unread_count }}</b>
          </button>
        </div>
        <div v-else class="teacher-inline-empty"><strong>还没有会话</strong><p>点击“发起会话”，从当前班级选择一名学生。</p></div>
      </aside>
      <article class="teacher-panel conversation-thread">
        <template v-if="selectedConversation">
          <header><div><strong>{{ selectedConversation.other.nickname }}</strong><small>学生 · @{{ selectedConversation.other.username }}</small></div><RouterLink :to="`/teacher/students/${selectedConversation.other.id}`">查看学情</RouterLink></header>
          <div ref="messageList" class="thread-messages">
            <button v-if="hasMore" class="load-earlier" type="button" :disabled="threadLoading" @click="loadEarlier">{{ threadLoading ? "加载中…" : "加载更早消息" }}</button>
            <div v-if="threadLoading && !messages.length" class="teacher-inline-empty">正在加载会话…</div>
            <div v-else-if="!messages.length" class="teacher-inline-empty">还没有消息。可以从一条具体、可执行的反馈开始。</div>
            <MessageBubble v-for="message in messages" :key="message.id" :message="message" :current-user-id="user.userId" :other-name="selectedConversation.other.nickname" />
          </div>
          <MessageComposer :busy="sending" placeholder="给学生发送消息" @send="sendMessage" />
        </template>
        <div v-else class="conversation-empty"><span>◇</span><strong>选择一名学生</strong><p>查看完整对话，或发起新的学习沟通。</p><button type="button" @click="openContacts">选择联系人</button></div>
      </article>
    </section>
    <ContactPicker :open="contactPickerOpen" :groups="contactGroups" :loading="contactsLoading" @close="contactPickerOpen = false" @select="startConversation" />
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { apiGet, apiPost } from "../api/client";
import ContactPicker from "../components/messages/ContactPicker.vue";
import MessageBubble from "../components/messages/MessageBubble.vue";
import MessageComposer from "../components/messages/MessageComposer.vue";
import PageHeader from "../components/ui/PageHeader.vue";
import { useUserStore } from "../stores/user";

const route = useRoute();
const router = useRouter();
const user = useUserStore();
const conversations = ref([]);
const selectedConversationId = ref(null);
const messages = ref([]);
const hasMore = ref(false);
const nextBeforeId = ref(null);
const error = ref("");
const loadingConversations = ref(false);
const threadLoading = ref(false);
const sending = ref(false);
const messageList = ref(null);
const contactPickerOpen = ref(false);
const contactsLoading = ref(false);
const contactGroups = ref([]);
const selectedConversation = computed(() => conversations.value.find((item) => item.id === selectedConversationId.value) || null);

async function scrollLatest() { await nextTick(); if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight; }
async function loadConversations() {
  loadingConversations.value = !conversations.value.length;
  try { const data = await apiGet("/api/messages/conversations", { relation: "teacher_student" }); conversations.value = data.items || []; }
  finally { loadingConversations.value = false; }
}
async function selectConversation(conversationId, updateRoute = true) {
  selectedConversationId.value = Number(conversationId); messages.value = []; hasMore.value = false; threadLoading.value = true; error.value = "";
  if (updateRoute) await router.replace({ query: { conversation_id: conversationId } });
  try {
    const data = await apiGet(`/api/messages/conversations/${conversationId}`, { limit: 50 });
    messages.value = data.items || []; hasMore.value = Boolean(data.has_more); nextBeforeId.value = data.next_before_id;
    await apiPost(`/api/messages/conversations/${conversationId}/read`, {});
    await loadConversations(); await scrollLatest();
  } catch (exception) { error.value = exception.message; }
  finally { threadLoading.value = false; }
}
async function loadEarlier() {
  if (!hasMore.value || !nextBeforeId.value) return;
  threadLoading.value = true;
  const previousHeight = messageList.value?.scrollHeight || 0;
  try {
    const data = await apiGet(`/api/messages/conversations/${selectedConversationId.value}`, { limit: 50, before_id: nextBeforeId.value });
    messages.value.unshift(...(data.items || [])); hasMore.value = Boolean(data.has_more); nextBeforeId.value = data.next_before_id;
    await nextTick(); if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight - previousHeight;
  } catch (exception) { error.value = exception.message; }
  finally { threadLoading.value = false; }
}
async function sendMessage(payload, resetComposer) {
  sending.value = true; error.value = "";
  try {
    const message = await apiPost(`/api/messages/conversations/${selectedConversationId.value}`, payload);
    messages.value.push(message); resetComposer(); await loadConversations(); await scrollLatest();
  } catch (exception) { error.value = exception.message; }
  finally { sending.value = false; }
}
async function openContacts() {
  contactPickerOpen.value = true;
  if (contactGroups.value.length) return;
  contactsLoading.value = true;
  try {
    const data = await apiGet("/api/messages/contacts");
    contactGroups.value = (data.groups || []).flatMap((group) => group.sections?.length
      ? group.sections.map((section) => ({ key: section.key, label: section.label, items: section.items || [] }))
      : [group]);
  }
  catch (exception) { error.value = exception.message; contactPickerOpen.value = false; }
  finally { contactsLoading.value = false; }
}
async function startConversation(contact) {
  try {
    const result = await apiPost("/api/messages/conversations/start", { target_user_id: contact.user_id, relation: contact.relation });
    contactPickerOpen.value = false; await loadConversations(); await selectConversation(result.conversation_id);
  } catch (exception) { error.value = exception.message; }
}
onMounted(async () => {
  try {
    await loadConversations();
    const requestedId = Number(route.query.conversation_id || 0);
    let initialId = conversations.value.some((item) => item.id === requestedId) ? requestedId : conversations.value[0]?.id;
    if (!initialId && route.query.student_id) {
      await openContacts();
      const contact = contactGroups.value.flatMap((group) => group.items || []).find((item) => item.user_id === Number(route.query.student_id));
      if (contact) { await startConversation(contact); return; }
    }
    if (initialId) await selectConversation(initialId, false);
  } catch (exception) { error.value = exception.message; }
});
</script>

<style scoped>
.new-conversation{min-height:42px;padding:0 18px;border:0}.teacher-message-layout{display:grid;grid-template-columns:320px minmax(0,1fr);gap:14px;min-height:650px}.conversation-list,.conversation-thread{min-width:0;overflow:hidden}.conversation-list>header button{color:#287381;background:transparent}.conversation-list>div>button{position:relative;width:100%;display:grid;grid-template-columns:38px minmax(0,1fr) auto;gap:10px;padding:14px;text-align:left;color:#33302b;border:0;border-bottom:1px solid rgba(46, 125, 140, 0.1);background:transparent;transition:background .2s ease}.conversation-list>div>button:hover,.conversation-list>div>button.active{background:rgba(46, 125, 140, 0.09)}.conversation-list>div>button.active{box-shadow:inset 3px 0 #2e7d8c}.conversation-list i{width:38px;height:38px;display:grid;place-items:center;font-style:normal;color:#ffffff;background:#2e7d8c}.conversation-list span{min-width:0;display:grid;gap:2px}.conversation-list small,.conversation-list p{color:#706b62}.conversation-list p{margin:4px 0 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.conversation-list b{min-width:20px;height:20px;display:grid;place-items:center;color:white;background:#b4554a;font-size:11px}.conversation-loading{display:grid;gap:1px}.conversation-loading span{height:70px;background:linear-gradient(90deg,#ffffff,#e7e0d5,#ffffff);background-size:220% 100%;animation:pulse 1.2s linear infinite}.conversation-thread{display:grid;grid-template-rows:auto minmax(0,1fr) auto}.conversation-thread>header a{color:#287381}.thread-messages{height:500px;overflow-y:auto;display:flex;flex-direction:column;gap:10px;padding:18px}.load-earlier{align-self:center;min-height:32px;padding:0 12px;color:#706b62;border:1px solid rgba(46, 125, 140, 0.18);background:#ffffff}.conversation-empty{min-height:620px;display:grid;place-content:center;justify-items:center;color:#706b62}.conversation-empty span{font-size:42px}.conversation-empty strong{color:#33302b}.conversation-empty button{min-height:38px;padding:0 14px;color:#ffffff;border:0;background:#2e7d8c;font-weight:800}.teacher-inline-empty p{margin:6px 0 0;color:#706b62;line-height:1.6}@keyframes pulse{to{background-position:220% 0}}@media(max-width:860px){.teacher-message-layout{grid-template-columns:1fr;min-height:0}.conversation-list{max-height:330px;overflow-y:auto}.thread-messages{height:460px}}@media(max-width:520px){.conversation-empty{min-height:440px}}
</style>
