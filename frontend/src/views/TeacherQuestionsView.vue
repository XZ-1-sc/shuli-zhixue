<template>
  <section class="teacher-view">
    <PageHeader title="题库管理" eyebrow="内容资产" description="浏览公共题库，维护教师自建题，发布后即可用于组卷。">
    <template #actions><button class="teacher-secondary-action" type="button" @click="aiOpen = true">✦ AI 出题</button><button class="teacher-secondary-action" type="button" @click="importOpen = true">⇧ 文件导入</button><RouterLink class="teacher-primary-action" to="/teacher/questions/new">＋ 新建题目</RouterLink></template>
    </PageHeader>
    <section class="teacher-metric-grid teacher-four-metrics"><article><span class="metric-icon cyan">▤</span><div><small>全部可用题目</small><strong>{{ summary.total }}</strong><p>开放与自建题库</p></div></article><article><span class="metric-icon blue">✎</span><div><small>我的题目</small><strong>{{ summary.mine }}</strong><p>当前教师创建</p></div></article><article><span class="metric-icon amber">◌</span><div><small>草稿</small><strong>{{ summary.drafts }}</strong><p>尚不可用于发布作业</p></div></article><article><span class="metric-icon green">✓</span><div><small>已发布</small><strong>{{ summary.published }}</strong><p>可直接组卷</p></div></article></section>
    <section class="teacher-filter-bar teacher-question-filters">
      <label><span>范围</span><select v-model="filters.scope" @change="resetLoad"><option value="all">全部可用</option><option value="mine">我的题目</option><option value="public">公共题库</option></select></label>
      <label><span>阶段</span><select v-model="filters.stage" @change="loadCoursesAndQuestions"><option value="">全部阶段</option><option v-for="item in stages" :key="item.stage_name" :value="item.stage_name">{{ item.stage_name }}</option></select></label>
      <label><span>课程</span><select v-model="filters.course" @change="resetLoad"><option value="">全部课程</option><option v-for="item in courses" :key="item.course_name" :value="item.course_name">{{ item.course_name }}</option></select></label>
      <label><span>题型</span><select v-model="filters.question_type" @change="resetLoad"><option value="">全部题型</option><option v-for="item in types" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
      <label class="teacher-search-field"><span>搜索</span><input v-model="filters.search" placeholder="题干、知识点或标签" @keyup.enter="resetLoad" /></label><button class="teacher-primary-action" @click="resetLoad">查询</button>
    </section>
    <p v-if="message" class="teacher-form-message" :class="{ 'is-error': messageError }">{{ message }}</p>
    <div v-if="loading" class="teacher-loading-grid"><i v-for="n in 8" :key="n"></i></div>
    <section v-else-if="error" class="teacher-state-panel is-error"><strong>题库暂时无法加载</strong><p>{{ error }}</p><button @click="loadQuestions">重试</button></section>
    <section v-else class="teacher-panel"><header><div><strong>题目列表</strong><small>第 {{ page }} 页 · 共 {{ total }} 道</small></div><span>草稿需发布后才能用于作业</span></header>
      <div v-if="questions.length" class="teacher-question-list"><article v-for="item in questions" :key="item.id"><header><span>{{ item.type_label }}</span><small>{{ item.stage }} · {{ item.course }}</small><em v-if="item.ai_generated" class="status-draft">AI 生成</em><em :class="`status-${item.publish_status}`">{{ statusText(item.publish_status) }}</em></header><h3>{{ item.question_text }}</h3><p>{{ item.knowledge_tag }} / {{ item.fine_tag }} · 难度 {{ item.difficulty }} · {{ item.source_name }}</p><footer><span v-if="item.question_type === 'choice'">答案 {{ item.correct_answer }}</span><span v-else>标准答案：{{ truncate(item.standard_answer, 60) }}</span><div><button type="button" @click="copyQuestion(item)">复制为草稿</button><template v-if="item.editable"><RouterLink :to="`/teacher/questions/${item.id}/edit`">审核编辑</RouterLink><button v-if="item.publish_status === 'draft'" @click="publishQuestion(item)">审核并发布</button><button v-if="item.publish_status !== 'archived'" class="danger" @click="archiveQuestion(item)">归档</button></template></div></footer></article></div><div v-else class="teacher-inline-empty">当前筛选条件下没有题目。</div>
      <footer v-if="total > filters.page_size" class="teacher-pagination"><button :disabled="page <= 1" @click="changePage(page - 1)">上一页</button><span>{{ page }} / {{ Math.ceil(total / filters.page_size) }}</span><button :disabled="page >= Math.ceil(total / filters.page_size)" @click="changePage(page + 1)">下一页</button></footer>
    </section>
    <QuestionImportDialog :open="importOpen" mode="bank" :initial-stage="filters.stage" :initial-course="filters.course" @close="importOpen = false" @imported="handleImported" />
    <TeacherAIQuestionDialog :open="aiOpen" :initial-course="filters.course" @close="aiOpen = false" @generated="handleGenerated" />
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue"; import { RouterLink, useRouter } from "vue-router";
import { apiGet, apiPost } from "../api/client"; import PageHeader from "../components/ui/PageHeader.vue"; import QuestionImportDialog from "../components/QuestionImportDialog.vue"; import TeacherAIQuestionDialog from "../components/TeacherAIQuestionDialog.vue"; import { requestConfirmation } from "../services/confirm";
const router=useRouter();
const loading=ref(true), error=ref(""), message=ref(""), messageError=ref(false), importOpen=ref(false), aiOpen=ref(false), questions=ref([]), total=ref(0), page=ref(1), stages=ref([]), courses=ref([]); const summary=reactive({total:0,mine:0,drafts:0,published:0});
const filters=reactive({scope:"all",search:"",stage:"",course:"",question_type:"",page_size:20}); const types=[{value:"choice",label:"选择题"},{value:"blank",label:"填空题"},{value:"calculation",label:"计算题"},{value:"proof",label:"证明题"},{value:"comprehensive",label:"综合题"}];
function truncate(v,n){const s=String(v||"");return s.length>n?`${s.slice(0,n)}…`:s;} function statusText(v){return ({draft:"草稿",published:"已发布",archived:"已归档"})[v]||v;}
async function loadQuestions(){loading.value=true;error.value="";try{const data=await apiGet("/api/teacher/questions",{...filters,page:page.value});questions.value=data.items||[];total.value=data.total||0;Object.assign(summary,data.summary||{});}catch(e){error.value=e.message;}finally{loading.value=false;}}
function resetLoad(){page.value=1;loadQuestions();} function changePage(v){page.value=v;loadQuestions();window.scrollTo({top:0,behavior:"smooth"});}
async function loadCoursesAndQuestions(){filters.course="";courses.value=filters.stage?(await apiGet("/api/courses",{stage:filters.stage})).courses||[]:[];resetLoad();}
async function publishQuestion(item){try{await apiPost(`/api/teacher/questions/${item.id}/publish`);messageError.value=false;message.value="题目已发布，可用于布置作业。";loadQuestions();}catch(e){messageError.value=true;message.value=e.message;}}
async function archiveQuestion(item){if(!(await requestConfirmation({title:"归档题目",description:"归档后将不再用于新作业，确定继续吗？",confirmLabel:"确认归档"})))return;try{await apiPost(`/api/teacher/questions/${item.id}/archive`);messageError.value=false;message.value="题目已归档。";loadQuestions();}catch(e){messageError.value=true;message.value=e.message;}}
async function copyQuestion(item){try{const data=await apiPost(`/api/teacher/questions/${item.id}/copy`);messageError.value=false;message.value="已复制为你的草稿题，正在打开编辑器。";await router.push(`/teacher/questions/${data.id}/edit`);}catch(e){messageError.value=true;message.value=e.message;}}
function handleGenerated(data){const created=data.created_count||0;messageError.value=!created;message.value=created?`已生成 ${created} 道 AI 私有草稿，请逐题审核后发布。`:(data.notice||"本次未生成题目，请调整条件后重试。");filters.scope="mine";resetLoad();}
function handleImported(data){messageError.value=Boolean(data.error_count);message.value=`已导入 ${data.created_count} 道草稿题${data.duplicate_count?`，跳过 ${data.duplicate_count} 道重复题`:""}${data.error_count?`，${data.error_count} 道失败`:""}。`;filters.scope="mine";resetLoad();}
onMounted(async()=>{try{stages.value=(await apiGet("/api/stages")).stages||[];}finally{loadQuestions();}});
</script>
