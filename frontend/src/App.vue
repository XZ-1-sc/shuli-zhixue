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

    <XiaoluoAssistant v-if="showAssistant" />
    <Toast />
    <ConfirmDialog />
  </div>
</template>

<script setup>
import { computed } from "vue";
import { RouterView, useRoute } from "vue-router";

import XiaoluoAssistant from "./components/XiaoluoAssistant.vue";
import StudentLayout from "./components/student/StudentLayout.vue";
import TeacherPageShell from "./components/TeacherPageShell.vue";
import ConfirmDialog from "./components/ui/ConfirmDialog.vue";
import Toast from "./components/ui/Toast.vue";
import { useUserStore } from "./stores/user";

const user = useUserStore();
const route = useRoute();
const showAssistant = computed(() => user.isLoggedIn && user.role === "student" && route.meta.hideAssistant !== true);
</script>
