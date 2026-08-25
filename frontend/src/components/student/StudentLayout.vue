<template>
  <section class="student-layout">
    <header class="ref-topbar">
      <RouterLink class="student-brand" to="/" aria-label="数理智学首页">
        <span>Σ</span>
        <strong>数理智学</strong>
      </RouterLink>
      <nav class="student-primary-nav" aria-label="学生端主导航">
        <RouterLink v-for="item in primaryNav" :key="item.to" :to="item.to">{{ item.label }}</RouterLink>
      </nav>
      <div class="student-account-area">
        <span class="student-stage">{{ currentStage }}</span>
        <UserAccountButton />
      </div>
    </header>

    <aside class="ref-sidebar">
      <nav class="student-side-nav" aria-label="学生端功能导航">
        <RouterLink v-for="item in mainSideNav" :key="item.to" :to="item.to">
          <span>{{ item.short }}</span>
          <strong>{{ item.label }}</strong>
        </RouterLink>
        <button class="student-more-button" type="button" :aria-expanded="moreOpen" @click="moreOpen = !moreOpen"><span>•••</span><strong>更多</strong></button>
      </nav>
      <nav v-if="moreOpen" class="student-more-nav" aria-label="更多学生端功能">
        <RouterLink v-for="item in moreSideNav" :key="item.to" :to="item.to" @click="moreOpen = false">{{ item.label }}</RouterLink>
      </nav>
      <section class="student-assessment-card">
        <small>建立学习基线</small>
        <strong>数学基础首测</strong>
        <p>完成混合题型测评，生成个人薄弱点与学习计划。</p>
        <RouterLink to="/practice?mode=assessment&limit=12">开始首测</RouterLink>
      </section>
    </aside>

    <main class="student-layout-main">
      <slot />
    </main>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";

import { useUserStore } from "../../stores/user";
import UserAccountButton from "../UserAccountButton.vue";

const user = useUserStore();
const currentStage = computed(() => user.user?.current_stage || "大一");
const moreOpen = ref(false);

const primaryNav = [
  { to: "/", label: "学习看板" },
  { to: "/roadmap", label: "学习规划" },
  { to: "/practice", label: "做题训练" },
  { to: "/knowledge", label: "知识图谱" },
  { to: "/review", label: "错题复盘" }
];

const mainSideNav = [
  { to: "/", label: "学习中控台", short: "控" },
  { to: "/messages", label: "消息中心", short: "信" },
  { to: "/profile", label: "学习档案", short: "档" },
  { to: "/notebook", label: "笔记本", short: "记" },
  { to: "/assignments", label: "我的作业", short: "业" }
];
const moreSideNav = [
  { to: "/achievements", label: "成就徽章" },
  { to: "/resources", label: "资源中心" },
  { to: "/settings", label: "设置中心", short: "设" }
];
</script>

<style scoped>
.student-layout {
  min-height: 100dvh;
  display: grid;
  grid-template-columns: 208px minmax(0, 1fr);
  grid-template-rows: 72px minmax(0, 1fr);
  color: #33302b;
  background: #f6f2e9;
}

.ref-topbar {
  position: sticky;
  top: 0;
  z-index: 40;
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: 208px minmax(0, 1fr) auto;
  align-items: center;
  min-width: 0;
  border-bottom: 1px solid rgba(46, 125, 140, 0.16);
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(16px);
}

.student-brand {
  height: 72px;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 0 20px;
  border-right: 1px solid rgba(46, 125, 140, 0.12);
  white-space: nowrap;
}

.student-brand span {
  width: 34px;
  height: 40px;
  display: grid;
  place-items: center;
  color: #287381;
  border: 1px solid rgba(46, 125, 140, 0.52);
  border-radius: 12px;
  font-size: 20px;
  font-weight: 900;
}

.student-brand strong { font-size: 18px; }

.student-primary-nav {
  min-width: 0;
  height: 72px;
  display: flex;
  align-items: stretch;
  gap: 4px;
  padding-left: 22px;
}

.student-primary-nav a {
  position: relative;
  display: grid;
  place-items: center;
  padding: 0 15px;
  color: #706b62;
  font-size: 14px;
  font-weight: 800;
  white-space: nowrap;
}

.student-primary-nav a.router-link-exact-active { color: #33302b; }
.student-primary-nav a.router-link-exact-active::after {
  content: "";
  position: absolute;
  right: 15px;
  bottom: 0;
  left: 15px;
  height: 2px;
  background: #2e7d8c;
}

.student-account-area {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 88px 0 20px;
}

.student-stage {
  padding: 8px 12px;
  color: #33302b;
  border: 1px solid rgba(46, 125, 140, 0.18);
  border-radius: 10px;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.ref-sidebar {
  position: sticky;
  top: 72px;
  grid-column: 1;
  grid-row: 2;
  height: calc(100dvh - 72px);
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 18px 12px;
  border-right: 1px solid rgba(46, 125, 140, 0.14);
  background: #ffffff;
  overflow: auto;
}

.student-side-nav { display: grid; align-content: start; gap: 5px; }
.student-side-nav a,
.student-more-button {
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 0 12px;
  color: #706b62;
  border-radius: 12px;
  font-size: 13px;
}
.student-more-button { width:100%; border:0; background:transparent; text-align:left; }
.student-side-nav a span,
.student-more-button span {
  width: 27px;
  height: 27px;
  display: grid;
  place-items: center;
  color: #287381;
  border: 1px solid rgba(46, 125, 140, 0.2);
  border-radius: 9px;
  font-size: 11px;
}
.student-more-nav { display:grid; gap:5px; padding:8px; border:1px solid rgba(46, 125, 140, 0.14); border-radius:12px; background:#ffffff; }
.student-more-nav a { padding:9px 10px; border-radius:8px; color:#33302b; font-size:12px; }
.student-more-nav a.router-link-exact-active { color:#33302b; background:rgba(46, 125, 140, 0.1); }
.student-side-nav a.router-link-exact-active {
  color: #33302b;
  background: rgba(46, 125, 140, 0.12);
}

.student-assessment-card {
  margin-top: auto;
  padding: 16px;
  border: 1px solid rgba(46, 125, 140, 0.22);
  border-radius: 14px;
  background: #ffffff;
}
.student-assessment-card small { color: #287381; }
.student-assessment-card strong { display: block; margin-top: 7px; }
.student-assessment-card p { margin: 8px 0 14px; color: #706b62; font-size: 12px; line-height: 1.6; }
.student-assessment-card a {
  min-height: 36px;
  display: grid;
  place-items: center;
  color: #ffffff;
  border-radius: 10px;
  background: #2e7d8c;
  font-size: 12px;
  font-weight: 900;
}

.student-layout-main { min-width: 0; grid-column: 2; grid-row: 2; overflow: clip; }

@media (max-width: 1280px) {
  .student-layout { grid-template-columns: 176px minmax(0, 1fr); }
  .ref-topbar { grid-template-columns: 176px minmax(0, 1fr) auto; }
  .student-brand strong { display: none; }
  .student-primary-nav a { padding: 0 10px; }
  .student-stage { display: none; }
  .student-account-area { padding: 0 76px 0 12px; }
}

@media (max-width: 760px) {
  .student-layout { display: block; padding: 62px 0 74px; }
  .ref-topbar {
    position: fixed;
    right: 0;
    left: 0;
    height: 62px;
    display: flex;
    justify-content: space-between;
  }
  .student-brand { height: 62px; padding: 0 14px; border: 0; }
  .student-brand strong { display: block; font-size: 16px; }
  .student-brand span { width: 30px; height: 34px; }
  .student-primary-nav { display: none; }
  .student-account-area { padding: 0 66px 0 12px; }
  .ref-sidebar {
    position: fixed;
    top: auto;
    right: 0;
    bottom: 0;
    left: 0;
    z-index: 38;
    width: auto;
    height: 66px;
    display: block;
    padding: 6px 8px;
    border: 0;
    border-top: 1px solid rgba(46, 125, 140, 0.18);
    background: rgba(255, 255, 255, 0.94);
  }
  .student-side-nav { display: grid; grid-template-columns: repeat(5, 1fr); gap: 2px; }
  .student-side-nav a { min-height: 54px; display: grid; place-items: center; gap: 2px; padding: 0; font-size: 10px; }
  .student-more-button { display:none; }
  .student-more-nav { display:none; }
  .student-side-nav a span { width: auto; height: auto; border: 0; font-size: 11px; }
  .student-assessment-card { display: none; }
  .student-layout-main { overflow: visible; }
}
</style>
