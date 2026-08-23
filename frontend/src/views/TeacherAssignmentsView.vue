<template>
  <section class="teacher-view">
    <PageHeader title="作业管理" eyebrow="教学任务" description="从题库组卷、发布到班级，并实时查看提交和批改进度。">
    <template #actions><RouterLink class="teacher-primary-action" to="/teacher/assignments/new">＋ 布置新作业</RouterLink></template>
    </PageHeader>
    <section class="teacher-filter-bar"><label><span>班级</span><select v-model="filters.class_id" @change="load"><option value="">全部班级</option><option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label><span>状态</span><select v-model="filters.status" @change="load"><option value="">全部状态</option><option value="draft">草稿</option><option value="published">进行中</option><option value="closed">已结束</option></select></label><button class="teacher-primary-action" @click="load">刷新</button></section>
    <div v-if="loading" class="teacher-loading-grid"><i v-for="n in 6" :key="n"></i></div><section v-else-if="error" class="teacher-state-panel is-error"><strong>作业列表加载失败</strong><p>{{ error }}</p><button @click="load">重试</button></section>
    <section v-else-if="!items.length" class="teacher-empty-onboarding"><div class="empty-compass">Σ</div><small>还没有作业</small><h2>从题库选择题目，发布第一份作业</h2><p>支持设置截止时间、限时、题目分值和提交后解析策略。</p><RouterLink to="/teacher/assignments/new">开始布置作业</RouterLink></section>
    <section v-else class="teacher-assignment-grid"><RouterLink v-for="item in items" :key="item.id" class="teacher-assignment-card" :to="`/teacher/assignments/${item.id}`"><header><span>{{ item.class_name }}</span><em :class="`status-${item.status}`">{{ statusText(item.status) }}</em></header><h2>{{ item.title }}</h2><p>{{ item.description || '未填写作业说明' }}</p><dl><div><dt>题目</dt><dd>{{ item.question_count }}</dd></div><div><dt>学生</dt><dd>{{ item.student_count }}</dd></div><div><dt>已提交</dt><dd>{{ item.submitted_count }}</dd></div><div><dt>待批改</dt><dd>{{ item.pending_review }}</dd></div></dl><footer><span>{{ item.due_at?`截止 ${formatTime(item.due_at)}`:'不限截止时间' }}</span><b>查看进度 →</b></footer></RouterLink></section>
  </section>
</template>
<script setup>
import{onMounted,reactive,ref}from"vue";import{RouterLink}from"vue-router";import{apiGet}from"../api/client";import PageHeader from "../components/ui/PageHeader.vue";
const loading=ref(true),error=ref(""),items=ref([]),classes=ref([]),filters=reactive({class_id:"",status:""});function statusText(v){return({draft:"草稿",published:"进行中",closed:"已结束"})[v]||v;}function formatTime(v){return new Date(v).toLocaleString("zh-CN");}async function load(){loading.value=true;error.value="";try{items.value=(await apiGet("/api/teacher/assignments",filters)).items||[];}catch(e){error.value=e.message;}finally{loading.value=false;}}onMounted(async()=>{try{classes.value=(await apiGet("/api/teacher/classes")).items||[];}finally{load();}});
</script>
