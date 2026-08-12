<template>
  <section class="teacher-app-shell">
    <TeacherSidebar :active="active" />
    <main class="teacher-main">
      <header class="teacher-topbar">
        <div><span>教师端</span><b>/</b><strong>{{ title }}</strong></div>
        <div class="teacher-top-actions">
          <RouterLink class="teacher-class-switch" to="/teacher/classes">▦ 班级与成员</RouterLink>
          <UserAccountButton />
        </div>
      </header>
      <section class="teacher-content">
        <header class="teacher-page-heading">
          <div><small>{{ eyebrow }}</small><h1>{{ title }}</h1><p>{{ description }}</p></div>
          <div class="teacher-heading-actions"><slot name="actions" /></div>
        </header>
        <slot />
      </section>
    </main>
  </section>
</template>

<script setup>
import { RouterLink } from "vue-router";
import TeacherSidebar from "./TeacherSidebar.vue";
import UserAccountButton from "./UserAccountButton.vue";

defineProps({
  active: { type: String, required: true },
  title: { type: String, required: true },
  eyebrow: { type: String, default: "教学管理" },
  description: { type: String, default: "" }
});
</script>
