<template>
  <TeacherPageShell
    active="assignments"
    :title="isEdit ? '编辑作业草稿' : '布置作业'"
    eyebrow="智能组卷"
    description="先确定班级与任务要求，再从已发布题库中挑选题目。"
  >
    <template #actions>
      <RouterLink class="teacher-secondary-action" to="/teacher/assignments">← 返回作业列表</RouterLink>
    </template>

    <form class="teacher-assignment-editor" @submit.prevent="save(false)">
      <section class="teacher-panel teacher-assignment-settings">
        <header><div><strong>1. 作业设置</strong><small>发布后学生会收到消息提醒</small></div></header>
        <div class="teacher-form-grid">
          <label><span>班级 *</span><select v-model="form.class_id" required><option value="" disabled>请选择班级</option><option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }} · {{ item.course }}</option></select></label>
          <label><span>作业标题 *</span><input v-model="form.title" required placeholder="例如：极限与连续周练" /></label>
          <label class="span-all"><span>作业说明</span><textarea v-model="form.description" rows="3" placeholder="学习目标、提交要求或注意事项"></textarea></label>
          <label><span>开始时间</span><input v-model="form.starts_at" type="datetime-local" /></label>
          <label><span>截止时间</span><input v-model="form.due_at" type="datetime-local" /></label>
          <label><span>限时（分钟）</span><input v-model.number="form.time_limit_minutes" type="number" min="5" max="600" placeholder="不填则不限时" /></label>
          <label><span>允许作答次数</span><input v-model.number="form.max_attempts" type="number" min="1" max="5" /></label>
          <label class="teacher-check-label"><input v-model="form.show_analysis_after_submit" type="checkbox" /><span>提交后允许查看解析</span></label>
        </div>
      </section>

      <section class="teacher-panel teacher-question-picker">
        <header>
          <div><strong>2. 选择题目</strong><small>已选择 {{ selectedIds.length }} 题，总分 {{ totalPoints }}</small></div>
          <div><input v-model="search" placeholder="搜索题干或知识点" @keyup.enter.prevent="loadQuestions" /><button type="button" @click="loadQuestions">搜索</button></div>
        </header>
        <div class="teacher-random-picker">
          <div><strong>按班级智能抽题</strong><small>按所选班级的阶段与课程，从已发布中文题库中随机抽取，已有选择会保留。</small></div>
          <label><span>数量</span><input v-model.number="randomCount" type="number" min="1" max="50" /></label>
          <button class="teacher-secondary-action" type="button" :disabled="randomizing" @click="randomSelect">{{ randomizing ? "抽取中…" : "随机选题" }}</button>
          <button class="teacher-upload-paper-action" type="button" @click="openPaperImport">⇧ 上传试卷</button>
          <button type="button" :disabled="!selectedIds.length" @click="clearSelection">清空选择</button>
        </div>
        <p v-if="randomMessage" class="teacher-form-message" :class="{ 'is-error': randomError }">{{ randomMessage }}</p>
        <div v-if="loading" class="teacher-inline-empty">正在加载已发布题目…</div>
        <div v-else class="teacher-picker-list">
          <label v-for="item in questions" :key="item.id" :class="{ selected: selectedIds.includes(item.id) }">
            <input v-model="selectedIds" type="checkbox" :value="item.id" :disabled="!selectedIds.includes(item.id) && selectedIds.length >= 100" />
            <span><small>{{ item.type_label }} · {{ item.stage }} · {{ item.course }}</small><strong>{{ item.question_text }}</strong><em>{{ item.knowledge_tag }} / {{ item.fine_tag }} · 难度 {{ item.difficulty }}</em></span>
            <input v-if="selectedIds.includes(item.id)" v-model.number="pointMap[item.id]" class="point-input" type="number" min="1" max="100" @click.stop />
            <b>分</b>
          </label>
        </div>
        <footer class="teacher-pagination"><button type="button" :disabled="page <= 1" @click="page--; loadQuestions()">上一页</button><span>第 {{ page }} 页</span><button type="button" :disabled="questions.length < 20" @click="page++; loadQuestions()">下一页</button></footer>
      </section>

      <p v-if="error" class="teacher-form-message is-error">{{ error }}</p>
      <footer class="teacher-sticky-actions">
        <span>已选择 {{ selectedIds.length }} 题 · 总分 {{ totalPoints }}</span>
        <button class="teacher-secondary-action" :disabled="saving" type="submit">保存草稿</button>
        <button class="teacher-primary-action" :disabled="saving || !selectedIds.length" type="button" @click="save(true)">{{ saving ? "处理中…" : "发布给学生" }}</button>
      </footer>
    </form>
    <QuestionImportDialog :open="paperImportOpen" mode="assignment" :initial-stage="selectedClass?.stage || ''" :initial-course="selectedClass?.course || ''" :selection-limit="Math.max(0, 100 - selectedIds.length)" @close="paperImportOpen = false" @imported="handlePaperImported" />
  </TeacherPageShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { apiGet, apiPost, apiPut } from "../api/client";
import TeacherPageShell from "../components/TeacherPageShell.vue";
import QuestionImportDialog from "../components/QuestionImportDialog.vue";

const route = useRoute();
const router = useRouter();
const isEdit = computed(() => Boolean(route.params.assignmentId));
const classes = ref([]);
const questions = ref([]);
const selectedIds = ref([]);
const pointMap = reactive({});
const search = ref("");
const page = ref(1);
const randomCount = ref(10);
const randomizing = ref(false);
const randomMessage = ref("");
const randomError = ref(false);
const paperImportOpen = ref(false);
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const form = reactive({
  class_id: "",
  title: "",
  description: "",
  starts_at: "",
  due_at: "",
  time_limit_minutes: null,
  max_attempts: 1,
  show_analysis_after_submit: true
});
const totalPoints = computed(() => selectedIds.value.reduce((sum, id) => sum + Number(pointMap[id] || 10), 0));
const selectedClass = computed(() => classes.value.find((item) => Number(item.id) === Number(form.class_id)) || null);

watch(selectedIds, (ids) => ids.forEach((id) => { if (!pointMap[id]) pointMap[id] = 10; }));

async function loadQuestions() {
  loading.value = true;
  try {
    const data = await apiGet("/api/teacher/questions", { scope: "all", publish_status: "published", search: search.value, page: page.value, page_size: 20 });
    questions.value = data.items || [];
  } catch (exception) {
    error.value = exception.message;
  } finally {
    loading.value = false;
  }
}

async function randomSelect() {
  randomMessage.value = "";
  randomError.value = false;
  const selectedClass = classes.value.find((item) => Number(item.id) === Number(form.class_id));
  if (!selectedClass) {
    randomError.value = true;
    randomMessage.value = "请先选择一个班级。";
    return;
  }
  randomizing.value = true;
  try {
    const remaining = 100 - selectedIds.value.length;
    if (remaining <= 0) {
      randomError.value = true;
      randomMessage.value = "每份试卷最多 100 道题，请先移除部分题目。";
      return;
    }
    const requested = Math.max(1, Math.min(remaining, 50, Number(randomCount.value || 10)));
    let data = await apiGet("/api/teacher/questions/random", {
      count: requested,
      stage: selectedClass.stage,
      course: selectedClass.course
    });
    if ((data.items || []).length < requested) {
      data = await apiGet("/api/teacher/questions/random", { count: requested, stage: selectedClass.stage });
    }
    const ids = (data.items || []).map((item) => Number(item.id));
    selectedIds.value = Array.from(new Set([...selectedIds.value.map(Number), ...ids]));
    questions.value = [
      ...(data.items || []),
      ...questions.value.filter((item) => !ids.includes(Number(item.id)))
    ];
    ids.forEach((id) => { if (!pointMap[id]) pointMap[id] = 10; });
    randomMessage.value = ids.length
      ? `已随机加入 ${ids.length} 道中文题，当前共选择 ${selectedIds.value.length} 道。`
      : "当前班级阶段暂无可用中文题，请先到题库发布题目。";
    randomError.value = !ids.length;
  } catch (exception) {
    randomError.value = true;
    randomMessage.value = exception.message;
  } finally {
    randomizing.value = false;
  }
}

function openPaperImport() {
  if (!selectedClass.value) {
    randomError.value = true;
    randomMessage.value = "请先选择班级，系统会用班级的阶段和课程归类试卷题目。";
    return;
  }
  if (selectedIds.value.length >= 100) {
    randomError.value = true;
    randomMessage.value = "每份试卷最多 100 道题，请先移除部分题目再上传试卷。";
    return;
  }
  paperImportOpen.value = true;
}

function handlePaperImported(data) {
  const imported = data.questions || [];
  const ids = imported.map((item) => Number(item.id));
  selectedIds.value = Array.from(new Set([...selectedIds.value.map(Number), ...ids]));
  questions.value = [...imported, ...questions.value.filter((item) => !ids.includes(Number(item.id)))];
  imported.forEach((item) => { pointMap[item.id] = Number(item.points || 10); });
  if (!form.title && data.source_file_name) {
    form.title = String(data.source_file_name).replace(/\.(pdf|xlsx?|csv)$/i, "");
  }
  randomError.value = Boolean(data.error_count);
  randomMessage.value = `已从试卷加入 ${imported.length} 道题${data.reused_count ? `（复用题库已有 ${data.reused_count} 道）` : ""}${data.duplicate_count ? `，跳过 ${data.duplicate_count} 道重复题` : ""}。`;
}

function clearSelection() {
  selectedIds.value = [];
  randomMessage.value = "已清空所选题目。";
  randomError.value = false;
}

async function save(publish) {
  saving.value = true;
  error.value = "";
  try {
    if (!form.class_id) throw new Error("请选择班级。");
    if (!selectedIds.value.length) throw new Error("请至少选择一道题。");
    const payload = {
      ...form,
      starts_at: form.starts_at || null,
      due_at: form.due_at || null,
      time_limit_minutes: form.time_limit_minutes || null,
      max_attempts: Number(form.max_attempts || 1),
      question_ids: selectedIds.value,
      points: selectedIds.value.map((id) => Number(pointMap[id] || 10)),
      publish
    };
    const data = isEdit.value
      ? await apiPut(`/api/teacher/assignments/${route.params.assignmentId}`, payload)
      : await apiPost("/api/teacher/assignments", payload);
    await router.push(`/teacher/assignments/${data.assignment.id}`);
  } catch (exception) {
    error.value = exception.message;
  } finally {
    saving.value = false;
  }
}

function localInput(value) {
  if (!value) return "";
  const date = new Date(value);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

onMounted(async () => {
  classes.value = (await apiGet("/api/teacher/classes")).items || [];
  form.class_id = classes.value[0]?.id || "";
  if (isEdit.value) {
    const data = await apiGet(`/api/teacher/assignments/${route.params.assignmentId}`);
    if (data.assignment.status !== "draft") {
      error.value = "只有草稿作业可以编辑。";
      return;
    }
    Object.assign(form, {
      class_id: data.assignment.class_id,
      title: data.assignment.title,
      description: data.assignment.description || "",
      starts_at: localInput(data.assignment.starts_at),
      due_at: localInput(data.assignment.due_at),
      time_limit_minutes: data.assignment.time_limit_minutes,
      max_attempts: data.assignment.max_attempts || 1,
      show_analysis_after_submit: data.assignment.show_analysis_after_submit
    });
    selectedIds.value = data.questions.map((question) => question.id);
    data.questions.forEach((question) => { pointMap[question.id] = question.points; });
  }
  await loadQuestions();
});
</script>
