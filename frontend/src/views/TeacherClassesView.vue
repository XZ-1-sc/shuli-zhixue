<template>
  <section class="teacher-app-shell">
    <TeacherSidebar active="classes" />

    <main class="teacher-main">
      <header class="teacher-topbar">
        <div><RouterLink to="/teacher">工作台</RouterLink><b>/</b><strong>班级管理</strong></div>
        <UserAccountButton />
      </header>

      <section class="teacher-content">
        <header class="teacher-page-heading">
          <div><small>组织与成员</small><h1>班级管理</h1><p>创建课程班级，并按学生用户名添加已经注册的学生。</p></div>
          <button class="teacher-primary-action" type="button" @click="openCreate">＋ 创建班级</button>
        </header>

        <p v-if="pageError" class="teacher-form-message is-error">{{ pageError }}</p>

        <section v-if="loading" class="teacher-loading-grid"><i v-for="item in 6" :key="item"></i></section>
        <section v-else class="teacher-classes-layout">
          <aside class="teacher-class-list-panel">
            <header><strong>我的班级</strong><span>{{ classes.length }} 个</span></header>
            <div v-if="classes.length" class="teacher-class-list">
              <button v-for="item in classes" :key="item.id" :class="{ active: selectedClassId === item.id }" type="button" @click="selectClass(item.id)">
                <small>{{ item.stage }} · {{ item.course }}</small>
                <strong>{{ item.name }}</strong>
                <span><b>{{ item.student_count }}</b> 名学生 · 今日 {{ item.active_today }} 人活跃</span>
                <i>邀请码 {{ item.invite_code }}</i>
              </button>
            </div>
            <div v-else class="teacher-class-empty-small">
              <span>Σ</span><strong>还没有班级</strong><p>创建班级后即可添加学生。</p><button type="button" @click="openCreate">立即创建</button>
            </div>
          </aside>

          <article v-if="detail.class" class="teacher-class-detail-panel">
            <header class="class-detail-heading">
              <div>
                <small>{{ detail.class.stage }} · {{ detail.class.course }}</small>
                <h2>{{ detail.class.name }}</h2>
                <p>班级邀请码 <button type="button" @click="copyInvite">{{ detail.class.invite_code }} · 复制</button> <button type="button" @click="regenerateInvite">重新生成</button></p>
              </div>
              <div class="class-heading-side"><div class="class-detail-stats"><span><strong>{{ detail.student_count }}</strong>学生</span><span><strong>{{ classSummary.accuracy }}</strong>正确率</span><span><strong>{{ classSummary.practice }}</strong>练习</span></div><div class="teacher-row-actions"><button type="button" @click="exportMembers">导出名单</button><button type="button" @click="openEdit">编辑班级</button><button class="danger" type="button" @click="archiveClass">归档</button></div></div>
            </header>

            <form class="teacher-add-student-form" @submit.prevent="addStudent">
              <div><strong>添加学生</strong><small>学生需要先注册学生端账号，再由教师按用户名加入班级。</small></div>
              <label><span>学生用户名</span><input v-model.trim="studentUsername" maxlength="64" placeholder="例如：树虫" required /></label>
              <button :disabled="addingStudent || !studentUsername" type="submit">{{ addingStudent ? "正在添加..." : "添加到班级" }}</button>
            </form>
            <p v-if="memberMessage" class="teacher-form-message" :class="{ 'is-error': memberError }">{{ memberMessage }}</p>

            <section class="teacher-member-section">
              <header><div><strong>班级学生</strong><small>学习统计来自学生真实做题记录</small></div><span>{{ detail.members.length }} 人</span></header>
              <div v-if="detail.members.length" class="teacher-table-wrap">
                <table>
                  <thead><tr><th>学生</th><th>阶段</th><th>练习量</th><th>正确率</th><th>学习时长</th><th>最近活跃</th><th>操作</th></tr></thead>
                  <tbody>
                    <tr v-for="member in detail.members" :key="member.id">
                      <td><i>{{ member.username.slice(0, 1) }}</i><strong>{{ member.username }}</strong></td>
                      <td>{{ member.current_stage }}</td><td>{{ member.practice_count }} 题</td>
                      <td :class="masteryTone(member.accuracy)">{{ member.accuracy }}%</td><td>{{ member.study_hours }} h</td>
                      <td>{{ formatTime(member.last_active) }}</td>
                      <td class="teacher-row-actions"><RouterLink :to="`/teacher/students/${member.id}`">学情</RouterLink><RouterLink :to="`/teacher/preview/${member.id}`">预览</RouterLink><button class="teacher-remove-member" type="button" @click="removeStudent(member)">移出</button></td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-else class="teacher-members-empty"><strong>班级中还没有学生</strong><p>在上方输入已注册学生的用户名，即可将他加入当前班级。</p></div>
            </section>
          </article>

          <article v-else class="teacher-select-class-empty"><span>▦</span><strong>选择一个班级</strong><p>查看成员和学习完成情况。</p></article>
        </section>
      </section>
    </main>

    <div v-if="createOpen" class="teacher-modal-backdrop" @click.self="closeModal">
      <form class="teacher-modal" @submit.prevent="createClass">
        <header><div><small>{{ editingClassId ? '维护教学组织' : '新建教学组织' }}</small><h2>{{ editingClassId ? '编辑班级' : '创建班级' }}</h2></div><button type="button" aria-label="关闭" @click="closeModal">×</button></header>
        <label><span>班级名称</span><input v-model.trim="classForm.name" maxlength="100" placeholder="例如：高等数学 A 班" required /></label>
        <label><span>学习阶段</span><select v-model="classForm.stage" @change="loadCourses"><option v-for="stage in stages" :key="stage.stage_name" :value="stage.stage_name">{{ stage.stage_name }} · {{ stage.title }}</option></select></label>
        <label><span>主要课程</span><select v-model="classForm.course" required><option v-for="course in courses" :key="course.course_name" :value="course.course_name">{{ course.course_name }}</option></select></label>
        <p v-if="createError" class="teacher-form-message is-error">{{ createError }}</p>
        <footer><button type="button" @click="closeModal">取消</button><button :disabled="creating" type="submit">{{ creating ? "正在保存..." : editingClassId ? "保存修改" : "创建班级" }}</button></footer>
      </form>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { apiDelete, apiGet, apiPost, apiPut } from "../api/client";
import TeacherSidebar from "../components/TeacherSidebar.vue";
import UserAccountButton from "../components/UserAccountButton.vue";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const pageError = ref("");
const classes = ref([]);
const selectedClassId = ref(null);
const detail = ref({ class: null, members: [], student_count: 0 });
const createOpen = ref(false);
const creating = ref(false);
const createError = ref("");
const editingClassId = ref(null);
const stages = ref([]);
const courses = ref([]);
const studentUsername = ref("");
const addingStudent = ref(false);
const memberMessage = ref("");
const memberError = ref(false);
const classForm = reactive({ name: "", stage: "大一", course: "" });

const classSummary = computed(() => {
  const members = detail.value.members || [];
  const practice = members.reduce((sum, item) => sum + item.practice_count, 0);
  const weighted = members.reduce((sum, item) => sum + item.accuracy * item.practice_count, 0);
  return { practice, accuracy: practice ? Math.round(weighted / practice) : 0 };
});

function masteryTone(value) { return value >= 80 ? "is-good" : value >= 60 ? "is-medium" : "is-weak"; }
function formatTime(value) { return value ? new Date(value).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "暂无记录"; }

async function loadStages() {
  const data = await apiGet("/api/stages");
  stages.value = data.stages || [];
  if (!stages.value.some((item) => item.stage_name === classForm.stage)) classForm.stage = stages.value[0]?.stage_name || "大一";
  await loadCourses();
}

async function loadCourses() {
  const data = await apiGet("/api/courses", { stage: classForm.stage });
  courses.value = data.courses || [];
  classForm.course = courses.value[0]?.course_name || "";
}

async function loadClasses(preferredId = null) {
  const data = await apiGet("/api/teacher/classes");
  classes.value = data.items || [];
  const queryId = Number(route.query.class_id || 0);
  const target = preferredId || queryId || selectedClassId.value || classes.value[0]?.id;
  if (target && classes.value.some((item) => item.id === target)) await selectClass(target, false);
  else detail.value = { class: null, members: [], student_count: 0 };
}

async function selectClass(classId, updateUrl = true) {
  selectedClassId.value = classId;
  detail.value = await apiGet(`/api/teacher/classes/${classId}`);
  memberMessage.value = "";
  if (updateUrl) router.replace({ query: { class_id: classId } });
}

async function initialize() {
  loading.value = true; pageError.value = "";
  try {
    await Promise.all([loadStages(), loadClasses()]);
    if (route.query.create === "1") openCreate();
  } catch (error) { pageError.value = error.message || "班级数据加载失败。"; }
  finally { loading.value = false; }
}

function openCreate() { editingClassId.value = null; classForm.name = ""; createError.value = ""; createOpen.value = true; }
function closeModal() { createOpen.value = false; editingClassId.value = null; }
async function openEdit() { editingClassId.value = detail.value.class.id; classForm.name = detail.value.class.name; classForm.stage = detail.value.class.stage; await loadCourses(); classForm.course = detail.value.class.course; createError.value = ""; createOpen.value = true; }

async function createClass() {
  creating.value = true; createError.value = "";
  try {
    const item = editingClassId.value ? await apiPut(`/api/teacher/classes/${editingClassId.value}`, classForm) : await apiPost("/api/teacher/classes", classForm);
    closeModal(); classForm.name = "";
    await loadClasses(item.id);
  } catch (error) { createError.value = error.message || "创建班级失败。"; }
  finally { creating.value = false; }
}

async function addStudent() {
  addingStudent.value = true; memberMessage.value = ""; memberError.value = false;
  try {
    detail.value = await apiPost(`/api/teacher/classes/${selectedClassId.value}/members`, { username: studentUsername.value });
    const addedUsername = studentUsername.value;
    const className = detail.value.class.name;
    studentUsername.value = "";
    await loadClasses(selectedClassId.value);
    memberMessage.value = `${addedUsername} 已加入 ${className}。`;
  } catch (error) { memberError.value = true; memberMessage.value = error.message || "添加学生失败。"; }
  finally { addingStudent.value = false; }
}

async function removeStudent(member) {
  if (!window.confirm(`确认将 ${member.username} 移出当前班级吗？`)) return;
  try {
    detail.value = await apiDelete(`/api/teacher/classes/${selectedClassId.value}/members/${member.id}`);
    await loadClasses(selectedClassId.value);
  } catch (error) { memberError.value = true; memberMessage.value = error.message || "移出学生失败。"; }
}

async function copyInvite() {
  await navigator.clipboard.writeText(detail.value.class.invite_code);
  memberError.value = false; memberMessage.value = "班级邀请码已复制。";
}

async function exportMembers() {
  memberMessage.value = "";
  memberError.value = false;
  try {
    const response = await fetch(`/api/teacher/classes/${selectedClassId.value}/export`, { credentials: "include" });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "导出班级名单失败。");
    }
    const blobUrl = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a");
    anchor.href = blobUrl;
    anchor.download = `${detail.value.class.name}-学生名单.csv`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(blobUrl);
    memberMessage.value = `已导出 ${detail.value.members.length} 名学生的班级名单。`;
  } catch (error) {
    memberError.value = true;
    memberMessage.value = error.message || "导出班级名单失败。";
  }
}

async function regenerateInvite() { if (!window.confirm("旧邀请码将立即失效，确定重新生成吗？")) return; try { detail.value = await apiPost(`/api/teacher/classes/${selectedClassId.value}/regenerate-invite`); await loadClasses(selectedClassId.value); memberError.value = false; memberMessage.value = "新的班级邀请码已生成。"; } catch (error) { memberError.value = true; memberMessage.value = error.message; } }
async function archiveClass() { if (!window.confirm(`确认归档 ${detail.value.class.name} 吗？`)) return; try { await apiPost(`/api/teacher/classes/${selectedClassId.value}/archive`); selectedClassId.value = null; await loadClasses(); } catch (error) { memberError.value = true; memberMessage.value = error.message; } }

onMounted(initialize);
</script>
