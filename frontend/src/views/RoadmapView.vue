<template>
  <section class="student-page plan-main">
      <section class="plan-title-block">
        <p class="math-doodle">∫  d/dx  ∑  π²/6</p>
        <h1>完整学习规划</h1>
        <p>基于诊断测试结果，已为你生成个性化四年学习路线图</p>
        <div class="plan-title-actions"><button type="button">⇩ 导出学习规划</button><button type="button" @click="askXiaoluo">◉ 问小逻怎么安排</button></div>
      </section>

      <section class="plan-content-grid">
        <div class="stage-paper-board">
          <article v-for="(stage, index) in planStages" :key="stage.stage_name" class="stage-paper" :class="`paper-${index}`">
            <header>
              <span>{{ stage.stage_name }}</span>
              <h2>{{ stage.title }}</h2>
              <small>{{ stage.sub }}</small>
            </header>
            <div class="stage-line-node"></div>
            <div class="paper-course-list">
              <RouterLink
                v-for="course in stage.courses"
                :key="course.course_name"
                :class="{ done: course.state === '已完成', doing: course.state === '进行中' }"
                :to="`/practice?stage=${stage.stage_name}&course=${course.course_name}&limit=8`"
              >
                <span>▤</span>
                <strong>{{ course.course_name }}</strong>
                <small>{{ course.state }}</small>
              </RouterLink>
            </div>
            <footer>
              <strong>阶段目标</strong>
              <p>{{ stage.goal_text }}</p>
            </footer>
          </article>
        </div>

        <aside class="plan-right-stack">
          <article class="week-plan-card">
            <h3>▣ 本周计划 <span>每天 90 分钟</span></h3>
            <div v-for="item in weeklyPlan" :key="item.day" class="week-row">
              <b>{{ item.day }}</b>
              <span>{{ item.course }}<small>{{ item.task }}</small></span>
              <em>{{ item.minutes }} 分钟</em>
            </div>
          </article>

          <article class="priority-card">
            <h3>◎ 优先补强 <span>本周重点</span></h3>
            <strong>优先补强：极限、导数应用</strong>
            <p>根据首测得分线索，导数应用题型掌握不足。</p>
            <small>当前掌握度</small>
            <div><i style="width:45%"></i></div>
            <b>45%</b>
          </article>

          <article class="vertical-paper-note">
            <div>
              <strong>从薄弱点反推</strong>
              <p>先补基础缺口，再拓展相关知识，最后形成能力闭环。</p>
              <span>基础 → 理解 → 应用</span>
            </div>
          </article>
        </aside>
      </section>

      <section class="course-flow-map">
        <h3>课程依赖关系图谱</h3>
        <div class="flow-line">
          <RouterLink v-for="course in flowCourses" :key="course" :to="`/practice?course=${course}&limit=8`">{{ course }}</RouterLink>
        </div>
      </section>

      <footer class="plan-progress-footer">
        <div><span>整体进度</span><strong>18%</strong></div>
        <div><span>已完成课程</span><strong>2 / 18</strong></div>
        <div><span>进行中课程</span><strong>2</strong></div>
        <div><span>未开始课程</span><strong>14</strong></div>
        <div><span>已学知识点</span><strong>86 / 480</strong></div>
        <RouterLink to="/knowledge">查看能力雷达图</RouterLink>
      </footer>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { apiGet } from "../api/client";
const roadmap = ref({});


const planStages = computed(() => {
  const source = roadmap.value.stages || [];
  const fallback = [
    {
      stage_name: "大一",
      title: "基础建立",
      sub: "夯实基础，建立数学思维",
      goal_text: "掌握核心基础知识，建立扎实的数学脉络。",
      courses: ["高等数学（上）", "高等数学（下）", "线性代数（上）", "概率论与数理统计"]
    },
    {
      stage_name: "大二",
      title: "核心能力",
      sub: "强化能力，形成知识体系",
      goal_text: "完善分析与代数体系，提升抽象与证明能力。",
      courses: ["线性代数（下）", "复变函数", "实变函数", "数学分析选讲"]
    },
    {
      stage_name: "大三",
      title: "专业深化",
      sub: "拓展方向，深入专业领域",
      goal_text: "深入数学分支，培养解决复杂问题的能力。",
      courses: ["抽象代数", "拓扑学基础", "常微分方程", "泛函分析初步"]
    },
    {
      stage_name: "大四",
      title: "综合应用",
      sub: "综合应用，面向未来发展",
      goal_text: "将数学应用于实际问题，完成综合项目。",
      courses: ["数学建模", "数值分析", "随机过程", "毕业设计 / 论文"]
    }
  ];
  return (source.length ? source : fallback).slice(0, 4).map((stage, stageIndex) => ({
    ...stage,
    sub: stage.sub || fallback[stageIndex]?.sub,
    courses: (stage.courses || fallback[stageIndex]?.courses || []).slice(0, 4).map((course, index) => {
      const name = typeof course === "string" ? course : course.course_name;
      return {
        course_name: name,
        state: stageIndex === 0 && index === 0 ? "已完成" : stageIndex === 0 && index < 3 ? "进行中" : "未开始"
      };
    })
  }));
});

const weeklyPlan = computed(() => roadmap.value.weekly_plan || [
  { day: "周一", course: "高等数学（下）", task: "极限的概念与性质", minutes: 90 },
  { day: "周二", course: "线性代数（上）", task: "矩阵的运算", minutes: 90 },
  { day: "周三", course: "高等数学（下）", task: "导数与微分", minutes: 90 },
  { day: "周四", course: "概率论", task: "随机事件与概率", minutes: 90 },
  { day: "周五", course: "习题与总结", task: "本周错题复盘", minutes: 90 },
  { day: "周六", course: "拓展阅读", task: "数学思维训练", minutes: 60 },
  { day: "周日", course: "休息与回顾", task: "知识图谱整理", minutes: "休息" }
]);

const flowCourses = ["高等数学（上）", "高等数学（下）", "线性代数（上）", "概率论与数理统计", "复变函数", "实变函数", "抽象代数", "数学建模", "数值分析"];

function askXiaoluo() { window.dispatchEvent(new CustomEvent("xiaoluo:open", { detail: { prompt: "请结合我的当前学习规划、薄弱点和可用时间，帮我调整本周安排。", context: { type: "plan" }, autoSend: true } })); }

onMounted(async () => {
  roadmap.value = await apiGet("/api/study-roadmap");
});
</script>

<style scoped>
.plan-title-actions{display:flex;justify-content:center;gap:10px;flex-wrap:wrap}.plan-title-actions button+button{border-color:rgba(46, 125, 140, 0.4);color:#33302b;background:rgba(46, 125, 140, 0.08)}
</style>

<style scoped src="../styles/views/roadmap.css"></style>
