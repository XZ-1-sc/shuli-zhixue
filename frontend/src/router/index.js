import { createRouter, createWebHistory } from "vue-router";

const AuthView = () => import("../views/AuthView.vue");
const DashboardView = () => import("../views/DashboardView.vue");
const KnowledgeView = () => import("../views/KnowledgeView.vue");
const PracticeView = () => import("../views/PracticeView.vue");
const ReviewView = () => import("../views/ReviewView.vue");
const RoadmapView = () => import("../views/RoadmapView.vue");
const SideFeatureView = () => import("../views/SideFeatureView.vue");
const TeacherHomeView = () => import("../views/TeacherHomeView.vue");
const TeacherClassesView = () => import("../views/TeacherClassesView.vue");
const TeacherStudentsView = () => import("../views/TeacherStudentsView.vue");
const TeacherStudentDetailView = () => import("../views/TeacherStudentDetailView.vue");
const TeacherQuestionsView = () => import("../views/TeacherQuestionsView.vue");
const TeacherQuestionEditorView = () => import("../views/TeacherQuestionEditorView.vue");
const TeacherAssignmentsView = () => import("../views/TeacherAssignmentsView.vue");
const TeacherAssignmentEditorView = () => import("../views/TeacherAssignmentEditorView.vue");
const TeacherAssignmentDetailView = () => import("../views/TeacherAssignmentDetailView.vue");
const TeacherReviewView = () => import("../views/TeacherReviewView.vue");
const StudentAssignmentsView = () => import("../views/StudentAssignmentsView.vue");
const StudentAssignmentView = () => import("../views/StudentAssignmentView.vue");

const studentMeta = (title) => ({ title, requiresAuth: true, role: "student", layout: "student" });
const teacherMeta = (title, navKey, extra = {}) => ({
  title,
  navKey,
  requiresAuth: true,
  role: "teacher",
  hideAssistant: true,
  layout: "teacher",
  ...extra
});

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
    meta: teacherMeta("教师工作台", "dashboard")
  },
  {
    path: "/teacher/classes",
    name: "teacher-classes",
    component: TeacherClassesView,
    meta: teacherMeta("班级管理", "classes")
  },
  { path: "/teacher/students", name: "teacher-students", component: TeacherStudentsView, meta: teacherMeta("学生学情", "students") },
  { path: "/teacher/students/:studentId", name: "teacher-student-detail", component: TeacherStudentDetailView, meta: teacherMeta("学生详情", "students") },
  { path: "/teacher/preview/:studentId", name: "teacher-student-preview", component: TeacherStudentDetailView, meta: teacherMeta("学生端只读预览", "students", { preview: true }) },
  { path: "/teacher/questions", name: "teacher-questions", component: TeacherQuestionsView, meta: teacherMeta("题库管理", "questions") },
  { path: "/teacher/questions/new", name: "teacher-question-new", component: TeacherQuestionEditorView, meta: teacherMeta("新建题目", "questions") },
  { path: "/teacher/questions/:questionId/edit", name: "teacher-question-edit", component: TeacherQuestionEditorView, meta: teacherMeta("编辑题目", "questions") },
  { path: "/teacher/assignments", name: "teacher-assignments", component: TeacherAssignmentsView, meta: teacherMeta("作业管理", "assignments") },
  { path: "/teacher/assignments/new", name: "teacher-assignment-new", component: TeacherAssignmentEditorView, meta: teacherMeta("布置作业", "assignments") },
  { path: "/teacher/assignments/:assignmentId/edit", name: "teacher-assignment-edit", component: TeacherAssignmentEditorView, meta: teacherMeta("编辑作业", "assignments") },
  { path: "/teacher/assignments/:assignmentId", name: "teacher-assignment-detail", component: TeacherAssignmentDetailView, meta: teacherMeta("作业进度", "assignments") },
  { path: "/teacher/review", name: "teacher-review", component: TeacherReviewView, meta: teacherMeta("批改中心", "review") },
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
