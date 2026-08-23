import { reactive } from "vue";

let nextId = 1;

export const toastState = reactive({
  items: []
});

export function notify(message, tone = "error", duration = 4200) {
  const text = String(message || "操作未完成，请稍后重试").trim();
  const id = nextId++;
  toastState.items.push({ id, message: text, tone });
  window.setTimeout(() => dismissToast(id), duration);
  return id;
}

export function dismissToast(id) {
  const index = toastState.items.findIndex((item) => item.id === id);
  if (index >= 0) toastState.items.splice(index, 1);
}
