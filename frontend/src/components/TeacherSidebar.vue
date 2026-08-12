<template>
  <aside class="teacher-sidebar">
    <RouterLink class="teacher-brand" to="/teacher">
      <span>Σ</span><strong>数理智学</strong>
    </RouterLink>
    <section class="teacher-profile-mini">
      <i>{{ initial }}</i>
      <div><strong>{{ user.username }}</strong><small>大学数学教学工作台</small><span>教师</span></div>
    </section>
    <nav aria-label="教师端导航">
      <RouterLink v-for="item in navItems" :key="item.key" :to="item.to" :class="{ active: active === item.key }">
        <span>{{ item.icon }}</span><strong>{{ item.label }}</strong>
      </RouterLink>
    </nav>
    <footer><span>安全会话已启用</span><small>班级、题目与作答均按教师权限隔离</small></footer>
  </aside>
</template>

<script setup>
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { useUserStore } from "../stores/user";

defineProps({ active: { type: String, default: "dashboard" } });
const user = useUserStore();
const initial = computed(() => user.username.slice(0, 1));
const navItems = [
  { key: "dashboard", to: "/teacher", icon: "⌂", label: "工作台" },
  { key: "classes", to: "/teacher/classes", icon: "▦", label: "班级管理" },
  { key: "students", to: "/teacher/students", icon: "♙", label: "学生学情" },
  { key: "questions", to: "/teacher/questions", icon: "▤", label: "题库管理" },
  { key: "assignments", to: "/teacher/assignments", icon: "▧", label: "作业管理" },
  { key: "review", to: "/teacher/review", icon: "✓", label: "批改中心" }
];
</script>
