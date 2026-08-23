<template>
  <section class="student-page home-ref">
    <div class="dashboard-page-controls">
      <label class="stage-picker">
        <small>当前阶段</small>
        <select v-model="goal.target_stage" @change="syncCourseToStage">
          <option value="大一">大一 · 上学期</option>
          <option value="大二">大二 · 下学期</option>
          <option value="大三">大三 · 专业课</option>
          <option value="大四">大四 · 综合应用</option>
        </select>
      </label>
    </div>
      <section class="welcome-strip">
        <div>
          <h1>大学数学学习中控台</h1>
          <p>晚上好，同学！今天是持续进步的一天。</p>
        </div>
        <blockquote>数学是打开科学大门的钥匙。<br />伽利略</blockquote>
      </section>

      <section class="home-board">
        <article class="glass-panel stage-progress-card">
          <div class="panel-title">阶段进度 <span>ⓘ</span></div>
          <div class="stage-inner">
            <div class="stage-card-head">
              <h2>{{ goal.target_stage || "大一" }} · 高等数学基础</h2>
              <button type="button" @click="saveGoal">保存目标</button>
            </div>
            <div class="stage-progress-body">
              <div class="reference-ring" :style="{ '--progress': `${displayProgress}%` }">
                <strong>{{ displayProgress }}</strong>
                <span>%</span>
                <small>总体进度</small>
              </div>
              <dl class="stage-stats">
                <div>
                  <dt>已学知识点</dt>
                  <dd>{{ answeredCount }} <small>题</small></dd>
                </div>
                <div>
                  <dt>掌握程度</dt>
                  <dd>{{ masteryLabel }} <i></i></dd>
                </div>
                <div>
                  <dt>学习时长</dt>
                  <dd>{{ studyHours }} h</dd>
                </div>
                <div>
                  <dt>连续学习</dt>
                  <dd>{{ hasRecords ? "已开始" : "待首测" }}</dd>
                </div>
              </dl>
            </div>
            <div class="stage-target">
              <span>{{ hasRecords ? "本阶段目标" : "尚未首测" }}</span>
              <small>{{ hasRecords ? `距离阶段目标：${Math.max(0, 80 - displayProgress)}%` : "完成首测后生成个人进度" }}</small>
              <p>{{ hasRecords ? "完成 80% 知识点学习并达到良好掌握" : "当前账号还没有做题记录，系统不会展示模拟进度。" }}</p>
              <div class="target-bar"><i :style="{ width: `${displayProgress}%` }"></i></div>
              <b>{{ displayProgress }}%</b>
            </div>
          </div>
          <div class="quick-entry-row">
            <RouterLink to="/roadmap"><span>▣</span>学习规划<small>个性化学习路径</small></RouterLink>
            <RouterLink to="/knowledge"><span>⟡</span>知识图谱<small>可视化知识结构</small></RouterLink>
            <RouterLink to="/review"><span>▤</span>错题复盘<small>巩固薄弱知识点</small></RouterLink>
          </div>
        </article>

        <article class="glass-panel daily-practice-card">
          <div class="panel-title">
            今日练习
            <span>▣ 2024-05-18（周六）</span>
          </div>
          <div class="daily-list">
            <template v-if="displayTasks.length">
              <button
                v-for="(task, index) in displayTasks"
                :key="`${task.title}-${index}`"
                type="button"
                @click="startTask(task)"
              >
                <i :class="`tone-${index % 5}`">{{ task.icon }}</i>
                <span>
                  <strong>{{ task.title }}</strong>
                  <small>章节练习 · {{ task.question_count }} 题</small>
                </span>
                <em>{{ task.status }}</em>
                <b>›</b>
              </button>
            </template>
            <div v-else class="home-empty-state">
              <strong>今日练习还没生成</strong>
              <p>先做一组首测题，系统会根据正确率和耗时生成今天的练习任务。</p>
              <RouterLink to="/practice?mode=assessment&limit=12">开始首测 ›</RouterLink>
            </div>
          </div>
          <RouterLink class="full-practice-link" to="/practice">查看全部练习 ›</RouterLink>
        </article>

        <div class="right-dashboard-stack">
          <article class="glass-panel radar-reference-card">
            <div class="panel-title">
              知识图谱 <span>先修关系 ♧</span>
            </div>
            <RadarChart :items="diagnosis.radar || []" />
          </article>

          <article class="glass-panel weak-course-card">
            <div class="panel-title">薄弱课程 <RouterLink to="/review">查看全部 ›</RouterLink></div>
            <div class="weak-course-list">
              <div v-for="weak in weakCourses" :key="`${weak.course}-${weak.fine_tag}`">
                <span>⚠ {{ weak.fine_tag || weak.knowledge_tag }}</span>
                <small>掌握度 {{ weak.score }}%</small>
                <RouterLink :to="`/practice?stage=${weak.stage}&course=${weak.course}&knowledge_tag=${weak.knowledge_tag}&limit=10`">去提升</RouterLink>
                <i><b :style="{ width: `${weak.score}%` }"></b></i>
              </div>
              <div v-if="!weakCourses.length" class="weak-empty-row">
                <span>暂无薄弱课程</span>
                <small>完成首测后自动生成</small>
                <RouterLink to="/practice?mode=assessment&limit=12">去首测</RouterLink>
                <i><b style="width: 0%"></b></i>
              </div>
            </div>
            <p>{{ hasRecords ? "💡 建议优先处理最低掌握度知识点，做题后查看解析和错因。" : "完成首测后，小逻会根据真实记录给出补强建议。" }}</p>
          </article>
        </div>
      </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRouter } from "vue-router";

import RadarChart from "../components/RadarChart.vue";
import { apiGet, apiPost } from "../api/client";
import { useUserStore } from "../stores/user";

const emit = defineEmits(["open-auth"]);
const user = useUserStore();
const router = useRouter();
const stages = ref([]);
const tasks = ref([]);
const diagnosis = ref({});
const profile = ref({});
const goal = reactive({
  target_stage: "大一",
  target_course: "高等数学上",
  weekly_hours: 8,
  exam_date: ""
});


const fallbackTasks = [
  { title: "极限的概念与运算法则", course: "高等数学上", knowledge_tag: "极限与连续", question_count: 15, status: "未开始", icon: "▱" },
  { title: "函数的连续性", course: "高等数学上", knowledge_tag: "极限与连续", question_count: 12, status: "进行中 6/12", icon: "▧" },
  { title: "导数的定义及几何意义", course: "高等数学上", knowledge_tag: "导数", question_count: 10, status: "未开始", icon: "▤" },
  { title: "导数的四则运算", course: "高等数学上", knowledge_tag: "导数", question_count: 15, status: "未开始", icon: "▣" },
  { title: "定积分的概念", course: "高等数学上", knowledge_tag: "积分", question_count: 10, status: "未开始", icon: "▥" }
];

const stageCourses = computed(() => {
  const stage = stages.value.find((item) => item.stage_name === goal.target_stage);
  return stage?.courses || [];
});

const displayProgress = computed(() => {
  const radar = diagnosis.value.radar || [];
  if (!radar.length || !diagnosis.value.recent_record_count) {
    return 0;
  }
  return Math.max(1, Math.round(radar.reduce((sum, item) => sum + Number(item.score || 0), 0) / radar.length));
});

const hasRecords = computed(() => Number(diagnosis.value.recent_record_count || 0) > 0);
const answeredCount = computed(() => Number(profile.value.stats?.practice_count || diagnosis.value.recent_record_count || 0));
const studyHours = computed(() => Number(profile.value.stats?.study_hours || 0).toFixed(1));
const masteryLabel = computed(() => {
  if (!hasRecords.value) {
    return "待测评";
  }
  if (displayProgress.value >= 80) return "良好";
  if (displayProgress.value >= 50) return "中等";
  return "需补强";
});

const displayTasks = computed(() => {
  if (!hasRecords.value) {
    return [];
  }
  const normalized = (tasks.value || []).slice(0, 5).map((task, index) => ({
    ...task,
    title: task.title?.replace("巩固训练", "").trim() || fallbackTasks[index]?.title,
    status: index === 1 ? "进行中" : "未开始",
    icon: fallbackTasks[index]?.icon || "▤"
  }));
  return normalized;
});

const weakCourses = computed(() => {
  if (!hasRecords.value) {
    return [];
  }
  const weak = diagnosis.value.weak_points || [];
  return weak.slice(0, 3);
});

function syncCourseToStage() {
  if (!stageCourses.value.find((course) => course.course_name === goal.target_course)) {
    goal.target_course = stageCourses.value[0]?.course_name || "高等数学上";
  }
}

async function saveGoal() {
  if (!user.userId) {
    emit("open-auth");
    return;
  }
  const data = await apiPost("/api/user-goals", {
    target_stage: goal.target_stage,
    target_course: goal.target_course,
    weekly_hours: goal.weekly_hours,
    exam_date: goal.exam_date || null
  });
  Object.assign(goal, data);
}

function startTask(task) {
  router.push({
    path: "/practice",
    query: {
      mode: "daily",
      stage: task.stage || goal.target_stage,
      course: task.course || goal.target_course,
      knowledge_tag: task.knowledge_tag,
      limit: task.question_count || 8
    }
  });
}

async function load() {
  const stageData = await apiGet("/api/stages");
  stages.value = stageData.stages || [];
  if (!user.userId) {
    diagnosis.value = { recent_record_count: 0, radar: [], weak_points: [], course_scores: [] };
    tasks.value = [];
    profile.value = {};
    Object.assign(goal, {
      target_stage: "大一",
      target_course: "高等数学上",
      weekly_hours: 8,
      exam_date: ""
    });
    syncCourseToStage();
    return;
  }
  const [goalData, diagnoseData, recommendData, profileData] = await Promise.all([
    apiGet("/api/user-goals").catch(() => ({})),
    apiGet("/api/diagnose"),
    apiGet("/api/recommend", { limit: 5 }),
    apiGet("/api/profile/summary").catch(() => ({}))
  ]);
  Object.assign(goal, {
    target_stage: goalData.target_stage || "大一",
    target_course: goalData.target_course || "高等数学上",
    weekly_hours: goalData.weekly_hours || 8,
    exam_date: goalData.exam_date || ""
  });
  diagnosis.value = diagnoseData;
  tasks.value = recommendData.tasks || [];
  profile.value = profileData || {};
  syncCourseToStage();
}

onMounted(load);
watch(() => user.userId, load);
</script>

<style scoped src="../styles/views/dashboard.css"></style>
