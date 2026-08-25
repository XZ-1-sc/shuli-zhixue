<template>
  <div class="app-root">
    <RouterView v-slot="{ Component }">
      <StudentLayout v-if="route.meta.layout === 'student'">
        <component :is="Component" @open-auth="user.openAuth()" />
      </StudentLayout>
      <TeacherPageShell v-else-if="route.meta.layout === 'teacher'">
        <component :is="Component" @open-auth="user.openAuth()" />
      </TeacherPageShell>
      <component :is="Component" v-else @open-auth="user.openAuth()" />
    </RouterView>

    <XiaoluoAssistant v-if="showAssistant" :role="assistantRole" :notification-summary="notificationSummary" />
    <Toast />
    <ConfirmDialog />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterView, useRoute } from "vue-router";

import XiaoluoAssistant from "./components/XiaoluoAssistant.vue";
import StudentLayout from "./components/student/StudentLayout.vue";
import TeacherPageShell from "./components/TeacherPageShell.vue";
import ConfirmDialog from "./components/ui/ConfirmDialog.vue";
import Toast from "./components/ui/Toast.vue";
import { useUserStore } from "./stores/user";
import { apiGet, apiPost } from "./api/client";

const user = useUserStore();
const route = useRoute();
const assistantRole = computed(() => route.meta.assistantRole || user.role || "student");
const showAssistant = computed(
  () => user.isLoggedIn && ["student", "teacher"].includes(user.role) && route.meta.hideAssistant !== true
);
const notificationSummary = ref({ unread_count: 0, latest: null, activity: {}, preference: { notify_xiaoluo: true }, quiet_hours: false, should_nudge: false });
let notificationTimer = null;

async function refreshNotificationSummary({ greeting = false } = {}) {
  if (!showAssistant.value) return;
  if (greeting && user.role === "student" && route.path === "/") {
    await apiPost("/api/notifications/greeting", {}).catch(() => null);
  }
  notificationSummary.value = await apiGet("/api/notifications/summary").catch(() => notificationSummary.value);
}

function restartNotificationPolling() {
  if (notificationTimer) window.clearInterval(notificationTimer);
  notificationTimer = null;
  if (!showAssistant.value) return;
  refreshNotificationSummary({ greeting: true });
  notificationTimer = window.setInterval(() => refreshNotificationSummary(), 60000);
}

watch(() => [user.userId, user.role, route.path], restartNotificationPolling);
onMounted(() => {
  restartNotificationPolling();
  window.addEventListener("xiaoluo:notification-read", refreshNotificationSummary);
});
onUnmounted(() => {
  if (notificationTimer) window.clearInterval(notificationTimer);
  window.removeEventListener("xiaoluo:notification-read", refreshNotificationSummary);
});
</script>
