<template>
  <div v-if="open" class="contact-picker-backdrop" role="presentation" @click.self="$emit('close')">
    <section class="contact-picker" role="dialog" aria-modal="true" aria-labelledby="contact-picker-title">
      <header><div><small>新建会话</small><h2 id="contact-picker-title">选择联系人</h2></div><button type="button" aria-label="关闭联系人选择" @click="$emit('close')">关闭</button></header>
      <label><span>搜索联系人</span><input v-model.trim="search" autofocus placeholder="输入姓名或账号" /></label>
      <div class="contact-picker-list">
        <p v-if="loading">正在加载联系人…</p>
        <template v-else v-for="group in filteredGroups" :key="group.key">
          <h3>{{ group.label }}</h3>
          <button v-for="item in group.items" :key="`${item.relation}-${item.user_id}`" type="button" @click="$emit('select', item)">
            <i>{{ item.nickname.slice(0, 1) }}</i><span><strong>{{ item.nickname }}</strong><small>@{{ item.username }} · {{ item.class_name || (item.role === 'teacher' ? '教师' : '学生') }}</small></span><b>开始沟通 ›</b>
          </button>
        </template>
        <p v-if="!loading && !filteredGroups.some((group) => group.items.length)">没有匹配的联系人。</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";

const props = defineProps({ open: { type: Boolean, default: false }, groups: { type: Array, default: () => [] }, loading: { type: Boolean, default: false } });
const emit = defineEmits(["close", "select"]);
const search = ref("");
const filteredGroups = computed(() => {
  const term = search.value.toLowerCase();
  return props.groups.map((group) => {
    const source = group.items?.length ? group.items : (group.sections || []).flatMap((section) => section.items || []);
    const seen = new Set();
    const items = source.filter((item) => {
      const key = `${item.relation}-${item.user_id}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return !term || `${item.nickname} ${item.username} ${item.class_name || ""}`.toLowerCase().includes(term);
    });
    return { ...group, items };
  });
});
function onKeydown(event) { if (event.key === "Escape" && props.open) emit("close"); }
watch(() => props.open, (value) => { if (value) search.value = ""; });
window.addEventListener("keydown", onKeydown);
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>

<style scoped>
.contact-picker-backdrop{position:fixed;z-index:30;inset:0;display:grid;place-items:center;padding:20px;background: rgba(60, 55, 45, 0.4);backdrop-filter:blur(8px)}.contact-picker{width:min(620px,100%);max-height:min(720px,90dvh);display:grid;grid-template-rows:auto auto minmax(0,1fr);overflow:hidden;color:#33302b;border:1px solid rgba(46, 125, 140, 0.28);background:#ffffff;box-shadow:0 28px 80px rgba(90, 75, 50, 0.18)}.contact-picker>header{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:20px;border-bottom:1px solid rgba(100, 90, 70, 0.12)}.contact-picker h2{margin:5px 0 0;font-size:26px}.contact-picker header small{color:#287381;font-weight:800}.contact-picker header button{min-height:35px;padding:0 12px;color:#33302b;border:1px solid rgba(100, 90, 70, 0.18);background:#ffffff}.contact-picker>label{display:grid;gap:7px;padding:14px 20px;color:#706b62;font-size:11px}.contact-picker input{height:42px;padding:0 12px;color:#33302b;border:1px solid rgba(100, 90, 70, 0.2);outline:0;background:#ffffff}.contact-picker input:focus{border-color:#287381}.contact-picker-list{min-height:180px;overflow-y:auto;padding-bottom:12px}.contact-picker-list h3{margin:10px 20px 5px;color:#287381;font-size:11px;letter-spacing:.08em}.contact-picker-list>button{width:100%;display:grid;grid-template-columns:40px minmax(0,1fr) auto;align-items:center;gap:11px;padding:12px 20px;text-align:left;color:#33302b;border:0;border-top:1px solid rgba(100, 90, 70, 0.08);background:transparent;transition:background .2s ease}.contact-picker-list>button:hover,.contact-picker-list>button:focus-visible{background:rgba(46, 125, 140, 0.08)}.contact-picker-list i{width:40px;height:40px;display:grid;place-items:center;color:#ffffff;background:#2e7d8c;font-style:normal}.contact-picker-list span{min-width:0;display:grid;gap:3px}.contact-picker-list small{overflow:hidden;color:#706b62;text-overflow:ellipsis;white-space:nowrap}.contact-picker-list b{color:#287381;font-size:11px}.contact-picker-list>p{margin:24px;color:#706b62;text-align:center}@media(max-width:560px){.contact-picker-backdrop{padding:0;place-items:stretch}.contact-picker{width:100%;max-height:none}.contact-picker-list>button{grid-template-columns:38px minmax(0,1fr)}.contact-picker-list b{grid-column:2}}
</style>
