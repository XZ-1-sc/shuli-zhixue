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
            <span>{{ currentDateLabel }}</span>
          </div>
          <section class="today-ai-advice">
            <span aria-hidden="true">✦</span>
            <div><small>今日 AI 建议</small><strong>{{ todayAdvice.title }}</strong><p>{{ todayAdvice.text }}</p></div>
            <button type="button" @click="askXiaoluo">问小逻</button>
          </section>
          <ol v-if="!hasRecords" class="student-onboarding-steps" aria-label="建立个性化学习计划的三个步骤"><li><b>1</b><span>选择当前阶段</span></li><li><b>2</b><span>完成基础首测</span></li><li><b>3</b><span>查看个人计划</span></li></ol>
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
      <HeatmapCalendar class="dashboard-learning-insights" :calendar="insights.calendar || []" :trend="insights.mastery_trend || []" />
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRouter } from "vue-router";

import RadarChart from "../components/RadarChart.vue";
import HeatmapCalendar from "../components/ui/HeatmapCalendar.vue";
import { apiGet, apiPost } from "../api/client";
import { useUserStore } from "../stores/user";

const emit = defineEmits(["open-auth"]);
const user = useUserStore();
const router = useRouter();
const stages = ref([]);
const tasks = ref([]);
const diagnosis = ref({});
const profile = ref({});
const insights = ref({ calendar: [], mastery_trend: [] });
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
  if (!radar.length || !hasRecords.value) {
    return 0;
  }
  return Math.max(1, Math.round(radar.reduce((sum, item) => sum + Number(item.score || 0), 0) / radar.length));
});

const recordCount = computed(() => Math.max(
  Number(diagnosis.value.recent_record_count || 0),
  Number(profile.value.stats?.practice_count || 0)
));
const hasRecords = computed(() => recordCount.value > 0);
const answeredCount = computed(() => recordCount.value);
const studyHours = computed(() => Number(profile.value.stats?.study_hours || 0).toFixed(1));
const currentDateLabel = computed(() => {
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    weekday: "short"
  }).formatToParts(new Date());
  const dateParts = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `▣ ${dateParts.year}-${dateParts.month}-${dateParts.day}（${dateParts.weekday}）`;
});
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
const todayAdvice = computed(() => {
  if (!hasRecords.value) return { title: "先完成数学基础首测", text: "用一组混合题建立真实基线，小逻才能生成可靠的学习建议。" };
  const first = tasks.value?.[0];
  const weak = weakCourses.value?.[0];
  return { title: first?.title || `${weak?.fine_tag || weak?.knowledge_tag || "薄弱知识点"} 巩固`, text: weak ? `优先处理 ${weak.course} 的“${weak.fine_tag || weak.knowledge_tag}”，做题后立即复盘错因。` : "保持当前节奏，完成一组变式题验证迁移能力。" };
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
function askXiaoluo() { window.dispatchEvent(new CustomEvent("xiaoluo:open", { detail: { prompt: "请结合我的今日推荐、薄弱点和学习目标，告诉我今天怎么安排最有效。", context: { type: "plan" }, autoSend: true } })); }

async function load() {
  const stageData = await apiGet("/api/stages").catch(() => ({ stages: [] }));
  stages.value = stageData.stages || [];
  if (!user.userId) {
    diagnosis.value = { recent_record_count: 0, radar: [], weak_points: [], course_scores: [] };
    tasks.value = [];
    profile.value = {};
    insights.value = { calendar: [], mastery_trend: [] };
    Object.assign(goal, {
      target_stage: "大一",
      target_course: "高等数学上",
      weekly_hours: 8,
      exam_date: ""
    });
    syncCourseToStage();
    return;
  }
  const requests = {
    goal: apiGet("/api/user-goals").catch(() => ({})),
    diagnosis: apiGet("/api/diagnose").catch(() => ({ recent_record_count: 0, radar: [], weak_points: [], course_scores: [] })),
    recommendation: apiGet("/api/recommend", { limit: 5 }).catch(() => ({ tasks: [] })),
    profile: apiGet("/api/profile/summary").catch(() => ({})),
    insights: apiGet("/api/learning-insights").catch(() => ({ calendar: [], mastery_trend: [] }))
  };
  profile.value = await requests.profile;
  const [goalData, diagnoseData, recommendData, insightData] = await Promise.all([
    requests.goal,
    requests.diagnosis,
    requests.recommendation,
    requests.insights
  ]);
  Object.assign(goal, {
    target_stage: goalData.target_stage || "大一",
    target_course: goalData.target_course || "高等数学上",
    weekly_hours: goalData.weekly_hours || 8,
    exam_date: goalData.exam_date || ""
  });
  diagnosis.value = diagnoseData;
  tasks.value = recommendData.tasks || [];
  insights.value = insightData;
  syncCourseToStage();
}

onMounted(load);
watch(() => user.userId, load);
</script>

<style scoped src="../styles/views/dashboard.css"></style>
