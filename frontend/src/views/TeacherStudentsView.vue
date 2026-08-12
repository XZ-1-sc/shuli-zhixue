<template>
  <TeacherPageShell active="students" title="学生学情" eyebrow="数据驱动教学" description="查看练习、正确率、学习时长与作业完成情况，快速定位需要帮助的学生。">
    <template #actions><RouterLink class="teacher-secondary-action" to="/teacher/classes">管理班级成员</RouterLink></template>

    <section class="teacher-filter-bar">
      <label><span>班级</span><select v-model="filters.class_id" @change="loadStudents"><option value="">全部班级</option><option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
      <label class="teacher-search-field"><span>搜索学生</span><input v-model="filters.search" placeholder="输入用户名或昵称" @keyup.enter="loadStudents" /></label>
      <button class="teacher-primary-action" type="button" @click="loadStudents">查询</button>
    </section>

    <div v-if="loading" class="teacher-loading-grid"><i v-for="n in 6" :key="n"></i></div>
    <section v-else-if="error" class="teacher-state-panel is-error"><strong>学生学情加载失败</strong><p>{{ error }}</p><button @click="initialize">重试</button></section>
    <section v-else-if="!students.length" class="teacher-empty-onboarding"><div class="empty-compass">Σ</div><small>暂无学生数据</small><h2>先把学生加入班级</h2><p>学生使用学生账号注册后，可在班级管理中按用户名添加。完成练习后，这里会自动形成学情。</p><RouterLink to="/teacher/classes">前往班级管理</RouterLink></section>
    <section v-else class="teacher-panel">
      <header><div><strong>学生列表</strong><small>共 {{ students.length }} 名学生</small></div><span>点击学生查看完整档案</span></header>
      <div class="teacher-table-wrap teacher-student-table"><table>
        <thead><tr><th>学生</th><th>所在班级</th><th>练习量</th><th>正确率</th><th>学习时长</th><th>作业</th><th>待批改</th><th>最近学习</th><th>操作</th></tr></thead>
        <tbody><tr v-for="student in students" :key="student.id">
          <td><i>{{ student.username.slice(0, 1) }}</i><div><strong>{{ student.nickname }}</strong><small>@{{ student.username }}</small></div></td>
          <td>{{ student.class_names }}</td><td>{{ student.practice_count }} 题</td>
          <td><b :class="tone(student.accuracy)">{{ student.accuracy }}%</b></td><td>{{ student.study_hours }} h</td><td>{{ student.assignment_count }} 份</td>
          <td><span :class="student.pending_review ? 'warn' : 'normal'">{{ student.pending_review }}</span></td><td>{{ formatTime(student.last_active) }}</td>
          <td class="teacher-row-actions"><RouterLink :to="`/teacher/students/${student.id}`">详情</RouterLink><RouterLink :to="`/teacher/preview/${student.id}`">预览</RouterLink></td>
        </tr></tbody>
      </table></div>
    </section>
  </TeacherPageShell>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import { apiGet } from "../api/client";
import TeacherPageShell from "../components/TeacherPageShell.vue";

const loading = ref(true); const error = ref(""); const classes = ref([]); const students = ref([]);
const filters = reactive({ class_id: "", search: "" });
function tone(v) { return v >= 80 ? "is-good" : v >= 60 ? "is-medium" : "is-weak"; }
function formatTime(v) { return v ? new Date(v).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "未开始"; }
async function loadStudents() { loading.value = true; error.value = ""; try { const data = await apiGet("/api/teacher/students", filters); students.value = data.items || []; } catch (e) { error.value = e.message; } finally { loading.value = false; } }
async function initialize() { try { const data = await apiGet("/api/teacher/classes"); classes.value = data.items || []; await loadStudents(); } catch (e) { loading.value = false; error.value = e.message; } }
onMounted(initialize);
</script>
