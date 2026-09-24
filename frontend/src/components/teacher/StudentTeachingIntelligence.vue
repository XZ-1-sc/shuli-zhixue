<template>
  <section class="student-intelligence teacher-panel">
    <header><div><small>个体决策支持</small><strong>小逻会诊与补救</strong></div><span>所有结论需教师结合实际判断</span></header>
    <div class="student-intelligence-actions">
      <button v-for="item in actions" :key="item.kind" type="button" :disabled="loadingKind === item.kind" @click="generate(item.kind)"><b>{{ item.symbol }}</b><span><strong>{{ item.label }}</strong><small>{{ item.description }}</small></span></button>
    </div>
    <p v-if="error" class="student-intelligence-error">{{ error }}</p>
    <article v-if="artifact" class="student-artifact">
      <header><div><small>AI 辅助草稿 · 尚未对学生生效</small><strong>{{ artifact.content.headline }}</strong></div><button v-if="artifact.type === 'remediation' && artifact.status === 'draft'" type="button" :disabled="confirming" @click="confirmRemediation">{{ confirming ? "确认中…" : "教师确认并下发" }}</button></header>
      <section><div><h4>依据</h4><ul><li v-for="item in artifact.content.evidence" :key="item">{{ item }}</li></ul></div><div><h4>建议</h4><ol><li v-for="item in artifact.content.recommendations" :key="item">{{ item }}</li></ol></div></section>
      <div v-if="artifact.content.remediation_questions?.length" class="remediation-questions"><strong>递进练习包</strong><span v-for="(item, index) in artifact.content.remediation_questions" :key="item.id">{{ index + 1 }}. {{ item.question_text }}</span></div>
      <p v-if="confirmed" class="confirmed-note">已由教师确认并通知学生，任务入口已进入学生消息中心。</p>
    </article>
  </section>
</template>

<script setup>
import { ref } from "vue";
import { apiPost } from "../../api/client";
const props = defineProps({ studentId: { type: Number, required: true } });
const actions = [{ kind: "student_consultation", symbol: "诊", label: "学生会诊报告", description: "正确率、错因、用时与求助信号" }, { kind: "remediation", symbol: "补", label: "补救任务包", description: "3—5 道递进题，确认后下发" }, { kind: "breakpoint_review", symbol: "折", label: "拐点复盘", description: "定位近期改善或下滑线索" }, { kind: "engagement_review", symbol: "投", label: "投入度分析", description: "只解释行为证据，不推断态度" }];
const loadingKind = ref(""), confirming = ref(false), artifact = ref(null), error = ref(""), confirmed = ref(false);
async function generate(kind) { loadingKind.value = kind; error.value = ""; confirmed.value = false; try { artifact.value = await apiPost("/api/teacher/intelligence/artifacts", { kind, student_id: props.studentId, note: "请明确数据证据、解释边界与下一步可执行动作。" }); } catch (exception) { error.value = exception.message; } finally { loadingKind.value = ""; } }
async function confirmRemediation() { confirming.value = true; error.value = ""; try { await apiPost(`/api/teacher/intelligence/artifacts/${artifact.value.id}/confirm`, {}); artifact.value.status = "confirmed"; confirmed.value = true; } catch (exception) { error.value = exception.message; } finally { confirming.value = false; } }
</script>

<style scoped>
.student-intelligence{display:grid;gap:14px;margin-top:16px}.student-intelligence>header,.student-artifact>header{display:flex;align-items:center;justify-content:space-between;gap:10px}.student-intelligence>header>div,.student-artifact>header>div{display:grid;gap:3px}.student-intelligence small,.student-artifact small{color:#777067;font-size:11px}.student-intelligence-actions{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.student-intelligence-actions>button{display:flex;align-items:center;gap:9px;min-height:64px;padding:10px;color:#33302b;border:1px solid #ded7cb;background:#fff;text-align:left}.student-intelligence-actions>button>b{display:grid;place-items:center;width:31px;height:31px;color:#fff;border-radius:50%;background:#2e7d8c}.student-intelligence-actions span{display:grid;gap:3px}.student-intelligence-actions small{font-size:9px}.student-artifact{display:grid;gap:12px;padding:14px;border-left:3px solid #2e7d8c;background:#edf6f5}.student-artifact>header>button{min-height:36px;padding:0 12px;color:#fff;background:#2e7d8c;font-weight:850}.student-artifact>section{display:grid;grid-template-columns:1fr 1fr;gap:10px}.student-artifact>section>div{padding:10px;background:#fff}.student-artifact h4{margin:0 0 7px}.student-artifact ul,.student-artifact ol{margin:0;padding-left:18px;color:#555047;font-size:11px;line-height:1.65}.remediation-questions{display:grid;gap:6px;padding:10px;background:#fff}.remediation-questions span{color:#555047;font-size:11px}.confirmed-note{margin:0;color:#347a56;font-size:11px}.student-intelligence-error{margin:0;color:#ad5046}@media(max-width:850px){.student-intelligence-actions{grid-template-columns:1fr 1fr}}@media(max-width:540px){.student-intelligence>header,.student-artifact>header{align-items:flex-start;flex-direction:column}.student-intelligence-actions,.student-artifact>section{grid-template-columns:1fr}}
</style>
