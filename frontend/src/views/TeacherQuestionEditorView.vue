<template>
  <TeacherPageShell active="questions" :title="isEdit ? '编辑题目' : '新建题目'" eyebrow="题目编辑器" description="题干、答案、解析与错因标签完整保存；草稿不会进入学生练习。">
    <template #actions><RouterLink class="teacher-secondary-action" to="/teacher/questions">← 返回题库</RouterLink></template>
    <form class="teacher-editor-layout" @submit.prevent="save('draft')">
      <section class="teacher-panel teacher-editor-form">
        <header><div><strong>题目内容</strong><small>带 * 的项目为必填</small></div></header>
        <div class="teacher-form-grid">
          <label><span>题型 *</span><select v-model="form.question_type"><option v-for="item in types" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          <label><span>阶段 *</span><select v-model="form.stage" @change="loadCourses"><option v-for="item in stages" :key="item.stage_name" :value="item.stage_name">{{ item.stage_name }}</option></select></label>
          <label><span>课程 *</span><select v-model="form.course"><option v-for="item in courses" :key="item.course_name" :value="item.course_name">{{ item.course_name }}</option></select></label>
          <label><span>难度</span><select v-model.number="form.difficulty"><option v-for="n in 5" :key="n" :value="n">{{ n }} 级</option></select></label>
          <label><span>知识点 *</span><input v-model="form.knowledge_tag" placeholder="例如：极限与连续" required /></label>
          <label><span>细分标签 *</span><input v-model="form.fine_tag" placeholder="例如：两个重要极限" required /></label>
          <label class="span-all"><span>题干 *</span><textarea v-model="form.question_text" rows="5" placeholder="支持输入数学公式文本，例如 lim(x→0) sinx/x" required></textarea></label>
          <ImageUploader class="span-all" title="题干图片" description="用于函数图像、几何图形或材料题插图。" :files="questionImages" :busy="uploading" @choose="chooseImages('question')" @remove="removeImage($event, 'question')" />
          <input ref="questionImageInput" hidden type="file" multiple accept="image/jpeg,image/png,image/webp" @change="uploadImages($event, 'question')" />
          <template v-if="form.question_type === 'choice'">
            <label v-for="key in ['a','b','c','d']" :key="key"><span>选项 {{ key.toUpperCase() }} *</span><input v-model="form[`option_${key}`]" required /></label>
            <label><span>正确答案 *</span><select v-model="form.correct_answer"><option v-for="key in ['A','B','C','D']" :key="key">{{ key }}</option></select></label>
          </template>
          <label class="span-all"><span>标准答案 *</span><textarea v-model="form.standard_answer" rows="4" required></textarea></label>
          <label class="span-all"><span>详细解析 *</span><textarea v-model="form.analysis_text" rows="6" required></textarea></label>
          <ImageUploader class="span-all" title="解析图片" description="用于步骤批注、图形证明或参考解法。" :files="analysisImages" :busy="uploading" @choose="chooseImages('analysis')" @remove="removeImage($event, 'analysis')" />
          <input ref="analysisImageInput" hidden type="file" multiple accept="image/jpeg,image/png,image/webp" @change="uploadImages($event, 'analysis')" />
          <label class="span-all"><span>关键步骤（每行一项）</span><textarea v-model="keyStepsText" rows="4" placeholder="第一步：…&#10;第二步：…"></textarea></label>
          <label class="span-all"><span>常见错误（每行一项）</span><textarea v-model="commonErrorsText" rows="3"></textarea></label>
          <label class="span-all"><span>错因标签（每行一项）</span><textarea v-model="mistakeTagsText" rows="3"></textarea></label>
        </div>
      </section>
      <aside class="teacher-editor-aside">
        <section class="teacher-panel teacher-preview-card"><header><div><strong>实时预览</strong><small>{{ typeLabel }}</small></div></header><div><small>{{ form.stage }} · {{ form.course }} · 难度 {{ form.difficulty }}</small><h3>{{ form.question_text || '在左侧输入题干后，这里会显示预览。' }}</h3><div v-if="questionImages.length" class="teacher-preview-images"><img v-for="file in questionImages" :key="file.id" :src="file.url" :alt="file.name" /></div><ol v-if="form.question_type==='choice'"><li v-for="key in ['A','B','C','D']" :key="key"><b>{{ key }}</b>{{ form[`option_${key.toLowerCase()}`] || `选项 ${key}` }}</li></ol><p><strong>知识点：</strong>{{ form.knowledge_tag || '未填写' }} / {{ form.fine_tag || '未填写' }}</p></div></section>
        <section class="teacher-panel teacher-publish-panel"><header><div><strong>保存设置</strong><small>发布后可用于组卷</small></div></header><label><span>可见范围</span><select v-model="form.visibility"><option value="public">教师题库公开</option><option value="class">仅我的班级</option></select></label><p v-if="error" class="teacher-form-message is-error">{{ error }}</p><button class="teacher-secondary-action" :disabled="saving" type="submit">保存草稿</button><button class="teacher-primary-action" :disabled="saving" type="button" @click="save('published')">{{ saving ? '保存中…' : '保存并发布' }}</button></section>
      </aside>
    </form>
  </TeacherPageShell>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { apiDelete, apiGet, apiPost, apiPut, apiUpload } from "../api/client";
import TeacherPageShell from "../components/TeacherPageShell.vue";

const ImageUploader = defineComponent({
  props: { title: String, description: String, files: Array, busy: Boolean },
  emits: ["choose", "remove"],
  setup(props, { emit }) {
    return () => h("section", { class: "teacher-editor-upload" }, [
      h("div", [h("span", props.title), h("small", props.description)]),
      h("button", { type: "button", disabled: props.busy || props.files.length >= 5, onClick: () => emit("choose") }, props.busy ? "上传中…" : "+ 上传图片"),
      props.files.length ? h("div", { class: "teacher-editor-image-list" }, props.files.map((file) => h("article", { key: file.id }, [h("img", { src: file.url, alt: file.name }), h("span", file.name), h("button", { type: "button", onClick: () => emit("remove", file) }, "×")])) ) : null
    ]);
  }
});

const route = useRoute(); const router = useRouter();
const isEdit = computed(() => Boolean(route.params.questionId));
const stages = ref([]); const courses = ref([]); const saving = ref(false); const uploading = ref(false); const error = ref("");
const questionImageInput = ref(null); const analysisImageInput = ref(null); const questionImages = ref([]); const analysisImages = ref([]);
const keyStepsText = ref(""); const commonErrorsText = ref(""); const mistakeTagsText = ref("");
const types = [{ value: "choice", label: "选择题" }, { value: "blank", label: "填空题" }, { value: "calculation", label: "计算题" }, { value: "proof", label: "证明题" }, { value: "comprehensive", label: "综合题" }];
const form = reactive({ question_type: "choice", stage: "大一", course: "", knowledge_tag: "", fine_tag: "", difficulty: 3, question_text: "", option_a: "", option_b: "", option_c: "", option_d: "", correct_answer: "A", standard_answer: "", analysis_text: "", visibility: "public" });
const typeLabel = computed(() => types.find((item) => item.value === form.question_type)?.label || "");

function lines(value) { return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean); }
async function loadCourses() { courses.value = (await apiGet("/api/courses", { stage: form.stage })).courses || []; if (!courses.value.some((item) => item.course_name === form.course)) form.course = courses.value[0]?.course_name || ""; }
function chooseImages(type) { (type === "question" ? questionImageInput.value : analysisImageInput.value)?.click(); }
async function uploadImages(event, type) { const files = [...(event.target.files || [])]; if (!files.length) return; uploading.value = true; try { const data = new FormData(); files.forEach((file) => data.append("files", file)); const result = await apiUpload("/api/uploads/question-images", data); const target = type === "question" ? questionImages : analysisImages; target.value.push(...(result.files || []).map((file) => ({ ...file, url: file.url }))); } catch (e) { error.value = e.message; } finally { uploading.value = false; event.target.value = ""; } }
async function removeImage(file, type) { const target = type === "question" ? questionImages : analysisImages; if (!isEdit.value) { try { await apiDelete(`/api/uploads/${file.id}`); } catch (e) { error.value = e.message; return; } } target.value = target.value.filter((item) => item.id !== file.id); }
async function save(publishStatus) { saving.value = true; error.value = ""; try { const payload = { ...form, key_steps: lines(keyStepsText.value), common_errors: lines(commonErrorsText.value), mistake_tags: lines(mistakeTagsText.value), attachment_ids: questionImages.value.map((item) => item.id), analysis_attachment_ids: analysisImages.value.map((item) => item.id), publish_status: publishStatus }; if (isEdit.value) await apiPut(`/api/teacher/questions/${route.params.questionId}`, payload); else await apiPost("/api/teacher/questions", payload); router.push("/teacher/questions"); } catch (e) { error.value = e.message; } finally { saving.value = false; } }

onMounted(async () => { try { stages.value = (await apiGet("/api/stages")).stages || []; if (isEdit.value) { const data = await apiGet(`/api/teacher/questions/${route.params.questionId}`); Object.keys(form).forEach((key) => { if (data[key] !== undefined && data[key] !== null) form[key] = data[key]; }); questionImages.value = data.attachments || []; analysisImages.value = data.analysis_attachments || []; keyStepsText.value = (data.key_steps || []).join("\n"); commonErrorsText.value = (data.common_errors || []).join("\n"); mistakeTagsText.value = (data.mistake_tags || []).join("\n"); } await loadCourses(); } catch (e) { error.value = e.message; } });
</script>
