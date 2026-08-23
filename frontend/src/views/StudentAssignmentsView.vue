<template>
  <section class="student-assignment-page student-page">
    <PageHeader title="我的作业" eyebrow="课程任务" description="查看教师发布的作业、截止时间和批改结果。" />
    <div v-if="loading" class="student-assignment-loading">正在同步作业...</div>
    <section v-else-if="error" class="student-assignment-empty">
      <h2>作业暂时无法加载</h2>
      <p>{{ error }}</p>
      <button type="button" @click="load">重试</button>
    </section>
    <EmptyState v-else-if="!items.length" title="暂时没有新作业" description="加入班级后，教师发布的任务会自动出现在这里。">
      <template #actions><RouterLink to="/">返回学习中控台</RouterLink></template>
    </EmptyState>
    <section v-else class="student-assignment-list">
      <RouterLink v-for="item in items" :key="item.id" :to="`/assignments/${item.id}`">
        <header><span>{{ item.class_name }} · {{ item.teacher_name }}</span><em :class="`status-${item.attempt_status}`">{{ statusText(item.attempt_status) }}</em></header>
        <h2>{{ item.title }}</h2>
        <p>{{ item.description || "按要求完成全部题目后提交。" }}</p>
        <dl><div><dt>题目</dt><dd>{{ item.question_count }}</dd></div><div><dt>已答</dt><dd>{{ item.answered_count }}</dd></div><div><dt>总分</dt><dd>{{ item.max_score }}</dd></div><div><dt>得分</dt><dd>{{ item.attempt_score ?? "-" }}</dd></div></dl>
        <footer><span :class="{ overdue: item.overdue }">{{ item.due_at ? `${item.overdue ? "已逾期" : "截止"} ${formatTime(item.due_at)}` : "不限截止时间" }}</span><b>{{ actionText(item) }} →</b></footer>
      </RouterLink>
    </section>
  </section>
</template>
<script setup>
import EmptyState from "../components/ui/EmptyState.vue";
import PageHeader from "../components/ui/PageHeader.vue";
import{onMounted,ref}from"vue";import{RouterLink}from"vue-router";import{apiGet}from"../api/client";const loading=ref(true),error=ref(""),items=ref([]);function statusText(v){return({not_started:"未开始",in_progress:"进行中",submitted:"已提交",grading:"批改中",graded:"已评分",returned:"待订正"})[v]||v;}function actionText(i){if(i.attempt_status==='not_started')return'开始作业';if(i.attempt_status==='in_progress')return'继续作答';if(i.attempt_status==='returned')return'开始订正';if(i.attempt_status==='graded'&&Number(i.attempt_no||1)<Number(i.max_attempts||1))return'再次作答';return'查看结果';}function formatTime(v){return new Date(v).toLocaleString("zh-CN");}async function load(){loading.value=true;try{items.value=(await apiGet("/api/assignments")).items||[];}catch(e){error.value=e.message;}finally{loading.value=false;}}onMounted(load);
</script>
