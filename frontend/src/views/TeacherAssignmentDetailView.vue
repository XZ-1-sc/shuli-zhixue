<template>
  <section class="teacher-view">
    <PageHeader :title="detail.assignment?.title || '作业进度'" eyebrow="作业进度" :description="detail.assignment ? `${detail.assignment.class_name} · ${detail.questions.length} 道题 · ${detail.assignment.total_score} 分` : '正在加载作业'">
      <template #actions>
        <button v-if="submittedCount" class="teacher-primary-action" type="button" :disabled="reportLoading" @click="openAiReport">{{ reportLoading ? "分析中…" : "✦ AI 分析报告" }}</button>
        <RouterLink class="teacher-secondary-action" to="/teacher/assignments">← 返回列表</RouterLink>
        <RouterLink v-if="detail.assignment?.status === 'draft'" class="teacher-secondary-action" :to="`/teacher/assignments/${detail.assignment.id}/edit`">编辑草稿</RouterLink>
        <button v-if="detail.assignment?.status === 'draft'" class="teacher-primary-action" @click="publish">发布作业</button>
        <button v-if="detail.assignment?.status === 'published'" class="teacher-secondary-action" @click="closeAssignment">结束作业</button>
        <button v-if="['draft', 'closed'].includes(detail.assignment?.status)" class="teacher-secondary-action danger" @click="archiveAssignment">归档</button>
      </template>
    </PageHeader>
    <p v-if="reportError" class="teacher-form-message is-error">{{ reportError }}</p>
    <div v-if="loading" class="teacher-loading-grid"><i v-for="n in 8" :key="n"></i></div>
    <section v-else-if="error" class="teacher-state-panel is-error"><strong>作业详情加载失败</strong><p>{{ error }}</p><button @click="load">重试</button></section>
    <template v-else>
      <section class="teacher-metric-grid teacher-four-metrics">
        <article><span class="metric-icon cyan">▤</span><div><small>题目</small><strong>{{ detail.questions.length }}</strong><p>总分 {{ detail.assignment.total_score }}</p></div></article>
        <article><span class="metric-icon blue">♙</span><div><small>班级学生</small><strong>{{ detail.students.length }}</strong><p>{{ detail.assignment.class_name }}</p></div></article>
        <article><span class="metric-icon green">✓</span><div><small>已提交</small><strong>{{ submittedCount }}</strong><p>提交率 {{ submitRate }}%</p></div></article>
        <article><span class="metric-icon amber">✎</span><div><small>待批改</small><strong>{{ pendingCount }}</strong><p>图片或主观作答</p></div></article>
      </section>
      <section class="teacher-detail-grid teacher-assignment-detail-grid">
        <article class="teacher-panel">
          <header><div><strong>学生完成情况</strong><small>按提交状态查看</small></div></header>
          <div class="teacher-table-wrap"><table><thead><tr><th>学生</th><th>状态</th><th>已答</th><th>得分</th><th>待批改</th><th>提交时间</th><th>操作</th></tr></thead><tbody><tr v-for="item in detail.students" :key="item.id"><td><i>{{ item.username.slice(0, 1) }}</i><strong>{{ item.username }}</strong></td><td><span :class="item.status === 'graded' ? 'normal' : item.status ? 'warn' : ''">{{ statusText(item.status) }}</span></td><td>{{ item.answered_count }}/{{ detail.questions.length }}</td><td>{{ item.total_score ?? '-' }}/{{ item.max_score }}</td><td>{{ item.pending_review }}</td><td>{{ formatTime(item.submitted_at) }}</td><td class="teacher-row-actions"><RouterLink :to="`/teacher/students/${item.id}`">学情</RouterLink><RouterLink v-if="item.pending_review" :to="`/teacher/review?assignment_id=${detail.assignment.id}`">批改</RouterLink></td></tr></tbody></table></div>
        </article>
        <article class="teacher-panel">
          <header><div><strong>试卷结构</strong><small>题目顺序与分值</small></div></header>
          <div class="teacher-mini-list teacher-paper-outline"><div v-for="item in detail.questions" :key="item.id"><b>{{ item.sort_order }}</b><span><strong>{{ item.question_text }}</strong><small>{{ item.type_label }} · {{ item.knowledge_tag }}</small></span><em>{{ item.points }} 分</em></div></div>
        </article>
      </section>
      <AssignmentAnalytics scope="assignment" :scope-id="Number(route.params.assignmentId)" />
      <AssignmentIntelligence :assignment-id="Number(route.params.assignmentId)" />
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { apiGet, apiPost } from "../api/client";
import AssignmentAnalytics from "../components/teacher/AssignmentAnalytics.vue";
import AssignmentIntelligence from "../components/teacher/AssignmentIntelligence.vue";
import PageHeader from "../components/ui/PageHeader.vue";
import { requestConfirmation } from "../services/confirm";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const error = ref("");
const reportLoading = ref(false);
const reportError = ref("");
const detail = ref({ assignment: null, questions: [], students: [] });
const submittedCount = computed(() => detail.value.students.filter((item) => ["submitted", "grading", "graded", "returned"].includes(item.status)).length);
const pendingCount = computed(() => detail.value.students.reduce((sum, item) => sum + item.pending_review, 0));
const submitRate = computed(() => detail.value.students.length ? Math.round(submittedCount.value / detail.value.students.length * 100) : 0);

function statusText(value) { return ({ in_progress: "进行中", submitted: "已提交", grading: "批改中", graded: "已评分", returned: "需订正" })[value] || "未开始"; }
function formatTime(value) { return value ? new Date(value).toLocaleString("zh-CN") : "-"; }
async function load() { loading.value = true; error.value = ""; try { detail.value = await apiGet(`/api/teacher/assignments/${route.params.assignmentId}`); } catch (exception) { error.value = exception.message; } finally { loading.value = false; } }
async function openAiReport() { reportLoading.value = true; reportError.value = ""; try { const data = await apiPost("/api/teacher/ai/assignment-report", { assignment_id: Number(route.params.assignmentId) }); window.dispatchEvent(new CustomEvent("xiaoluo:open", { detail: { card: data.card, prompt: "请结合这份作业报告，给出下一节课的教学安排。", autoSend: true } })); } catch (exception) { reportError.value = exception.message; } finally { reportLoading.value = false; } }
async function publish() { await apiPost(`/api/teacher/assignments/${route.params.assignmentId}/publish`); load(); }
async function closeAssignment() { if (await requestConfirmation({ title: "结束作业", description: "结束后学生不能继续提交，确定吗？", confirmLabel: "确认结束" })) { await apiPost(`/api/teacher/assignments/${route.params.assignmentId}/close`); load(); } }
async function archiveAssignment() { if (await requestConfirmation({ title: "归档作业", description: "归档后将从默认列表隐藏，确定吗？", confirmLabel: "确认归档" })) { await apiPost(`/api/teacher/assignments/${route.params.assignmentId}/archive`); router.push("/teacher/assignments"); } }
onMounted(load);
</script>
