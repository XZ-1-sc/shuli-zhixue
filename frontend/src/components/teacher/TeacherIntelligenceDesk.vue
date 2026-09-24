<template>
  <section class="intelligence-desk teacher-panel">
    <header>
      <div><small>主动发现 · 建议可审阅</small><strong>小逻教学雷达</strong></div>
      <div class="desk-heading-actions"><button type="button" @click="preferencesOpen = !preferencesOpen">AI 偏好</button><button type="button" :disabled="scanning" @click="scan">{{ scanning ? "扫描中…" : "重新扫描" }}</button></div>
    </header>
    <p v-if="error" class="desk-error">{{ error }}</p>
    <form v-if="preferencesOpen" class="preference-form" @submit.prevent="savePreferences">
      <header><div><strong>教师偏好记忆</strong><small>用于调整草稿口吻与评分建议，所有输出仍标注为 AI 辅助</small></div></header>
      <label><span>讲评口吻</span><input v-model="preferences.tone" maxlength="64" /></label>
      <label><span>评分倾向</span><select v-model="preferences.scoring_strictness"><option value="lenient">相对宽松</option><option value="balanced">均衡</option><option value="strict">相对严格</option></select></label>
      <label class="preference-notes"><span>风格说明</span><textarea v-model="preferences.style_notes" maxlength="2000" placeholder="例如：先肯定有效步骤，再指出第一处偏差。"></textarea></label>
      <label class="assistant-switch"><input v-model="preferences.assistant_enabled" type="checkbox" /><span>允许小逻按已保存偏好起草（发送前仍需教师确认）</span></label>
      <button type="submit" :disabled="preferenceSaving">{{ preferenceSaving ? "保存中…" : "保存偏好" }}</button>
      <small v-if="preferenceSaved">偏好已保存，并会参与后续组卷、讲评与批改草稿。</small>
    </form>
    <div class="desk-grid">
      <section>
        <header><strong>风险信号</strong><span>{{ risks.length }}</span></header>
        <p v-if="!risks.length" class="desk-empty">暂未发现达到阈值的风险信号。</p>
        <article v-for="item in risks.slice(0, 6)" :key="item.id" :class="`severity-${item.severity}`">
          <div><small>{{ riskLabel(item.risk_type) }}</small><strong>{{ item.title }}</strong><span>{{ formatTime(item.detected_at) }}</span></div>
          <footer><RouterLink v-if="item.student_id" :to="`/teacher/students/${item.student_id}`">查看学生</RouterLink><RouterLink v-else-if="item.question_id" to="/teacher/questions">查看题目</RouterLink><button type="button" @click="resolveRisk(item)">标记已处理</button></footer>
        </article>
      </section>
      <section>
        <header><strong>学生求助信号</strong><span>{{ signals.length }}</span></header>
        <p v-if="!signals.length" class="desk-empty">暂无连续错误触发的求助信号。</p>
        <article v-for="item in signals.slice(0, 6)" :key="item.id">
          <div><small>{{ item.class_name }} · {{ item.knowledge_tag }}</small><strong>{{ item.student }}</strong><span>连续错误后触发，请结合实际判断</span></div>
          <footer><RouterLink :to="`/teacher/students/${item.student_id}`">查看与联系</RouterLink><button type="button" @click="resolveSignal(item)">完成跟进</button></footer>
        </article>
      </section>
    </div>
    <section class="decision-workbench">
      <header><div><strong>决策与代劳草稿</strong><small>所有内容默认保存为草稿，不会自动发布或落分</small></div></header>
      <div class="decision-command">
        <select v-model="kind"><option v-for="item in kinds" :key="item.value" :value="item.value">{{ item.label }}</option></select>
        <select v-if="needsClass" v-model="classId"><option value="" disabled>选择班级</option><option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}</option></select>
        <input v-model="note" placeholder="补充课堂进度或关注点（可选）" />
        <button type="button" :disabled="generating || (needsClass && !classId)" @click="generate">{{ generating ? "生成中…" : "生成草稿" }}</button>
      </div>
      <article v-if="artifact" class="artifact-preview"><header><small>AI 辅助草稿 · 教师确认后使用</small><strong>{{ artifact.headline }}</strong></header><ul><li v-for="item in artifact.evidence" :key="item">{{ item }}</li></ul><ol><li v-for="item in artifact.recommendations" :key="item">{{ item }}</li></ol></article>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { apiGet, apiPost, apiPut } from "../../api/client";
const props = defineProps({ classes: { type: Array, default: () => [] } });
const risks = ref([]), signals = ref([]), error = ref(""), scanning = ref(false), generating = ref(false), artifact = ref(null), note = ref("");
const preferencesOpen = ref(false), preferenceSaving = ref(false), preferenceSaved = ref(false);
const preferences = ref({ tone: "清晰、鼓励、重方法", scoring_strictness: "balanced", preferred_types: [], style_notes: "", assistant_enabled: true });
const kind = ref("weekly_report"), classId = ref("");
const classes = computed(() => props.classes || []);
const kinds = [{ value: "weekly_report", label: "班级学情周报" }, { value: "next_lesson", label: "下堂课建议" }, { value: "layered_teaching", label: "分层教学建议" }, { value: "pace_review", label: "教学节奏诊断" }, { value: "question_health", label: "题目健康巡检" }, { value: "substitute_handoff", label: "代课交接包" }, { value: "cross_class", label: "跨班横向对比" }, { value: "semester_review", label: "学期教学复盘" }];
const needsClass = computed(() => !["cross_class", "semester_review"].includes(kind.value));
function riskLabel(value) { return ({ student_inactive: "活跃度", consecutive_wrong: "连续错误", question_health: "题目健康" })[value] || "教学风险"; }
function formatTime(value) { return value ? new Date(value).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : ""; }
async function load() { try { const [riskData, signalData, preferenceData] = await Promise.all([apiGet("/api/teacher/intelligence/risks"), apiGet("/api/teacher/intelligence/help-signals"), apiGet("/api/teacher/ai/preferences")]); risks.value = riskData.items || []; signals.value = signalData.items || []; preferences.value = { ...preferences.value, ...preferenceData }; classId.value ||= classes.value[0]?.id || ""; } catch (exception) { error.value = exception.message; } }
async function scan() { scanning.value = true; error.value = ""; try { const data = await apiPost("/api/teacher/intelligence/risks/scan", {}); risks.value = data.items || []; } catch (exception) { error.value = exception.message; } finally { scanning.value = false; } }
async function resolveRisk(item) { await apiPut(`/api/teacher/intelligence/risks/${item.id}`, { status: "resolved" }); risks.value = risks.value.filter((risk) => risk.id !== item.id); }
async function resolveSignal(item) { await apiPut(`/api/teacher/intelligence/help-signals/${item.id}`, { status: "resolved" }); signals.value = signals.value.filter((signal) => signal.id !== item.id); }
async function generate() { generating.value = true; error.value = ""; artifact.value = null; try { const data = await apiPost("/api/teacher/intelligence/artifacts", { kind: kind.value, class_id: needsClass.value ? Number(classId.value) : null, note: note.value }); artifact.value = data.content; } catch (exception) { error.value = exception.message; } finally { generating.value = false; } }
async function savePreferences() { preferenceSaving.value = true; preferenceSaved.value = false; error.value = ""; try { preferences.value = await apiPut("/api/teacher/ai/preferences", preferences.value); preferenceSaved.value = true; } catch (exception) { error.value = exception.message; } finally { preferenceSaving.value = false; } }
onMounted(load);
</script>

<style scoped>
.intelligence-desk{display:grid;gap:15px;margin-bottom:16px}.intelligence-desk>header,.desk-grid>section>header,.decision-workbench>header,.artifact-preview>header{display:flex;align-items:center;justify-content:space-between;gap:12px}.intelligence-desk>header>div{display:grid;gap:3px}.intelligence-desk>header small,.decision-workbench small,.artifact-preview small{color:#777067;font-size:11px}.intelligence-desk>header>div strong{font-size:18px}.intelligence-desk button{min-height:34px;padding:0 10px;color:#287381;border:1px solid rgba(46,125,140,.32);background:#fff;font-weight:800}.desk-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.desk-grid>section{display:grid;align-content:start;gap:8px;padding:13px;border:1px solid #ded7cb;background:#faf7f0}.desk-grid>section>header>span{display:grid;place-items:center;min-width:25px;height:25px;color:#fff;border-radius:50%;background:#706b62;font-size:11px}.desk-grid article{display:grid;gap:8px;padding:11px;border-left:3px solid #b17d1e;background:#fff}.desk-grid article.severity-high{border-left-color:#b4554a}.desk-grid article.severity-low{border-left-color:#2e7d8c}.desk-grid article>div{display:grid;gap:3px}.desk-grid article small{color:#817a70;font-size:10px}.desk-grid article strong{font-size:12px}.desk-grid article span{color:#817a70;font-size:10px}.desk-grid footer{display:flex;align-items:center;justify-content:flex-end;gap:7px}.desk-grid footer a{color:#287381;font-size:11px;font-weight:800;text-decoration:none}.desk-grid footer button{min-height:28px;font-size:10px}.decision-workbench{display:grid;gap:11px;padding-top:14px;border-top:1px solid #ded7cb}.decision-command{display:grid;grid-template-columns:180px 180px 1fr auto;gap:8px}.decision-command select,.decision-command input{min-width:0;min-height:38px;padding:0 9px;color:#33302b;border:1px solid #ded7cb;background:#fff}.artifact-preview{display:grid;gap:10px;padding:13px;border-left:3px solid #2e7d8c;background:#edf6f5}.artifact-preview>header{display:grid;justify-content:start}.artifact-preview ul,.artifact-preview ol{margin:0;padding-left:19px;color:#514c45;font-size:11px;line-height:1.65}.desk-empty,.desk-error{margin:0;color:#817a70;font-size:11px}.desk-error{color:#ad5046}@media(max-width:900px){.decision-command{grid-template-columns:1fr 1fr}.decision-command input{grid-column:1/-1}}@media(max-width:650px){.desk-grid{grid-template-columns:1fr}.decision-command{grid-template-columns:1fr}.decision-command input{grid-column:auto}}
.desk-heading-actions{display:flex!important;gap:7px}.preference-form{display:grid;grid-template-columns:1fr 180px auto;align-items:end;gap:10px;padding:13px;border:1px solid #ded7cb;background:#faf7f0}.preference-form>header,.preference-form .preference-notes,.preference-form .assistant-switch,.preference-form>small{grid-column:1/-1}.preference-form>header>div,.preference-form label{display:grid;gap:5px}.preference-form input,.preference-form select,.preference-form textarea{min-height:38px;padding:8px;color:#33302b;border:1px solid #ded7cb;background:#fff}.preference-form textarea{min-height:68px;resize:vertical}.preference-form .assistant-switch{display:flex;align-items:center}.preference-form .assistant-switch input{min-height:auto}.preference-form>button{color:#fff;background:#2e7d8c}.preference-form>small{color:#347a56}@media(max-width:900px){.preference-form{grid-template-columns:1fr 1fr}}@media(max-width:650px){.preference-form{grid-template-columns:1fr}}
</style>
