<template>
  <div class="account-menu" @keydown.escape="menuOpen = false">
    <button
      v-if="user.isLoggedIn"
      class="student-chip account-trigger"
      type="button"
      :aria-expanded="menuOpen"
      @click.stop="menuOpen = !menuOpen"
    >
      <span>{{ initial }}</span>
      {{ user.username }}
      <b>⌄</b>
    </button>
    <button v-else class="student-chip account-trigger is-login" type="button" @click="user.openAuth('login')">
      登录 / 注册
    </button>

    <div v-if="user.isLoggedIn && menuOpen" class="account-popover">
      <strong>{{ user.username }}</strong>
      <small>{{ user.role === "teacher" ? "教师账号 · 教学数据工作台" : "学生账号 · 学习数据已同步" }}</small>
      <button type="button" @click="logout">退出登录</button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { useUserStore } from "../stores/user";

const user = useUserStore();
const router = useRouter();
const menuOpen = ref(false);
const initial = computed(() => user.username.slice(0, 1).toUpperCase());

function closeFromOutside() {
  menuOpen.value = false;
}

async function logout() {
  await user.logout();
  menuOpen.value = false;
  await router.replace("/auth");
}

onMounted(() => {
  window.addEventListener("click", closeFromOutside);
});

onBeforeUnmount(() => {
  window.removeEventListener("click", closeFromOutside);
});
</script>
