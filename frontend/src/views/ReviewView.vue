<template>
  <section class="review-page-shell">
    <header class="review-topbar">
      <RouterLink class="practice-logo" to="/">
        <span>▰</span>
        数理智学
      </RouterLink>
      <nav>
        <RouterLink to="/">学习看板</RouterLink>
        <RouterLink to="/practice">智能练习</RouterLink>
        <RouterLink to="/knowledge">知识图谱</RouterLink>
        <RouterLink to="/roadmap">学习规划</RouterLink>
      </nav>
      <UserAccountButton />
    </header>

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
          <button
            v-for="item in items"
            :key="item.record_id"
            class="wrong-card"
            :class="{ active: active?.record_id === item.record_id }"
            type="button"
            @click="active = item"
          >
            <span>{{ item.course }} · {{ item.fine_tag || item.knowledge_tag }}</span>
            <strong>{{ item.question_text.slice(0, 92) }}...</strong>
            <small>得分 {{ item.score }} · {{ (item.record_mistake_tags || item.mistake_tags || []).join(" / ") }}</small>
          </button>
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
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import UserAccountButton from "../components/UserAccountButton.vue";
import { apiGet } from "../api/client";
import { useUserStore } from "../stores/user";

const user = useUserStore();
const items = ref([]);
const active = ref(null);

async function load() {
  if (!user.userId) {
    items.value = [];
    active.value = null;
    return;
  }
  const data = await apiGet("/api/review/wrong-questions", { user_id: user.userId, limit: 30 });
  items.value = data.items || [];
  active.value = items.value[0] || null;
}

onMounted(load);
</script>
