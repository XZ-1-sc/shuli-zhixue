<template>
  <section class="teacher-view">
        <PageHeader title="班级管理" eyebrow="组织与成员" description="创建课程班级，并按学生用户名添加已经注册的学生。">
          <template #actions>
          <button class="teacher-primary-action" type="button" @click="openCreate">＋ 创建班级</button>
          </template>
        </PageHeader>

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
              <div class="class-heading-side"><div class="class-detail-stats"><span><strong>{{ detail.student_count }}</strong>学生</span><span><strong>{{ classSummary.accuracy }}</strong>正确率</span><span><strong>{{ classSummary.practice }}</strong>练习</span></div><div class="teacher-row-actions"><button type="button" @click="exportMembers">导出名单</button><button type="button" @click="openEdit">编辑班级</button><button class="danger" type="button" @click="archiveClass">归档</button><button class="danger is-delete" type="button" @click="openDeleteConfirm">永久删除</button></div></div>
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

            <AssignmentAnalytics :key="`class-analytics-${selectedClassId}`" scope="class" :scope-id="Number(selectedClassId)" />

            <section class="teacher-panel advice-draft-panel">
              <header>
                <div><strong>建议草稿箱</strong><small>AI 为每名学生起草，编辑确认后再发送到个人收件箱</small></div>
                <div class="advice-actions"><button type="button" :disabled="generatingAdvice || !detail.members.length" @click="generateAdvice">{{ generatingAdvice ? "生成中…" : "✦ 生成建议" }}</button><button type="button" :disabled="!selectedDraftIds.length || sendingAdvice" @click="batchSendAdvice">批量发送 {{ selectedDraftIds.length || "" }}</button></div>
              </header>
              <p v-if="adviceMessage" class="teacher-form-message" :class="{ 'is-error': adviceError }">{{ adviceMessage }}</p>
              <div v-if="adviceDrafts.length" class="advice-draft-list">
                <article v-for="draft in adviceDrafts" :key="draft.id">
                  <header><label><input :checked="selectedDraftIds.includes(draft.id)" type="checkbox" @change="toggleDraft(draft.id)" /><span><strong>{{ draft.nickname }}</strong><small>@{{ draft.username }} · {{ draft.latest_assignment || "暂无近期作业" }}</small></span></label><button type="button" :disabled="savingDraftId === draft.id" @click="saveDraft(draft)">{{ savingDraftId === draft.id ? "保存中…" : "保存修改" }}</button></header>
                  <textarea v-model="draft.content" rows="5" maxlength="4000" aria-label="学习调整建议"></textarea>
                  <footer><small>更新于 {{ formatTime(draft.updated_at) }}</small><button type="button" :disabled="sendingAdvice" @click="sendAdvice(draft)">发送给学生</button></footer>
                </article>
              </div>
              <div v-else class="teacher-inline-empty">还没有待审阅建议。点击“生成建议”为班级学生创建草稿。</div>
            </section>
          </article>

          <article v-else class="teacher-select-class-empty"><span>▦</span><strong>选择一个班级</strong><p>查看成员和学习完成情况。</p></article>
        </section>
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
    <div v-if="deleteOpen" class="teacher-modal-backdrop teacher-delete-backdrop" @click.self="closeDeleteConfirm">
      <form class="teacher-modal teacher-delete-modal" role="dialog" aria-modal="true" aria-labelledby="class-delete-title" @submit.prevent="submitDelete" @keydown.esc.prevent="closeDeleteConfirm">
        <header>
          <div><small>危险操作 · 不可恢复</small><h2 id="class-delete-title">永久删除「{{ deleteTarget.name }}」</h2></div>
          <button type="button" aria-label="关闭删除确认" :disabled="deleting" @click="closeDeleteConfirm">×</button>
        </header>

        <div v-if="deleteImpactLoading" class="teacher-delete-loading" role="status"><i></i><span>正在核对班级关联数据…</span></div>
        <template v-else-if="deleteImpactReady">
          <div class="teacher-delete-impact" aria-label="班级删除影响">
            <span><strong>{{ deleteCounts.member_count }}</strong><small>名学生</small></span>
            <span><strong>{{ deleteCounts.assignment_count }}</strong><small>份作业</small></span>
            <span><strong>{{ deleteCounts.record_count }}</strong><small>条关联作答</small></span>
          </div>
          <p v-if="deleteHasPublishedAssignment" class="teacher-delete-blocked"><strong>暂时无法删除</strong><span>班级仍有进行中的作业，请先结束作业再删除班级。</span></p>
          <p v-else-if="deleteNeedsName" class="teacher-delete-warning">
            永久删除会移除成员关系、作业及其提交和成绩。学生作答记录本身会保留，但班级与作业关联将被清空。此操作不可恢复，建议优先使用“归档”。
          </p>
          <p v-else class="teacher-delete-warning is-empty">该班级没有成员、作业或关联作答。删除班级本身后不可恢复。</p>

          <label v-if="deleteNeedsName && !deleteHasPublishedAssignment" class="teacher-delete-name-field">
            <span>输入班级名称 <b>{{ deleteTarget.name }}</b> 以确认</span>
            <input v-model.trim="deleteName" :placeholder="deleteTarget.name" autocomplete="off" aria-describedby="class-delete-name-help" required />
            <small id="class-delete-name-help" :class="{ 'is-match': deleteNameMatches }">{{ deleteNameMatches ? "名称一致，可以永久删除。" : "必须与班级名称完全一致。" }}</small>
          </label>
        </template>

        <p v-if="deleteError" class="teacher-form-message is-error" role="alert">{{ deleteError }}</p>
        <footer>
          <button type="button" :disabled="deleting" @click="closeDeleteConfirm">取消</button>
          <button class="teacher-delete-submit" :disabled="deleting || deleteImpactLoading || !deleteImpactReady || deleteHasPublishedAssignment || (deleteNeedsName && !deleteNameMatches)" type="submit">
            {{ deleting ? "删除中…" : "确认永久删除" }}
          </button>
        </footer>
      </form>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { apiDelete, apiGet, apiPost, apiPut } from "../api/client";
import AssignmentAnalytics from "../components/teacher/AssignmentAnalytics.vue";
import PageHeader from "../components/ui/PageHeader.vue";
import { requestConfirmation } from "../services/confirm";
import { notify } from "../services/toast";

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
const adviceDrafts = ref([]);
const selectedDraftIds = ref([]);
const generatingAdvice = ref(false);
const sendingAdvice = ref(false);
const savingDraftId = ref(null);
const adviceMessage = ref("");
const adviceError = ref(false);
const classForm = reactive({ name: "", stage: "大一", course: "" });
const deleteOpen = ref(false);
const deleting = ref(false);
const deleteImpactLoading = ref(false);
const deleteImpactReady = ref(false);
const deleteHasPublishedAssignment = ref(false);
const deleteNeedsName = ref(false);
const deleteName = ref("");
const deleteError = ref("");
const deleteTarget = reactive({ id: null, name: "" });
const deleteCounts = reactive({ member_count: 0, assignment_count: 0, record_count: 0 });

const classSummary = computed(() => {
  const members = detail.value.members || [];
  const practice = members.reduce((sum, item) => sum + item.practice_count, 0);
  const weighted = members.reduce((sum, item) => sum + item.accuracy * item.practice_count, 0);
  return { practice, accuracy: practice ? Math.round(weighted / practice) : 0 };
});
const deleteNameMatches = computed(() => deleteName.value === deleteTarget.name);

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
  await loadAdviceDrafts();
  memberMessage.value = "";
  if (updateUrl) router.replace({ query: { class_id: classId } });
}

async function loadAdviceDrafts() {
  if (!selectedClassId.value) { adviceDrafts.value = []; return; }
  const data = await apiGet("/api/teacher/advice/drafts", { class_id: selectedClassId.value });
  adviceDrafts.value = data.items || [];
  selectedDraftIds.value = selectedDraftIds.value.filter((id) => adviceDrafts.value.some((draft) => draft.id === id));
}

function toggleDraft(draftId) {
  selectedDraftIds.value = selectedDraftIds.value.includes(draftId) ? selectedDraftIds.value.filter((id) => id !== draftId) : [...selectedDraftIds.value, draftId];
}

async function generateAdvice() {
  generatingAdvice.value = true; adviceMessage.value = ""; adviceError.value = false;
  try {
    const result = await apiPost("/api/teacher/advice/generate", { class_id: selectedClassId.value });
    await loadAdviceDrafts();
    adviceMessage.value = result.generated_count ? `已生成 ${result.generated_count} 份建议草稿，请审阅后发送。` : "每名学生都已有待审阅草稿。";
  } catch (error) { adviceError.value = true; adviceMessage.value = error.message; }
  finally { generatingAdvice.value = false; }
}

async function saveDraft(draft) {
  savingDraftId.value = draft.id; adviceMessage.value = ""; adviceError.value = false;
  try { await apiPut(`/api/teacher/advice/drafts/${draft.id}`, { content: draft.content }); adviceMessage.value = `${draft.nickname} 的建议已保存。`; }
  catch (error) { adviceError.value = true; adviceMessage.value = error.message; }
  finally { savingDraftId.value = null; }
}

async function sendAdvice(draft) {
  sendingAdvice.value = true; adviceMessage.value = ""; adviceError.value = false;
  try { await apiPut(`/api/teacher/advice/drafts/${draft.id}`, { content: draft.content }); await apiPost(`/api/teacher/advice/drafts/${draft.id}/send`); await loadAdviceDrafts(); adviceMessage.value = `已将建议发送给 ${draft.nickname}。`; }
  catch (error) { adviceError.value = true; adviceMessage.value = error.message; }
  finally { sendingAdvice.value = false; }
}

async function batchSendAdvice() {
  sendingAdvice.value = true; adviceMessage.value = ""; adviceError.value = false;
  try { const result = await apiPost("/api/teacher/advice/drafts/batch-send", { draft_ids: selectedDraftIds.value }); selectedDraftIds.value = []; await loadAdviceDrafts(); adviceMessage.value = `已发送 ${result.sent_count} 份学习建议。`; }
  catch (error) { adviceError.value = true; adviceMessage.value = error.message; }
  finally { sendingAdvice.value = false; }
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
  if (!(await requestConfirmation({ title: "移出学生", description: `确认将 ${member.username} 移出当前班级吗？`, confirmLabel: "确认移出" }))) return;
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

async function regenerateInvite() { if (!(await requestConfirmation({ title: "重新生成邀请码", description: "旧邀请码将立即失效，确定重新生成吗？", confirmLabel: "重新生成" }))) return; try { detail.value = await apiPost(`/api/teacher/classes/${selectedClassId.value}/regenerate-invite`); await loadClasses(selectedClassId.value); memberError.value = false; memberMessage.value = "新的班级邀请码已生成。"; } catch (error) { memberError.value = true; memberMessage.value = error.message; } }
async function archiveClass() { if (!(await requestConfirmation({ title: "归档班级", description: `确认归档 ${detail.value.class.name} 吗？`, confirmLabel: "确认归档" }))) return; try { await apiPost(`/api/teacher/classes/${selectedClassId.value}/archive`); selectedClassId.value = null; await loadClasses(); } catch (error) { memberError.value = true; memberMessage.value = error.message; } }

function closeDeleteConfirm() {
  if (deleting.value) return;
  deleteOpen.value = false;
  deleteName.value = "";
  deleteError.value = "";
}

function updateDeleteCounts(payload = {}) {
  deleteCounts.member_count = Number(payload.member_count || 0);
  deleteCounts.assignment_count = Number(payload.assignment_count || 0);
  deleteCounts.record_count = Number(payload.record_count || 0);
}

async function openDeleteConfirm() {
  if (!detail.value.class) return;
  deleteTarget.id = detail.value.class.id;
  deleteTarget.name = detail.value.class.name;
  deleteName.value = "";
  deleteError.value = "";
  deleteNeedsName.value = false;
  deleteHasPublishedAssignment.value = false;
  deleteImpactReady.value = false;
  updateDeleteCounts({ member_count: detail.value.student_count });
  deleteOpen.value = true;
  deleteImpactLoading.value = true;
  try {
    const impact = await apiGet(`/api/teacher/classes/${deleteTarget.id}/delete-impact`);
    updateDeleteCounts(impact);
    deleteNeedsName.value = Boolean(impact.has_data);
    deleteHasPublishedAssignment.value = Boolean(impact.has_published_assignment);
    deleteImpactReady.value = true;
  } catch (error) {
    deleteError.value = error.message || "无法核对班级关联数据，请稍后重试。";
  } finally {
    deleteImpactLoading.value = false;
  }
}

function applyCountsFromDeleteError(message) {
  const matched = String(message).match(/班级含\s*(\d+)\s*名学生、(\d+)\s*份作业、(\d+)\s*条/);
  if (matched) updateDeleteCounts({ member_count: matched[1], assignment_count: matched[2], record_count: matched[3] });
}

async function submitDelete() {
  if (deleting.value || !deleteImpactReady.value || deleteHasPublishedAssignment.value) return;
  if (deleteNeedsName.value && !deleteNameMatches.value) return;
  deleting.value = true;
  deleteError.value = "";
  const classId = deleteTarget.id;
  const className = deleteTarget.name;
  try {
    await apiDelete(`/api/teacher/classes/${classId}`, { confirm: deleteNeedsName.value });
    selectedClassId.value = null;
    deleteOpen.value = false;
    deleteName.value = "";
    await router.replace({ query: {} });
    await loadClasses();
    notify(`班级「${className}」已永久删除。`, "success");
  } catch (error) {
    const message = error.message || "删除班级失败。";
    if (message.includes("请输入班级名称")) {
      applyCountsFromDeleteError(message);
      deleteNeedsName.value = true;
      deleteName.value = "";
    } else if (message.includes("进行中的作业")) {
      deleteHasPublishedAssignment.value = true;
      deleteError.value = message;
    } else if (message.includes("不存在或不属于")) {
      deleteOpen.value = false;
      selectedClassId.value = null;
      await router.replace({ query: {} });
      await loadClasses();
    } else {
      deleteError.value = message;
    }
  } finally {
    deleting.value = false;
  }
}

onMounted(initialize);
</script>

<style scoped>
.advice-draft-panel{margin-top:16px}.advice-actions{display:flex;gap:8px}.advice-actions button,.advice-draft-list button{min-height:34px;padding:0 12px;border:1px solid rgba(46, 125, 140, 0.25);color:#287381;background:transparent}.advice-actions button:last-child,.advice-draft-list footer button{color:#ffffff;background:#2e7d8c}.advice-draft-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;padding:16px}.advice-draft-list>article{display:grid;gap:10px;padding:14px;border:1px solid rgba(46, 125, 140, 0.14);background: rgba(255, 255, 255, 0.82)}.advice-draft-list article>header,.advice-draft-list article>footer{display:flex;justify-content:space-between;gap:10px;align-items:center}.advice-draft-list label{display:flex;gap:9px;align-items:center}.advice-draft-list label span{display:grid}.advice-draft-list small{color:#706b62}.advice-draft-list textarea{width:100%;resize:vertical;padding:11px;color:#33302b;border:1px solid rgba(46, 125, 140, 0.2);background:#ffffff;line-height:1.65}@media(max-width:760px){.advice-draft-list{grid-template-columns:1fr}.advice-draft-panel>header{align-items:flex-start}.advice-actions{flex-direction:column}}
.teacher-row-actions .is-delete{color:#ad5046;border-color:rgba(180, 85, 74, 0.62);background:rgba(180, 85, 74, 0.16)}
.teacher-row-actions .is-delete:hover{border-color:#ad5046;background:rgba(180, 85, 74, 0.28)}
.teacher-delete-backdrop{z-index:260;padding:20px}
.teacher-delete-modal{width:min(610px,100%);max-height:calc(100dvh - 40px);overflow-y:auto}
.teacher-delete-modal>header small{color:#ad5046;letter-spacing:.12em}
.teacher-delete-modal>header h2{overflow-wrap:anywhere}
.teacher-delete-loading{display:flex;align-items:center;gap:12px;min-height:96px;padding:18px;color:#706b62;border:1px solid rgba(46, 125, 140, 0.14);background: rgba(255, 255, 255, 0.82)}
.teacher-delete-loading i{width:18px;height:18px;border:2px solid rgba(180, 85, 74, 0.25);border-top-color:#ad5046;border-radius:50%;animation:delete-spin .8s linear infinite}
.teacher-delete-impact{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;border:1px solid rgba(180, 85, 74, 0.2);background:rgba(180, 85, 74, 0.2)}
.teacher-delete-impact span{display:grid;gap:4px;padding:14px 10px;text-align:center;background:#ffffff}
.teacher-delete-impact strong{color:#33302b;font:700 24px/1 Georgia,serif;font-variant-numeric:tabular-nums}
.teacher-delete-impact small{color:#706b62;font-size:12px}
.teacher-delete-warning,.teacher-delete-blocked{margin:0;padding:14px 16px;color:#ad5046;border-left:3px solid #b4554a;background:rgba(180, 85, 74, 0.1);line-height:1.65}
.teacher-delete-warning.is-empty{color:#33302b;border-left-color:#706b62;background:rgba(100, 90, 70, 0.08)}
.teacher-delete-blocked{display:grid;gap:3px;color:#8f5f0e;border-left-color:#8f5f0e;background:rgba(176, 125, 30, 0.09)}
.teacher-delete-blocked strong{color:#8f5f0e}
.teacher-delete-name-field{display:grid;gap:8px}
.teacher-delete-name-field>span{color:#33302b;font-weight:700}
.teacher-delete-name-field b{color:#33302b;overflow-wrap:anywhere}
.teacher-delete-name-field input{width:100%;min-height:44px;padding:0 12px;color:#33302b;border:1px solid rgba(180, 85, 74, 0.42);outline:none;background:#ffffff}
.teacher-delete-name-field input:focus-visible{border-color:#ad5046;box-shadow:0 0 0 3px rgba(180, 85, 74, 0.14)}
.teacher-delete-name-field small{color:#706b62}
.teacher-delete-name-field small.is-match{color:#347a56}
.teacher-delete-modal footer .teacher-delete-submit{color:#fff;border-color:#ad5046;background:#b4554a}
.teacher-delete-modal footer .teacher-delete-submit:hover:not(:disabled){background:#b4554a}
.teacher-delete-modal footer .teacher-delete-submit:disabled{color:#ad9491;border-color:rgba(180, 85, 74, 0.18);background:rgba(180, 85, 74, 0.24);cursor:not-allowed}
@keyframes delete-spin{to{transform:rotate(360deg)}}
@media(max-width:520px){.teacher-delete-backdrop{padding:10px}.teacher-delete-modal{max-height:calc(100dvh - 20px);padding:20px}.teacher-delete-impact span{padding:12px 5px}.teacher-delete-impact strong{font-size:21px}.teacher-delete-modal footer{display:grid;grid-template-columns:1fr 1fr}.teacher-delete-modal footer button{width:100%;margin:0}}
@media(prefers-reduced-motion:reduce){.teacher-delete-loading i{animation:none}}
</style>
