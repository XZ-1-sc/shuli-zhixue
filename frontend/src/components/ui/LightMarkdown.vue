<template>
  <div class="light-markdown">
    <template v-for="(block, index) in blocks" :key="index">
      <h3 v-if="block.type === 'heading'"><template v-for="(part, partIndex) in inlineParts(block.text)" :key="partIndex"><strong v-if="part.bold">{{ part.text }}</strong><span v-else>{{ part.text }}</span></template></h3>
      <ul v-else-if="block.type === 'list'"><li v-for="(item, itemIndex) in block.items" :key="itemIndex"><template v-for="(part, partIndex) in inlineParts(item)" :key="partIndex"><strong v-if="part.bold">{{ part.text }}</strong><span v-else>{{ part.text }}</span></template></li></ul>
      <ol v-else-if="block.type === 'ordered'"><li v-for="(item, itemIndex) in block.items" :key="itemIndex"><template v-for="(part, partIndex) in inlineParts(item)" :key="partIndex"><strong v-if="part.bold">{{ part.text }}</strong><span v-else>{{ part.text }}</span></template></li></ol>
      <p v-else><template v-for="(part, partIndex) in inlineParts(block.text)" :key="partIndex"><strong v-if="part.bold">{{ part.text }}</strong><span v-else>{{ part.text }}</span></template></p>
    </template>
  </div>
</template>

<script setup>
import { computed } from "vue";
const props = defineProps({ text: { type: String, default: "" } });
const blocks = computed(() => {
  const result = [];
  for (const rawLine of props.text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const heading = line.match(/^#{1,3}\s+(.+)$/);
    if (heading) { result.push({ type: "heading", text: heading[1] }); continue; }
    const ordered = line.match(/^\d+[.)、]\s*(.+)$/);
    const bullet = line.match(/^[-*•]\s+(.+)$/);
    const type = ordered ? "ordered" : bullet ? "list" : null;
    if (type) {
      const previous = result.at(-1);
      const text = (ordered || bullet)[1];
      if (previous?.type === type) previous.items.push(text); else result.push({ type, items: [text] });
      continue;
    }
    result.push({ type: "paragraph", text: line });
  }
  return result;
});
function inlineParts(text) { return String(text).split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part) => ({ bold: part.startsWith("**") && part.endsWith("**"), text: part.replace(/^\*\*|\*\*$/g, "") })); }
</script>

<style scoped>
.light-markdown{display:grid;gap:7px}.light-markdown :is(h3,p,ul,ol){margin:0}.light-markdown h3{font-size:14px}.light-markdown :is(ul,ol){display:grid;gap:4px;padding-left:18px}.light-markdown p,.light-markdown li{line-height:1.65}.light-markdown strong{color:#33302b}
</style>
