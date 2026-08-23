<template>
  <section class="teacher-view">
    <PageHeader :title="isPreview ? '学生端只读预览' : '学生学习档案'" :eyebrow="isPreview ? '只读观察模式' : '个体学情分析'" :description="isPreview ? '以学生视角查看当前数据，不会写入或修改任何学习记录。' : '从课程、薄弱知识点、近期练习和作业完成情况理解学生。'">
    <template #actions><RouterLink class="teacher-secondary-action" to="/teacher/students">← 返回学生列表</RouterLink><RouterLink v-if="!isPreview && profile.id" class="teacher-primary-action" :to="`/teacher/preview/${profile.id}`">学生端预览</RouterLink></template>
    </PageHeader>
    <div v-if="loading" class="teacher-loading-grid"><i v-for="n in 8" :key="n"></i></div>
    <section v-else-if="error" class="teacher-state-panel is-error"><strong>学生档案无法加载</strong><p>{{ error }}</p><button @click="load">重试</button></section>
    <template v-else>
      <aside v-if="isPreview" class="teacher-readonly-banner"><strong>只读预览</strong><span>你正在查看 {{ profile.nickname }} 的学习首页数据。所有操作入口已禁用。</span></aside>
      <section class="teacher-student-hero">
        <i>{{ profile.username?.slice(0, 1) }}</i><div><small>{{ profile.current_stage }} · {{ profile.class_names }}</small><h2>{{ profile.nickname }}</h2><p>@{{ profile.username }} · 最近学习 {{ formatTime(profile.last_active) }}</p></div>
        <dl><div><dt>练习量</dt><dd>{{ profile.practice_count }}<small>题</small></dd></div><div><dt>正确率</dt><dd>{{ profile.accuracy }}<small>%</small></dd></div><div><dt>学习时长</dt><dd>{{ profile.study_hours }}<small>h</small></dd></div></dl>
      </section>
      <section class="teacher-detail-grid">
        <article class="teacher-panel"><header><div><strong>课程掌握情况</strong><small>根据真实作答聚合</small></div></header><div v-if="data.courses.length" class="mastery-list"><div v-for="item in data.courses" :key="item.course"><span><b>{{ item.course }}</b><small>{{ item.attempts }} 次 · 错 {{ item.wrong_count }} 次</small></span><i><em :class="tone(item.accuracy)" :style="{ width: `${Math.max(item.accuracy, 3)}%` }"></em></i><strong>{{ item.accuracy }}%</strong></div></div><div v-else class="teacher-inline-empty">尚无做题数据。</div></article>
        <article class="teacher-panel"><header><div><strong>学习目标</strong><small>学生当前设置</small></div></header><dl v-if="data.goal" class="teacher-goal-list"><div><dt>目标阶段</dt><dd>{{ data.goal.target_stage }}</dd></div><div><dt>目标课程</dt><dd>{{ data.goal.target_course }}</dd></div><div><dt>每周时长</dt><dd>{{ data.goal.weekly_hours }} 小时</dd></div><div><dt>目标日期</dt><dd>{{ data.goal.exam_date || '未设置' }}</dd></div></dl><div v-else class="teacher-inline-empty">学生尚未设置学习目标。</div></article>
      </section>
      <section class="teacher-detail-grid">
        <article class="teacher-panel"><header><div><strong>薄弱知识点</strong><small>由低掌握度到高排序</small></div></header><div v-if="data.weak_points.length" class="teacher-weak-grid"><div v-for="item in data.weak_points" :key="`${item.course}-${item.fine_tag}`"><small>{{ item.course }}</small><strong>{{ item.fine_tag }}</strong><span>{{ item.knowledge_tag }} · {{ item.attempts }} 次</span><b :class="tone(item.mastery)">{{ item.mastery }}%</b></div></div><div v-else class="teacher-inline-empty">完成练习后生成薄弱点。</div></article>
        <article class="teacher-panel"><header><div><strong>作业进度</strong><small>已发布作业与提交状态</small></div></header><div v-if="data.assignments.length" class="teacher-mini-list"><div v-for="item in data.assignments" :key="item.id"><span><strong>{{ item.title }}</strong><small>{{ item.class_name }} · {{ item.due_at ? `截止 ${formatDate(item.due_at)}` : '不限时' }}</small></span><b :class="`status-${item.status || 'not_started'}`">{{ statusLabel(item.status) }}</b></div></div><div v-else class="teacher-inline-empty">暂无已发布作业。</div></article>
      </section>
      <section class="teacher-panel"><header><div><strong>近期学习记录</strong><small>最近 20 次练习与作业作答</small></div></header><div v-if="data.recent_records.length" class="teacher-table-wrap"><table><thead><tr><th>时间</th><th>课程</th><th>知识点</th><th>题型</th><th>模式</th><th>得分</th><th>状态</th></tr></thead><tbody><tr v-for="item in data.recent_records" :key="item.id"><td>{{ formatTime(item.answered_at) }}</td><td>{{ item.course }}</td><td>{{ item.fine_tag }}</td><td>{{ item.type_label }}</td><td>{{ item.practice_mode }}</td><td>{{ item.score ?? '待评' }}</td><td><span :class="item.review_status === 'pending' ? 'warn' : item.is_correct ? 'normal' : 'warn'">{{ item.review_status === 'pending' ? '待批改' : item.is_correct ? '正确' : '需巩固' }}</span></td></tr></tbody></table></div><div v-else class="teacher-inline-empty">暂无学习记录。</div></section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { apiGet } from "../api/client";
import PageHeader from "../components/ui/PageHeader.vue";
const route = useRoute(); const loading = ref(true); const error = ref(""); const data = ref({ profile: {}, goal: null, courses: [], weak_points: [], recent_records: [], assignments: [] });
const profile = computed(() => data.value.profile || {}); const isPreview = computed(() => route.meta.preview === true);
function tone(v) { return v >= 80 ? "is-good" : v >= 60 ? "is-medium" : "is-weak"; }
function formatTime(v) { return v ? new Date(v).toLocaleString("zh-CN") : "未开始"; } function formatDate(v) { return new Date(v).toLocaleDateString("zh-CN"); }
function statusLabel(v) { return ({ in_progress: "进行中", submitted: "已提交", grading: "批改中", graded: "已评分", returned: "需订正" })[v] || "未开始"; }
async function load() { loading.value = true; error.value = ""; try { data.value = await apiGet(`/api/teacher/students/${route.params.studentId}${isPreview.value ? '/preview' : ''}`); } catch (e) { error.value = e.message; } finally { loading.value = false; } }
onMounted(load);
</script>
