import { reactive } from "vue";

export const confirmState = reactive({
  open: false,
  title: "确认操作",
  description: "",
  confirmLabel: "确认",
  tone: "danger",
  resolve: null
});

export function requestConfirmation(options = {}) {
  const normalized = typeof options === "string" ? { description: options } : options;
  if (confirmState.resolve) confirmState.resolve(false);
  Object.assign(confirmState, {
    open: true,
    title: normalized.title || "确认操作",
    description: normalized.description || "此操作需要你的确认。",
    confirmLabel: normalized.confirmLabel || "确认",
    tone: normalized.tone || "danger"
  });
  return new Promise((resolve) => {
    confirmState.resolve = resolve;
  });
}

export function settleConfirmation(value) {
  const resolve = confirmState.resolve;
  confirmState.open = false;
  confirmState.resolve = null;
  resolve?.(Boolean(value));
}
