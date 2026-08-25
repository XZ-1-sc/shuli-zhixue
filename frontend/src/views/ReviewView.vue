<template>
  <section class="review-page-shell">
    <section class="review-ai-report">
      <AICard :card="analysisCard" @action="handleAIAction" />
    </section>
    <main class="review-layout">
      <article class="surface review-list">
        <div class="section-head">
          <div>
            <p class="eyebrow">错题复盘</p>
            <h2>按错因回炉</h2>
          </div>
          <button class="ghost-button" type="button" @click="load">刷新</button>
        </div>

        <div v-if="items.length" class="wrong-stack">
          <article
            v-for="item in items"
            :key="item.record_id"
            class="wrong-card-row"
          >
            <button class="wrong-card" :class="{ active: active?.record_id === item.record_id }" type="button" @click="active = item">
              <span>{{ item.course }} · {{ item.fine_tag || item.knowledge_tag }}</span>
              <strong>{{ item.question_text.slice(0, 92) }}...</strong>
              <small>得分 {{ item.score }} · {{ (item.record_mistake_tags || item.mistake_tags || []).join(" / ") }}</small>
            </button>
            <button class="wrong-ask-ai" type="button" @click="askXiaoluo(item)">问小逻</button>
          </article>
        </div>
        <div v-else class="empty-state">
          <h3>还没有错题记录</h3>
          <p class="muted">完成一组练习并提交答案后，错题会自动进入这里。</p>
          <RouterLink class="primary-button" to="/practice?mode=daily&limit=12">去做首测</RouterLink>
        </div>
      </article>

      <aside class="surface review-detail">
        <p class="eyebrow">解析</p>
        <h2>{{ active ? active.course : "选择一道错题" }}</h2>
        <template v-if="active">
          <p class="question-text compact">{{ active.question_text }}</p>
          <section>
            <strong>标准答案</strong>
            <p>{{ active.standard_answer }}</p>
          </section>
          <button class="review-ask-ai" type="button" @click="askXiaoluo(active)">◉ 让小逻拆解这道错题</button>
          <button class="review-share-question" type="button" @click="shareQuestion(active)">↗ 分享给老师 / 同学</button>
          <section>
            <strong>关键步骤</strong>
            <ol>
              <li v-for="step in active.key_steps" :key="step">{{ step }}</li>
            </ol>
          </section>
          <section>
            <strong>错因标签</strong>
            <div class="tag-row">
              <span v-for="tag in active.record_mistake_tags || active.mistake_tags" :key="tag">{{ tag }}</span>
            </div>
          </section>
          <RouterLink
            class="primary-button wide"
            :to="`/practice?stage=${active.stage}&course=${active.course}&knowledge_tag=${active.knowledge_tag}&mode=wrong_book&limit=10`"
          >
            加入回炉练习
          </RouterLink>
        </template>
        <p v-else class="muted">这里会显示题目解析、关键步骤、常见错误，以及下一组推荐练习。</p>
      </aside>
    </main>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";

import { apiGet } from "../api/client";
import AICard from "../components/ui/AICard.vue";
import { useUserStore } from "../stores/user";

const user = useUserStore();
const router = useRouter();
const items = ref([]);
const active = ref(null);
const analysis = ref({ reason_distribution: [], weak_knowledge: [], suggestion: "完成练习后生成错因报告。", wrong_count: 0 });
const analysisCard = computed(() => ({
  type: "reason",
  title: analysis.value.wrong_count ? `AI 错因分析 · ${analysis.value.wrong_count} 道错题` : "AI 错因分析",
  summary: analysis.value.suggestion,
  metrics: [
    { label: "错题数量", value: `${analysis.value.wrong_count || 0} 题` },
    { label: "主要错因", value: analysis.value.reason_distribution?.[0]?.label || "待生成" },
    { label: "首要薄弱点", value: analysis.value.weak_knowledge?.[0]?.fine_tag || "待生成" }
  ],
  mistakes: analysis.value.reason_distribution?.slice(0, 5) || [],
  details: (analysis.value.weak_knowledge || []).slice(0, 5).map((item) => ({ label: item.course, value: `${item.fine_tag} · 错 ${item.wrong_count} 次` })),
  actions: [{ label: "问小逻如何改进", type: "prompt", prompt: "请根据我的错因报告，给出未来 7 天的纠错安排。", context: { type: "diagnosis" } }]
}));

async function load() {
  if (!user.userId) {
    items.value = [];
    active.value = null;
    return;
  }
  const [data, report] = await Promise.all([apiGet("/api/review/wrong-questions", { limit: 30 }), apiGet("/api/review/analysis")]);
  items.value = data.items || [];
  analysis.value = report;
  active.value = items.value[0] || null;
}

function askXiaoluo(item) {
  window.dispatchEvent(new CustomEvent("xiaoluo:open", { detail: { prompt: "请结合这道错题、我的答案和同类错误，定位根因并给出订正步骤。", context: { type: "wrong", question_id: item.id, record_id: item.record_id }, autoSend: true } }));
}
async function shareQuestion(item) {
  sessionStorage.setItem("pending_message_question_ref", JSON.stringify({ question_id: item.id, record_id: item.record_id }));
  await router.push("/messages");
}
function handleAIAction(action) { window.dispatchEvent(new CustomEvent("xiaoluo:open", { detail: { prompt: action.prompt, context: action.context, autoSend: true } })); }

onMounted(load);
</script>

<style scoped>
.review-page-shell { grid-template-rows: auto auto; align-content: start; }
.review-ai-report { width:min(1180px,calc(100% - 36px)); margin:0 auto 18px; padding-top:28px; }
.wrong-card-row { position:relative; }
.wrong-card-row .wrong-card { width:100%; padding-right:82px; }
.wrong-ask-ai { position:absolute; right:12px; bottom:12px; min-height:28px; padding:0 9px; border:1px solid rgba(46, 125, 140, 0.3); border-radius:8px; color:#287381; background: rgba(255, 255, 255, 0.94); font-size:11px; font-weight:800; }
.review-ask-ai { width:100%; min-height:40px; border:1px solid rgba(46, 125, 140, 0.35); border-radius:10px; color:#33302b; background:rgba(46, 125, 140, 0.07); font-weight:850; }
.review-share-question { width:100%; min-height:40px; margin-top:8px; border:1px solid rgba(176, 125, 30, 0.32); border-radius:10px; color:#8f5f0e; background:rgba(176, 125, 30, 0.06); font-weight:850; }
@media(max-width:600px){.review-ai-report{width:calc(100% - 24px);padding-top:16px}}
</style>
