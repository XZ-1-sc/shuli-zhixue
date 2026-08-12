<template>
  <TeacherPageShell
    active="review"
    title="批改中心"
    eyebrow="人工复核"
    description="查看学生文字与图片作答，给出分数、评语和订正要求。"
  >
    <section class="teacher-filter-bar">
      <label>
        <span>状态</span>
        <select v-model="reviewStatus" @change="load">
          <option value="pending">待批改</option>
          <option value="graded">已批改</option>
        </select>
      </label>
      <button class="teacher-primary-action" type="button" @click="load">刷新队列</button>
    </section>

    <div v-if="loading" class="teacher-loading-grid"><i v-for="n in 6" :key="n"></i></div>
    <section v-else-if="error" class="teacher-state-panel is-error">
      <strong>批改队列加载失败</strong><p>{{ error }}</p><button type="button" @click="load">重试</button>
    </section>
    <section v-else-if="!items.length" class="teacher-empty-onboarding">
      <div class="empty-compass">✓</div><small>队列已清空</small>
      <h2>{{ reviewStatus === "pending" ? "没有待批改作答" : "还没有已批改记录" }}</h2>
      <p>学生提交图片答案或需要人工复核的主观题后，会自动出现在这里。</p>
      <RouterLink to="/teacher/assignments">查看作业</RouterLink>
    </section>

    <section v-else class="teacher-review-layout">
      <nav class="teacher-review-queue" aria-label="批改队列">
        <button
          v-for="item in items"
          :key="item.id"
          :class="{ active: selected?.id === item.id }"
          type="button"
          @click="select(item)"
        >
          <span>{{ item.username.slice(0, 1) }}</span>
          <div>
            <small>{{ item.assignment_title || "日常练习" }}</small>
            <strong>{{ item.username }} · {{ item.course }}</strong>
            <em>{{ item.knowledge_tag }} · {{ formatTime(item.answered_at) }}</em>
          </div>
          <b>{{ item.attachments.length ? `${item.attachments.length} 图` : "文字" }}</b>
        </button>
      </nav>

      <article v-if="selected" class="teacher-review-paper">
        <header>
          <div>
            <small>{{ selected.assignment_title || "日常练习" }} · {{ typeLabel(selected.question_type) }}</small>
            <h2>{{ selected.question_text }}</h2>
            <p>{{ selected.course }} / {{ selected.knowledge_tag }}</p>
          </div>
          <RouterLink :to="`/teacher/students/${selected.student_id}`">查看学生档案</RouterLink>
        </header>

        <section class="teacher-review-answer">
          <h3>学生答案</h3>
          <p>{{ selected.answer_text || selected.selected_answer || "仅提交了图片作答" }}</p>
          <div v-if="selected.attachments.length" class="teacher-review-images">
            <button v-for="file in selected.attachments" :key="file.id" type="button" @click="openPreview(file)">
              <img :src="file.url" alt="学生作答图片" />
              <span>查看原图</span>
            </button>
          </div>
        </section>

        <section class="teacher-review-reference">
          <h3>参考答案与解析</h3>
          <p><strong>标准答案：</strong>{{ selected.standard_answer }}</p>
          <ol><li v-for="step in selected.key_steps" :key="step">{{ step }}</li></ol>
          <p>{{ selected.analysis_text }}</p>
        </section>

        <form class="teacher-grade-form" @submit.prevent="grade">
          <label>
            <span>得分（0-100）</span>
            <input v-model.number="gradeForm.score" type="number" min="0" max="100" required />
          </label>
          <div class="teacher-score-presets" aria-label="快捷分数">
            <button v-for="score in scorePresets" :key="score" type="button" @click="gradeForm.score = score">{{ score }} 分</button>
          </div>
          <label class="span-all">
            <span>教师评语</span>
            <textarea v-model="gradeForm.feedback" rows="4" required placeholder="指出做得好的地方、错误原因和下一步建议"></textarea>
          </label>
          <div class="teacher-quick-feedback span-all">
            <span>快捷评语</span>
            <div><button v-for="comment in quickComments" :key="comment" type="button" @click="appendComment(comment)">{{ comment }}</button></div>
          </div>
          <label class="teacher-check-label span-all">
            <input v-model="gradeForm.correction_required" type="checkbox" />
            <span>要求学生订正</span>
          </label>
          <p v-if="gradeError" class="teacher-form-message is-error span-all">{{ gradeError }}</p>
          <button v-if="reviewStatus === 'pending'" class="teacher-primary-action" :disabled="grading" type="submit">
            {{ grading ? "提交中…" : "完成批改并通知学生" }}
          </button>
          <p v-else class="teacher-reviewed-note span-all">该作答已完成批改，当前页面为历史记录。</p>
        </form>
      </article>
    </section>

    <div v-if="previewFile" class="teacher-image-lightbox" role="dialog" aria-modal="true" @click.self="closePreview">
      <header class="teacher-image-toolbar">
        <span>{{ previewFile.name || "学生作答原图" }} · {{ Math.round(previewScale * 100) }}%</span>
        <div>
          <button type="button" title="向左旋转" @click="rotatePreview(-90)">↶</button>
          <button type="button" title="向右旋转" @click="rotatePreview(90)">↷</button>
          <button type="button" title="缩小" :disabled="previewScale <= 0.5" @click="zoomPreview(-0.25)">−</button>
          <button type="button" title="放大" :disabled="previewScale >= 3" @click="zoomPreview(0.25)">＋</button>
          <button type="button" title="还原" @click="resetPreview">1:1</button>
          <a :href="previewFile.url" :download="previewFile.name || '学生作答图片'">下载原图</a>
          <button type="button" title="关闭" @click="closePreview">×</button>
        </div>
      </header>
      <div class="teacher-image-stage">
        <img
          :src="previewFile.url"
          alt="学生作答图片大图"
          :style="{ transform: `rotate(${previewRotation}deg) scale(${previewScale})` }"
        />
      </div>
    </div>
  </TeacherPageShell>
</template>

<script setup>
import { onMounted, onUnmounted, reactive, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { apiGet, apiPost } from "../api/client";
import TeacherPageShell from "../components/TeacherPageShell.vue";

const route = useRoute();
const loading = ref(true);
const error = ref("");
const items = ref([]);
const selected = ref(null);
const reviewStatus = ref("pending");
const grading = ref(false);
const gradeError = ref("");
const previewFile = ref(null);
const previewRotation = ref(0);
const previewScale = ref(1);
const scorePresets = [60, 75, 85, 90, 100];
const quickComments = ["步骤完整，思路清晰", "结论正确，过程需补充", "注意计算符号与书写规范", "关键定理使用不准确", "请按解析订正后再次提交"];
const gradeForm = reactive({ score: 80, feedback: "", correction_required: false });

function formatTime(value) { return value ? new Date(value).toLocaleString("zh-CN") : ""; }
function typeLabel(value) { return ({ choice: "选择题", blank: "填空题", calculation: "计算题", proof: "证明题", comprehensive: "综合题" })[value] || value; }

function select(item) {
  selected.value = item;
  gradeForm.score = item?.teacher_score ?? item?.score ?? 80;
  gradeForm.feedback = item?.teacher_feedback || "";
  gradeForm.correction_required = false;
  gradeError.value = "";
}

function appendComment(comment) {
  gradeForm.feedback = gradeForm.feedback.trim() ? `${gradeForm.feedback.trim()}；${comment}` : comment;
}

function openPreview(file) {
  previewFile.value = file;
  resetPreview();
}
function closePreview() { previewFile.value = null; }
function rotatePreview(delta) { previewRotation.value = (previewRotation.value + delta) % 360; }
function zoomPreview(delta) { previewScale.value = Math.max(0.5, Math.min(3, previewScale.value + delta)); }
function resetPreview() { previewRotation.value = 0; previewScale.value = 1; }
function handleKeydown(event) { if (event.key === "Escape" && previewFile.value) closePreview(); }

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const data = await apiGet("/api/teacher/review-queue", {
      assignment_id: route.query.assignment_id || "",
      review_status: reviewStatus.value
    });
    items.value = data.items || [];
    select(items.value[0] || null);
  } catch (exception) {
    error.value = exception.message;
  } finally {
    loading.value = false;
  }
}

async function grade() {
  grading.value = true;
  gradeError.value = "";
  try {
    await apiPost(`/api/teacher/submissions/${selected.value.id}/grade`, gradeForm);
    await load();
  } catch (exception) {
    gradeError.value = exception.message;
  } finally {
    grading.value = false;
  }
}

onMounted(() => { window.addEventListener("keydown", handleKeydown); load(); });
onUnmounted(() => window.removeEventListener("keydown", handleKeydown));
</script>
