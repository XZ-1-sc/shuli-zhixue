<template>
  <div class="app-root">
    <RouterView v-slot="{ Component }">
      <component :is="Component" @open-auth="user.openAuth()" />
    </RouterView>

    <XiaoluoAssistant v-if="showAssistant" />
  </div>
</template>

<script setup>
import { computed } from "vue";
import { RouterView, useRoute } from "vue-router";

import XiaoluoAssistant from "./components/XiaoluoAssistant.vue";
import { useUserStore } from "./stores/user";

const user = useUserStore();
const route = useRoute();
const showAssistant = computed(() => user.isLoggedIn && user.role === "student" && route.meta.hideAssistant !== true);
</script>
