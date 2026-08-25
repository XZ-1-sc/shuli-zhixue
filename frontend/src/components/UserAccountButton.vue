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

<style scoped>
.account-menu { position: relative; display: inline-flex; justify-content: flex-end; }
.student-chip { min-height: 42px; display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 0 16px; color: #33302b; border: 1px solid rgba(100, 90, 70, 0.18); border-radius: 999px; background: rgba(255, 255, 255, 0.06); font-weight: 900; }
.student-chip span { width: 34px; height: 34px; display: grid; place-items: center; color: #3a362f; border-radius: 50%; background: #f2eee7; }
.account-trigger { min-width: 118px; cursor: pointer; white-space: nowrap; }
.account-trigger.is-login { color: #ffffff; border-color: rgba(46, 125, 140, 0.72); background: #2e7d8c; box-shadow: 0 12px 30px rgba(46, 125, 140, 0.16); }
.account-trigger b { color: rgba(51, 48, 43, 0.78); font-size: 14px; }
.account-popover { position: absolute; top: calc(100% + 10px); right: 0; z-index: 130; width: 220px; display: grid; gap: 8px; padding: 14px; border: 1px solid rgba(100, 90, 70, 0.22); border-radius: 12px; background: rgba(255, 255, 255, 0.94); box-shadow: 0 20px 54px rgba(90, 75, 50, 0.152); }
.account-popover strong { color: #33302b; font-size: 16px; }
.account-popover small { color: #706b62; line-height: 1.5; }
.account-popover button { min-height: 36px; color: #ffffff; border: 0; border-radius: 999px; background: #2e7d8c; font-weight: 900; cursor: pointer; }
@media (max-width: 720px) { .account-trigger { min-width: 42px; width: 42px; padding: 0; font-size: 0; } .account-trigger span { width: 32px; height: 32px; font-size: 13px; } .account-trigger b { display: none; } }
</style>
