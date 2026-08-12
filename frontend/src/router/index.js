import { createRouter, createWebHistory } from "vue-router";

import AuthView from "../views/AuthView.vue";
import DashboardView from "../views/DashboardView.vue";
import KnowledgeView from "../views/KnowledgeView.vue";
import PracticeView from "../views/PracticeView.vue";
import ReviewView from "../views/ReviewView.vue";
import RoadmapView from "../views/RoadmapView.vue";
import SideFeatureView from "../views/SideFeatureView.vue";
import TeacherHomeView from "../views/TeacherHomeView.vue";
import TeacherClassesView from "../views/TeacherClassesView.vue";
import TeacherStudentsView from "../views/TeacherStudentsView.vue";
import TeacherStudentDetailView from "../views/TeacherStudentDetailView.vue";
import TeacherQuestionsView from "../views/TeacherQuestionsView.vue";
import TeacherQuestionEditorView from "../views/TeacherQuestionEditorView.vue";
import TeacherAssignmentsView from "../views/TeacherAssignmentsView.vue";
import TeacherAssignmentEditorView from "../views/TeacherAssignmentEditorView.vue";
import TeacherAssignmentDetailView from "../views/TeacherAssignmentDetailView.vue";
import TeacherReviewView from "../views/TeacherReviewView.vue";
import StudentAssignmentsView from "../views/StudentAssignmentsView.vue";
import StudentAssignmentView from "../views/StudentAssignmentView.vue";

const studentMeta = (title) => ({ title, requiresAuth: true, role: "student" });

const routes = [
  { path: "/auth", name: "auth", component: AuthView, meta: { title: "账号登录", hideAssistant: true } },
  { path: "/", name: "dashboard", component: DashboardView, meta: studentMeta("学习中控台") },
  { path: "/roadmap", name: "roadmap", component: RoadmapView, meta: studentMeta("完整学习规划") },
  { path: "/practice", name: "practice", component: PracticeView, meta: studentMeta("做题训练") },
  { path: "/knowledge", name: "knowledge", component: KnowledgeView, meta: studentMeta("知识图谱") },
  { path: "/review", name: "review", component: ReviewView, meta: studentMeta("错题复盘") },
  { path: "/messages", name: "messages", component: SideFeatureView, meta: studentMeta("消息中心") },
  { path: "/profile", name: "profile", component: SideFeatureView, meta: studentMeta("学习档案") },
  { path: "/achievements", name: "achievements", component: SideFeatureView, meta: studentMeta("成就徽章") },
  { path: "/resources", name: "resources", component: SideFeatureView, meta: studentMeta("资源中心") },
  { path: "/notebook", name: "notebook", component: SideFeatureView, meta: studentMeta("笔记本") },
  { path: "/settings", name: "settings", component: SideFeatureView, meta: studentMeta("设置中心") },
  { path: "/assignments", name: "student-assignments", component: StudentAssignmentsView, meta: studentMeta("我的作业") },
  { path: "/assignments/:assignmentId", name: "student-assignment", component: StudentAssignmentView, meta: studentMeta("完成作业") },
  {
    path: "/teacher",
    name: "teacher-home",
    component: TeacherHomeView,
    meta: { title: "教师工作台", requiresAuth: true, role: "teacher", hideAssistant: true }
  },
  {
    path: "/teacher/classes",
    name: "teacher-classes",
    component: TeacherClassesView,
    meta: { title: "班级管理", requiresAuth: true, role: "teacher", hideAssistant: true }
  },
  { path: "/teacher/students", name: "teacher-students", component: TeacherStudentsView, meta: { title: "学生学情", requiresAuth: true, role: "teacher", hideAssistant: true } },
  { path: "/teacher/students/:studentId", name: "teacher-student-detail", component: TeacherStudentDetailView, meta: { title: "学生详情", requiresAuth: true, role: "teacher", hideAssistant: true } },
  { path: "/teacher/preview/:studentId", name: "teacher-student-preview", component: TeacherStudentDetailView, meta: { title: "学生端只读预览", requiresAuth: true, role: "teacher", hideAssistant: true, preview: true } },
  { path: "/teacher/questions", name: "teacher-questions", component: TeacherQuestionsView, meta: { title: "题库管理", requiresAuth: true, role: "teacher", hideAssistant: true } },
  { path: "/teacher/questions/new", name: "teacher-question-new", component: TeacherQuestionEditorView, meta: { title: "新建题目", requiresAuth: true, role: "teacher", hideAssistant: true } },
  { path: "/teacher/questions/:questionId/edit", name: "teacher-question-edit", component: TeacherQuestionEditorView, meta: { title: "编辑题目", requiresAuth: true, role: "teacher", hideAssistant: true } },
  { path: "/teacher/assignments", name: "teacher-assignments", component: TeacherAssignmentsView, meta: { title: "作业管理", requiresAuth: true, role: "teacher", hideAssistant: true } },
  { path: "/teacher/assignments/new", name: "teacher-assignment-new", component: TeacherAssignmentEditorView, meta: { title: "布置作业", requiresAuth: true, role: "teacher", hideAssistant: true } },
  { path: "/teacher/assignments/:assignmentId/edit", name: "teacher-assignment-edit", component: TeacherAssignmentEditorView, meta: { title: "编辑作业", requiresAuth: true, role: "teacher", hideAssistant: true } },
  { path: "/teacher/assignments/:assignmentId", name: "teacher-assignment-detail", component: TeacherAssignmentDetailView, meta: { title: "作业进度", requiresAuth: true, role: "teacher", hideAssistant: true } },
  { path: "/teacher/review", name: "teacher-review", component: TeacherReviewView, meta: { title: "批改中心", requiresAuth: true, role: "teacher", hideAssistant: true } },
  { path: "/:pathMatch(.*)*", redirect: "/" }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

function storedUser() {
  const raw = localStorage.getItem("math_brain_current_user") || sessionStorage.getItem("math_brain_current_user");
  if (!raw) {
    return null;
  }
  try {
    const user = JSON.parse(raw);
    return { ...user, role: user.role || "student" };
  } catch (error) {
    localStorage.removeItem("math_brain_current_user");
    sessionStorage.removeItem("math_brain_current_user");
    return null;
  }
}

router.beforeEach((to) => {
  const user = storedUser();
  if (to.name === "auth" && user) {
    return user.role === "teacher" ? "/teacher" : "/";
  }
  if (!to.meta.requiresAuth) {
    return true;
  }
  if (!user) {
    return {
      name: "auth",
      query: { mode: "login", role: to.meta.role || "student", redirect: to.fullPath }
    };
  }
  if (to.meta.role && user.role !== to.meta.role) {
    return user.role === "teacher" ? "/teacher" : "/";
  }
  return true;
});

router.afterEach((to) => {
  document.title = `${to.meta.title || "学习"} - 数理智学`;
});

export default router;
