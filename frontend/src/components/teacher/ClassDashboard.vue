<template>
  <section class="class-dashboard teacher-panel" aria-labelledby="class-dashboard-title">
    <header class="dashboard-heading">
      <div>
        <small>近 7 天 · 仅统计正式练习</small>
        <strong id="class-dashboard-title">班级学情驾驶舱</strong>
      </div>
      <button type="button" :disabled="loading || generating" @click="generateLesson">
        {{ generating ? "生成中…" : "✦ 生成下堂课建议" }}
      </button>
    </header>

    <p v-if="error" class="dashboard-message is-error">{{ error }}</p>
    <div v-if="loading" class="dashboard-loading"><i v-for="item in 4" :key="item"></i></div>
    <template v-else-if="dashboard">
      <div class="dashboard-grid">
        <article class="trend-card">
          <header><strong>练习趋势</strong><span>作答量 / 正确率</span></header>
          <div class="trend-chart">
            <div v-for="item in dashboard.trend_7d" :key="item.date" class="trend-column">
              <span :style="{ height: `${Math.max(4, attemptHeight(item.attempts))}%` }"></span>
              <i :style="{ bottom: `${Math.max(2, item.accuracy)}%` }" :title="`正确率 ${item.accuracy}%`"></i>
              <small>{{ shortDate(item.date) }}</small>
            </div>
          </div>
        </article>

        <article class="mastery-card">
          <header><strong>薄弱知识点</strong><span>按正确率排序</span></header>
          <div v-if="dashboard.knowledge_bottom?.length" class="mastery-list">
            <div v-for="item in dashboard.knowledge_bottom" :key="item.knowledge_tag">
              <span><b>{{ item.knowledge_tag }}</b><small>{{ item.attempts }} 次</small></span>
              <i><em :style="{ width: `${item.accuracy}%` }"></em></i>
              <strong>{{ item.accuracy }}%</strong>
            </div>
          </div>
          <p v-else class="inline-empty">还没有可聚合的正式作答。</p>
        </article>

        <article class="mistake-card">
          <header><strong>错因分布</strong><span>Top 6</span></header>
          <div v-if="dashboard.mistake_distribution?.length" class="reason-list">
            <div v-for="item in dashboard.mistake_distribution.slice(0, 6)" :key="item.reason">
              <span>{{ item.reason }}</span><i><em :style="{ width: `${reasonWidth(item.count)}%` }"></em></i><b>{{ item.count }}</b>
            </div>
          </div>
          <p v-else class="inline-empty">错题产生后会显示可核验错因。</p>
        </article>

        <article class="activity-card">
          <header><strong>学生活跃度</strong><span>按需关注</span></header>
          <div v-if="dashboard.student_activity?.length" class="activity-list">
            <RouterLink v-for="item in dashboard.student_activity.slice(0, 7)" :key="item.student_id" :to="`/teacher/students/${item.student_id}`">
              <span><b>{{ item.student }}</b><small>{{ item.study_minutes_7d }} 分钟</small></span>
              <strong>{{ item.attempts_7d }} 题</strong>
            </RouterLink>
          </div>
          <p v-else class="inline-empty">班级中还没有学习记录。</p>
        </article>
      </div>

      <section class="heat-card">
        <header><div><strong>学生 × 知识点错误热力</strong><small>颜色越深，错误率越高；“—”表示暂无样本</small></div></header>
        <div v-if="dashboard.heatmap?.columns?.length" class="heat-scroll">
          <table>
            <thead><tr><th>学生</th><th v-for="tag in dashboard.heatmap.columns" :key="tag" :title="tag">{{ tag }}</th></tr></thead>
            <tbody>
              <tr v-for="row in dashboard.heatmap.rows" :key="row.student_id">
                <th>{{ row.student }}</th>
                <td v-for="cell in row.cells" :key="cell.knowledge_tag" :style="cellStyle(cell)" :title="cell.attempts ? `${cell.attempts} 次作答，错误率 ${cell.error_rate}%` : '暂无样本'">
                  {{ cell.attempts ? `${cell.error_rate}%` : "—" }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="inline-empty">至少完成一次正式练习后生成热力矩阵。</p>
      </section>

      <section class="issues-card">
        <header><div><strong>共性讲评区</strong><small>至少 3 名学生共错才会进入清单</small></div><span>{{ issues.length }} 项</span></header>
        <div v-if="issues.length" class="issue-list">
          <article v-for="item in issues.slice(0, 6)" :key="item.question_id">
            <span>{{ item.fine_tag || item.knowledge_tag }}</span>
            <strong>{{ item.student_count }} 名学生共错</strong>
            <p>{{ item.question_text }}</p>
            <button type="button" @click="askXiaoluo(item)">问小逻生成讲评材料</button>
          </article>
        </div>
        <p v-else class="inline-empty">当前没有达到共错阈值的问题。</p>
      </section>

      <section v-if="lessonDraft" class="lesson-draft" aria-live="polite">
        <header><small>AI 辅助草稿 · 教师确认后使用</small><strong>{{ lessonDraft.headline }}</strong></header>
        <ul><li v-for="item in lessonDraft.recommendations" :key="item">{{ item }}</li></ul>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import { apiGet, apiPost } from "../../api/client";

const props = defineProps({ classId: { type: Number, required: true } });
const dashboard = ref(null);
const issues = ref([]);
const lessonDraft = ref(null);
const loading = ref(true);
const generating = ref(false);
const error = ref("");

const maxAttempts = computed(() => Math.max(1, ...(dashboard.value?.trend_7d || []).map((item) => Number(item.attempts || 0))));
const maxReasons = computed(() => Math.max(1, ...(dashboard.value?.mistake_distribution || []).map((item) => Number(item.count || 0))));
function attemptHeight(value) { return Math.round(Number(value || 0) / maxAttempts.value * 86); }
function reasonWidth(value) { return Math.round(Number(value || 0) / maxReasons.value * 100); }
function shortDate(value) { return String(value || "").slice(5).replace("-", "/"); }
function cellStyle(cell) {
  if (!cell.attempts) return { background: "#f5f1e9", color: "#9b958b" };
  const alpha = Math.min(0.72, 0.1 + Number(cell.error_rate || 0) / 150);
  return { background: `rgba(180, 85, 74, ${alpha})`, color: alpha > 0.48 ? "#fff" : "#5d302c" };
}

async function load() {
  if (!props.classId) return;
  loading.value = true; error.value = ""; lessonDraft.value = null;
  try {
    const [data, common] = await Promise.all([
      apiGet(`/api/teacher/classes/${props.classId}/dashboard`),
      apiGet(`/api/teacher/classes/${props.classId}/common-issues`)
    ]);
    dashboard.value = data;
    issues.value = common.items || [];
  } catch (exception) { error.value = exception.message || "班级驾驶舱加载失败。"; }
  finally { loading.value = false; }
}

async function generateLesson() {
  generating.value = true; error.value = "";
  try {
    const data = await apiPost("/api/teacher/intelligence/artifacts", { kind: "next_lesson", class_id: props.classId, note: "围绕班级共性错题给出课堂例题和一分钟自测建议。" });
    lessonDraft.value = data.content;
  } catch (exception) { error.value = exception.message || "下堂课建议生成失败。"; }
  finally { generating.value = false; }
}

function askXiaoluo(item) {
  window.dispatchEvent(new CustomEvent("xiaoluo:open", { detail: {
    prompt: `请围绕“${item.fine_tag || item.knowledge_tag}”生成一份可直接审阅的讲评材料。已有 ${item.student_count} 名学生在同一道题上出错，请先解释概念边界，再给课堂例题和 1 分钟自测。`,
    autoSend: true
  } }));
}

watch(() => props.classId, load);
onMounted(load);
</script>

<style scoped>
.class-dashboard{margin-top:16px}.dashboard-heading,.class-dashboard article>header,.heat-card>header,.issues-card>header,.lesson-draft>header{display:flex;align-items:center;justify-content:space-between;gap:12px}.dashboard-heading>div,.lesson-draft>header{display:grid;gap:4px}.dashboard-heading small,.class-dashboard article header span,.heat-card small,.issues-card small,.lesson-draft small{color:#777067;font-size:12px}.dashboard-heading>div>strong{font-size:18px;color:#33302b}.dashboard-heading>button,.issue-list button{min-height:36px;padding:0 13px;border:1px solid rgba(46,125,140,.35);border-radius:9px;color:#287381;background:#fff;font-weight:800}.dashboard-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;margin-top:16px;background:#ded7cb;border:1px solid #ded7cb}.dashboard-grid>article{min-width:0;padding:16px;background:#fff}.trend-chart{display:flex;align-items:flex-end;height:150px;gap:7px;padding:16px 4px 0;border-bottom:1px solid #ded7cb}.trend-column{position:relative;display:flex;flex:1;align-items:flex-end;justify-content:center;height:120px}.trend-column>span{width:min(25px,64%);background:#d9ecee;border-radius:3px 3px 0 0}.trend-column>i{position:absolute;width:8px;height:8px;border:2px solid #fff;border-radius:50%;background:#2e7d8c;transform:translateY(50%)}.trend-column small{position:absolute;bottom:-23px;color:#827b71;font-size:10px}.mastery-list,.reason-list,.activity-list{display:grid;gap:10px;margin-top:16px}.mastery-list>div,.reason-list>div,.activity-list>a{display:grid;grid-template-columns:minmax(100px,1.2fr) minmax(80px,1fr) 44px;align-items:center;gap:9px;color:#33302b;text-decoration:none}.mastery-list span,.activity-list span{display:grid}.mastery-list span small,.activity-list small{color:#827b71;font-size:10px}.mastery-list i,.reason-list i{height:7px;overflow:hidden;background:#ece6dc}.mastery-list em,.reason-list em{display:block;height:100%;background:#2e7d8c}.mastery-list>div>strong,.reason-list b,.activity-list>a>strong{text-align:right;font-size:12px}.reason-list>div{grid-template-columns:minmax(90px,1.1fr) minmax(70px,1fr) 24px;font-size:12px}.activity-list>a{grid-template-columns:1fr auto;padding-bottom:8px;border-bottom:1px solid #eee8df}.heat-card,.issues-card{margin-top:16px;padding-top:16px;border-top:1px solid #ded7cb}.heat-scroll{margin-top:12px;overflow:auto}.heat-scroll table{width:100%;min-width:620px;border-collapse:collapse;font-size:11px}.heat-scroll th,.heat-scroll td{min-width:74px;padding:9px 7px;border:1px solid #e4ddd2;text-align:center}.heat-scroll thead th{position:sticky;top:0;max-width:110px;overflow:hidden;text-overflow:ellipsis;color:#5f5a52;background:#f7f3eb;white-space:nowrap}.heat-scroll tbody th{position:sticky;left:0;text-align:left;color:#33302b;background:#fff}.issue-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:12px}.issue-list article{display:grid;align-content:start;gap:8px;padding:13px;border:1px solid #e1dacf;background:#fff}.issue-list article>span{color:#287381;font-size:11px;font-weight:800}.issue-list article>strong{font-size:13px}.issue-list p{display:-webkit-box;overflow:hidden;margin:0;color:#6d675e;font-size:12px;line-height:1.55;-webkit-box-orient:vertical;-webkit-line-clamp:2}.lesson-draft{display:grid;gap:10px;margin-top:14px;padding:15px;border-left:3px solid #2e7d8c;background:#edf6f5}.lesson-draft ul{margin:0;padding-left:20px;color:#49453f;line-height:1.65}.dashboard-loading{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:16px}.dashboard-loading i{height:120px;background:#eee9df;animation:pulse 1.2s ease-in-out infinite alternate}.dashboard-message{margin:12px 0 0;color:#ad5046}.inline-empty{margin:18px 0 0;color:#888177;font-size:12px}@keyframes pulse{to{opacity:.45}}@media(max-width:820px){.dashboard-grid{grid-template-columns:1fr}.issue-list{grid-template-columns:1fr 1fr}}@media(max-width:560px){.dashboard-heading{align-items:flex-start;flex-direction:column}.issue-list{grid-template-columns:1fr}.dashboard-loading{grid-template-columns:1fr 1fr}}
</style>
