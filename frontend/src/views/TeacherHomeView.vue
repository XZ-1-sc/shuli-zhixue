<template>
  <section class="teacher-app-shell">
    <TeacherSidebar active="dashboard" />

    <main class="teacher-main">
      <header class="teacher-topbar">
        <div><span>工作台</span><b>/</b><strong>教师工作台</strong></div>
        <div class="teacher-top-actions">
          <RouterLink class="teacher-class-switch" to="/teacher/classes">
            ▦ {{ selectedClass?.name || "创建第一个班级" }}
          </RouterLink>
          <UserAccountButton />
        </div>
      </header>

      <section class="teacher-content">
        <header class="teacher-page-heading">
          <div>
            <small>教学总览</small>
            <h1>教师工作台</h1>
            <p>掌握班级进度，及时发现需要帮助的学生。</p>
          </div>
          <div class="teacher-heading-actions">
            <RouterLink class="teacher-primary-action" to="/teacher/classes?create=1">＋ 创建班级</RouterLink>
            <RouterLink class="teacher-secondary-action" to="/teacher/assignments/new">布置作业</RouterLink>
          </div>
        </header>

        <div v-if="loading" class="teacher-loading-grid" aria-label="正在加载教师工作台">
          <i v-for="item in 8" :key="item"></i>
        </div>

        <section v-else-if="error" class="teacher-state-panel is-error">
          <strong>工作台暂时无法加载</strong>
          <p>{{ error }}</p>
          <button type="button" @click="loadOverview">重新加载</button>
        </section>

        <template v-else>
          <section class="teacher-metric-grid">
            <article>
              <span class="metric-icon cyan">▦</span>
              <div><small>班级</small><strong>{{ summary.class_count }}</strong><p>当前管理</p></div>
            </article>
            <article>
              <span class="metric-icon blue">♙</span>
              <div><small>学生</small><strong>{{ summary.student_count }}</strong><p>已加入班级</p></div>
            </article>
            <article>
              <span class="metric-icon green">↗</span>
              <div><small>今日活跃</small><strong>{{ summary.active_today }}</strong><p>今日有学习记录</p></div>
            </article>
            <article>
              <span class="metric-icon amber">✓</span>
              <div><small>平均正确率</small><strong>{{ summary.accuracy }}<em>%</em></strong><p>已自动评分记录</p></div>
            </article>
            <article>
              <span class="metric-icon red">▤</span>
              <div><small>待批改</small><strong>{{ summary.pending_review }}</strong><p>图片或主观答案</p></div>
            </article>
          </section>

          <section v-if="!summary.class_count" class="teacher-empty-onboarding">
            <div class="empty-compass">Σ</div>
            <small>从这里开始</small>
            <h2>创建班级，连接你的学生</h2>
            <p>创建后可按学生用户名添加成员，工作台会自动汇总练习量、正确率、活跃度与待批改答案。</p>
            <RouterLink to="/teacher/classes?create=1">创建第一个班级</RouterLink>
          </section>

          <template v-else>
            <section class="teacher-analytics-grid">
              <article class="teacher-panel teacher-trend-panel">
                <header><div><strong>班级学习趋势</strong><small>最近 7 天真实做题数据</small></div><span>活跃人数 / 正确率</span></header>
                <div class="teacher-line-chart">
                  <div class="chart-grid-lines"><i v-for="n in 5" :key="n"></i></div>
                  <svg viewBox="0 0 700 220" preserveAspectRatio="none" aria-label="最近七天学习趋势">
                    <polyline :points="activeLine" fill="none" stroke="#64d7e8" stroke-width="4" vector-effect="non-scaling-stroke" />
                    <polyline :points="accuracyLine" fill="none" stroke="#70e0aa" stroke-width="3" stroke-dasharray="8 7" vector-effect="non-scaling-stroke" />
                    <circle v-for="point in activePoints" :key="`a-${point.x}`" :cx="point.x" :cy="point.y" r="5" fill="#64d7e8" />
                    <circle v-for="point in accuracyPoints" :key="`r-${point.x}`" :cx="point.x" :cy="point.y" r="4" fill="#70e0aa" />
                  </svg>
                  <div class="chart-labels"><span v-for="item in overview.trend" :key="item.date">{{ item.label }}</span></div>
                </div>
              </article>

              <article class="teacher-panel teacher-mastery-panel">
                <header><div><strong>课程掌握度</strong><small>按学生已完成题目聚合</small></div></header>
                <div v-if="overview.course_mastery.length" class="mastery-list">
                  <div v-for="item in overview.course_mastery" :key="item.course">
                    <span><b>{{ item.course }}</b><small>{{ item.attempts }} 次作答</small></span>
                    <i><em :class="masteryTone(item.mastery)" :style="{ width: `${Math.max(item.mastery, 4)}%` }"></em></i>
                    <strong>{{ item.mastery }}%</strong>
                  </div>
                </div>
                <div v-else class="teacher-inline-empty">学生完成练习后，这里会出现课程掌握度。</div>
              </article>
            </section>

            <section class="teacher-bottom-grid">
              <article class="teacher-panel teacher-attention-panel">
                <header><div><strong>需要关注的学生</strong><small>按活跃度与正确率自动排序</small></div><RouterLink to="/teacher/students">查看学情</RouterLink></header>
                <div v-if="overview.attention_students.length" class="teacher-table-wrap">
                  <table>
                    <thead><tr><th>学生</th><th>练习量</th><th>正确率</th><th>最近学习</th><th>状态</th></tr></thead>
                    <tbody>
                      <tr v-for="student in overview.attention_students" :key="student.id" @click="$router.push(`/teacher/students/${student.id}`)">
                        <td><i>{{ student.username.slice(0, 1) }}</i><strong>{{ student.username }}</strong></td>
                        <td>{{ student.practice_count }} 题</td>
                        <td :class="masteryTone(student.accuracy)">{{ student.accuracy }}%</td>
                        <td>{{ formatTime(student.last_active) }}</td>
                        <td><span :class="student.accuracy && student.accuracy < 60 ? 'warn' : 'normal'">{{ student.practice_count ? (student.accuracy < 60 ? "需关注" : "正常") : "未开始" }}</span></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-else class="teacher-inline-empty">班级中还没有学生。</div>
              </article>

              <article class="teacher-panel teacher-activity-panel">
                <header><div><strong>最近学习动态</strong><small>成员最新作答记录</small></div></header>
                <div v-if="overview.recent_activity.length" class="teacher-activity-list">
                  <div v-for="(item, index) in overview.recent_activity" :key="`${item.username}-${index}`">
                    <i :class="item.is_correct ? 'success' : 'danger'">{{ item.is_correct ? "✓" : "!" }}</i>
                    <p><strong>{{ item.username }}</strong><span>{{ item.course }} · {{ item.knowledge_tag }}</span></p>
                    <time>{{ formatTime(item.answered_at) }}</time>
                  </div>
                </div>
                <div v-else class="teacher-inline-empty">暂无学生学习动态。</div>
              </article>
            </section>

            <section class="teacher-panel teacher-class-strip">
              <header><div><strong>我的班级</strong><small>点击进入成员管理</small></div><RouterLink to="/teacher/classes">全部班级</RouterLink></header>
              <div>
                <RouterLink v-for="item in overview.classes" :key="item.id" :to="`/teacher/classes?class_id=${item.id}`">
                  <small>{{ item.stage }} · {{ item.course }}</small>
                  <strong>{{ item.name }}</strong>
                  <span>{{ item.student_count }} 名学生 · 今日 {{ item.active_today }} 人活跃</span>
                  <b>进入班级 →</b>
                </RouterLink>
              </div>
            </section>
          </template>
        </template>
      </section>
    </main>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { apiGet } from "../api/client";
import TeacherSidebar from "../components/TeacherSidebar.vue";
import UserAccountButton from "../components/UserAccountButton.vue";

const loading = ref(true);
const error = ref("");
const overview = ref({
  summary: { class_count: 0, student_count: 0, active_today: 0, pending_review: 0, accuracy: 0 },
  classes: [], trend: [], course_mastery: [], attention_students: [], recent_activity: []
});

const summary = computed(() => overview.value.summary);
const selectedClass = computed(() => overview.value.classes[0]);

function linePoints(key, maxValue) {
  const items = overview.value.trend || [];
  return items.map((item, index) => ({
    x: items.length > 1 ? 30 + (index * 640) / (items.length - 1) : 350,
    y: 195 - (Math.min(Number(item[key]) || 0, maxValue) / maxValue) * 165
  }));
}

const activePoints = computed(() => {
  const max = Math.max(5, ...overview.value.trend.map((item) => item.active_students || 0));
  return linePoints("active_students", max);
});
const accuracyPoints = computed(() => linePoints("accuracy", 100));
const activeLine = computed(() => activePoints.value.map((p) => `${p.x},${p.y}`).join(" "));
const accuracyLine = computed(() => accuracyPoints.value.map((p) => `${p.x},${p.y}`).join(" "));

function masteryTone(value) {
  if (value >= 80) return "is-good";
  if (value >= 60) return "is-medium";
  return "is-weak";
}

function formatTime(value) {
  if (!value) return "暂无记录";
  const time = new Date(value);
  const today = new Date();
  if (time.toDateString() === today.toDateString()) return `今天 ${time.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
  return time.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

async function loadOverview() {
  loading.value = true;
  error.value = "";
  try {
    overview.value = await apiGet("/api/teacher/overview");
  } catch (requestError) {
    error.value = requestError.message || "教师数据接口暂时不可用。";
  } finally {
    loading.value = false;
  }
}

onMounted(loadOverview);
</script>
