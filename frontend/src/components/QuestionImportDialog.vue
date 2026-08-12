<template>
  <Teleport to="body">
    <div v-if="open" class="teacher-import-backdrop" @click.self="emit('close')">
      <section class="teacher-import-dialog" role="dialog" aria-modal="true" aria-labelledby="import-dialog-title">
        <header class="teacher-import-header">
          <div>
            <small>{{ mode === 'assignment' ? '试卷识别' : '批量入库' }}</small>
            <h2 id="import-dialog-title">{{ mode === 'assignment' ? '上传试卷并加入当前作业' : '从文件导入题目' }}</h2>
            <p>支持 PDF、Excel 和 UTF-8 CSV，写入前会先展示识别结果。</p>
          </div>
          <button type="button" aria-label="关闭" @click="emit('close')">×</button>
        </header>

        <div class="teacher-import-steps" aria-label="导入进度">
          <span :class="{ active: !preview }"><b>1</b> 上传与归类</span>
          <i></i>
          <span :class="{ active: preview }"><b>2</b> 校验与确认</span>
        </div>

        <div v-if="!preview" class="teacher-import-setup">
          <input ref="fileInput" hidden type="file" accept=".pdf,.xlsx,.xls,.csv" @change="pickFile" />
          <button
            class="teacher-import-dropzone"
            :class="{ 'has-file': file }"
            type="button"
            @click="fileInput?.click()"
            @dragover.prevent
            @drop.prevent="dropFile"
          >
            <span>{{ file ? fileBadge : '⇧' }}</span>
            <strong>{{ file ? file.name : '选择或拖入题目文件' }}</strong>
            <small>{{ file ? fileSize : 'PDF / XLSX / XLS / CSV，最大 15 MB' }}</small>
          </button>

          <div class="teacher-import-format-row">
            <p><b>表格文件</b><span>可在每一行填写阶段、课程和知识点；缺失项使用下方默认归类。</span></p>
            <a href="/api/teacher/question-imports/template" download>下载 Excel 模板</a>
          </div>
          <div class="teacher-import-format-row">
            <p><b>PDF 试卷</b><span>使用“1. 题干、A. 选项、答案：、解析：”格式；扫描件需先做 OCR。</span></p>
            <em>自动识别题号与答案</em>
          </div>

          <div class="teacher-import-defaults">
            <header><strong>默认归类</strong><small>文件内已有字段时，以文件内容为准</small></header>
            <div>
              <label><span>阶段 *</span><select v-model="defaults.stage" @change="loadCourses"><option value="">请选择</option><option v-for="item in stages" :key="item.stage_name" :value="item.stage_name">{{ item.stage_name }}</option></select></label>
              <label><span>课程 *</span><select v-model="defaults.course"><option value="">请选择</option><option v-for="item in courses" :key="item.course_name" :value="item.course_name">{{ item.course_name }}</option></select></label>
              <label><span>知识点 *</span><input v-model.trim="defaults.knowledge_tag" placeholder="例如：函数极限" /></label>
              <label><span>细分标签</span><input v-model.trim="defaults.fine_tag" placeholder="例如：重要极限" /></label>
              <label><span>默认难度</span><select v-model.number="defaults.difficulty"><option v-for="n in 5" :key="n" :value="n">{{ n }} 级</option></select></label>
            </div>
          </div>
        </div>

        <div v-else class="teacher-import-preview">
          <div class="teacher-import-summary">
            <article><small>识别题目</small><strong>{{ preview.total_detected }}</strong></article>
            <article class="valid"><small>可导入</small><strong>{{ preview.valid_count }}</strong></article>
            <article :class="{ invalid: preview.invalid_count }"><small>需修正</small><strong>{{ preview.invalid_count }}</strong></article>
            <article><small>已选择</small><strong>{{ selectedIndexes.length }}</strong></article>
          </div>
          <div class="teacher-import-preview-tools">
            <label><input type="checkbox" :checked="allValidSelected" @change="toggleAll" /> 选择全部有效题目</label>
            <span>{{ preview.file_name }} · {{ parseMethod }}</span>
            <button type="button" @click="preview = null">返回调整</button>
          </div>
          <div class="teacher-import-question-list">
            <article v-for="(item, index) in preview.questions" :key="`${item.source_row}-${index}`" :class="{ invalid: !item.valid, selected: selectedIndexes.includes(index) }">
              <label>
                <input v-model="selectedIndexes" type="checkbox" :value="index" :disabled="!item.valid || selectionDisabled(index)" />
                <b>{{ item.source_row }}</b>
              </label>
              <div>
                <header><span>{{ item.type_label }}</span><em>{{ item.stage || '未归类' }} · {{ item.course || '未归类' }}</em><small>{{ item.points }} 分</small></header>
                <h3>{{ item.question_text || '未识别到题干' }}</h3>
                <p v-if="item.question_type === 'choice'">答案 {{ item.correct_answer || '缺失' }} · {{ compactOptions(item) }}</p>
                <p v-else>参考答案：{{ truncate(item.standard_answer, 100) || '缺失' }}</p>
                <ul v-if="item.errors.length"><li v-for="errorItem in item.errors" :key="errorItem">{{ errorItem }}</li></ul>
                <aside v-if="item.warnings.length"><span v-for="warning in item.warnings" :key="warning">{{ warning }}</span></aside>
              </div>
            </article>
          </div>
        </div>

        <p v-if="error" class="teacher-form-message is-error">{{ error }}</p>
        <footer class="teacher-import-footer">
          <span v-if="preview && preview.invalid_count">有 {{ preview.invalid_count }} 道题未通过校验，不会被导入。</span>
          <span v-else-if="preview && allValidIndexes.length > selectionLimit">当前试卷还可加入 {{ selectionLimit }} 道题，超出部分未选择。</span>
          <span v-else></span>
          <button type="button" @click="emit('close')">取消</button>
          <button v-if="!preview" class="teacher-primary-action" type="button" :disabled="parsing || !file" @click="parseFile">{{ parsing ? '正在识别…' : '解析文件' }}</button>
          <button v-else class="teacher-primary-action" type="button" :disabled="committing || !selectedIndexes.length" @click="commitImport">{{ committing ? '正在写入…' : confirmText }}</button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { apiGet, apiPost, apiUpload } from "../api/client";

const props = defineProps({
  open: { type: Boolean, default: false },
  mode: { type: String, default: "bank" },
  initialStage: { type: String, default: "" },
  initialCourse: { type: String, default: "" },
  selectionLimit: { type: Number, default: 500 }
});
const emit = defineEmits(["close", "imported"]);
const fileInput = ref(null);
const file = ref(null);
const preview = ref(null);
const stages = ref([]);
const courses = ref([]);
const selectedIndexes = ref([]);
const parsing = ref(false);
const committing = ref(false);
const error = ref("");
const defaults = reactive({ stage: "", course: "", knowledge_tag: "", fine_tag: "", difficulty: 3 });

const fileBadge = computed(() => file.value?.name?.split(".").pop()?.toUpperCase() || "FILE");
const fileSize = computed(() => file.value ? `${(file.value.size / 1024 / 1024).toFixed(2)} MB` : "");
const allValidIndexes = computed(() => (preview.value?.questions || []).map((item, index) => item.valid ? index : -1).filter((index) => index >= 0));
const selectableValidIndexes = computed(() => allValidIndexes.value.slice(0, props.selectionLimit));
const allValidSelected = computed(() => selectableValidIndexes.value.length > 0 && selectableValidIndexes.value.every((index) => selectedIndexes.value.includes(index)));
const parseMethod = computed(() => preview.value?.parse_method === "pdf-text" ? "PDF 文字识别" : "结构化表格");
const confirmText = computed(() => props.mode === "assignment" ? `导入并加入试卷（${selectedIndexes.value.length}）` : `确认入库（${selectedIndexes.value.length}）`);

function reset() {
  file.value = null;
  preview.value = null;
  selectedIndexes.value = [];
  error.value = "";
  Object.assign(defaults, { stage: props.initialStage || "", course: props.initialCourse || "", knowledge_tag: "", fine_tag: "", difficulty: 3 });
}

function acceptFile(candidate) {
  const suffix = candidate?.name?.split(".").pop()?.toLowerCase();
  if (!candidate || !["pdf", "xlsx", "xls", "csv"].includes(suffix)) {
    error.value = "请选择 PDF、Excel 或 CSV 文件。";
    return;
  }
  if (candidate.size > 15 * 1024 * 1024) {
    error.value = "文件不能超过 15 MB。";
    return;
  }
  file.value = candidate;
  preview.value = null;
  error.value = "";
}

function pickFile(event) {
  acceptFile(event.target.files?.[0]);
  event.target.value = "";
}

function dropFile(event) {
  acceptFile(event.dataTransfer?.files?.[0]);
}

async function loadCourses() {
  defaults.course = "";
  courses.value = defaults.stage ? (await apiGet("/api/courses", { stage: defaults.stage })).courses || [] : [];
}

async function ensureLists() {
  if (!stages.value.length) stages.value = (await apiGet("/api/stages")).stages || [];
  if (defaults.stage) {
    courses.value = (await apiGet("/api/courses", { stage: defaults.stage })).courses || [];
  }
}

async function parseFile() {
  parsing.value = true;
  error.value = "";
  try {
    const formData = new FormData();
    formData.append("file", file.value);
    formData.append("default_stage", defaults.stage);
    formData.append("default_course", defaults.course);
    formData.append("default_knowledge_tag", defaults.knowledge_tag);
    formData.append("default_fine_tag", defaults.fine_tag);
    formData.append("default_difficulty", String(defaults.difficulty));
    preview.value = await apiUpload("/api/teacher/question-imports/preview", formData);
    selectedIndexes.value = (preview.value.questions || []).map((item, index) => item.valid ? index : -1).filter((index) => index >= 0).slice(0, props.selectionLimit);
  } catch (exception) {
    error.value = exception.message;
  } finally {
    parsing.value = false;
  }
}

function toggleAll(event) {
  selectedIndexes.value = event.target.checked ? [...selectableValidIndexes.value] : [];
}

function selectionDisabled(index) {
  return !selectedIndexes.value.includes(index) && selectedIndexes.value.length >= props.selectionLimit;
}

async function commitImport() {
  committing.value = true;
  error.value = "";
  try {
    const questions = selectedIndexes.value.map((index) => preview.value.questions[index]);
    const result = await apiPost("/api/teacher/question-imports/commit", {
      questions,
      publish_status: props.mode === "assignment" ? "published" : "draft",
      visibility: props.mode === "assignment" ? "class" : "public",
      source_file_name: preview.value.file_name,
      skip_duplicates: true,
      reuse_duplicates: props.mode === "assignment"
    });
    emit("imported", result);
    emit("close");
  } catch (exception) {
    error.value = exception.message;
  } finally {
    committing.value = false;
  }
}

function truncate(value, length) {
  const text = String(value || "");
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

function compactOptions(item) {
  return ["A", "B", "C", "D"].map((key) => `${key}. ${truncate(item[`option_${key.toLowerCase()}`], 28)}`).join("　");
}

watch(() => props.open, async (isOpen) => {
  if (!isOpen) return;
  reset();
  try {
    await ensureLists();
  } catch (exception) {
    error.value = exception.message;
  }
});
</script>
