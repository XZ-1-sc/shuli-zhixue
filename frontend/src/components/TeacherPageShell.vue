<template>
  <section class="teacher-app-shell">
    <TeacherSidebar :active="active" />
    <main class="teacher-main">
      <header class="teacher-topbar">
        <div><span>教师端</span><b>/</b><strong>{{ route.meta.title || "教学管理" }}</strong></div>
        <div class="teacher-top-actions">
          <RouterLink class="teacher-class-switch" to="/teacher/classes">▦ 班级与成员</RouterLink>
          <UserAccountButton />
        </div>
      </header>
      <section class="teacher-content">
        <slot />
      </section>
    </main>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { RouterLink, useRoute } from "vue-router";
import TeacherSidebar from "./TeacherSidebar.vue";
import UserAccountButton from "./UserAccountButton.vue";

const route = useRoute();
const active = computed(() => route.meta.navKey || "dashboard");
</script>
