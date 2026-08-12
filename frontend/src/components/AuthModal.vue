<template>
  <div v-if="visible" class="auth-overlay" @click.self="emit('close')">
    <form class="auth-panel" @submit.prevent="submit">
      <button class="auth-close" type="button" aria-label="关闭登录注册窗口" title="关闭" @click="emit('close')">
        ×
      </button>
      <header class="auth-heading">
        <p class="eyebrow">{{ isRegister ? "创建学习档案" : "欢迎回来" }}</p>
        <h2>{{ isRegister ? "注册数理智学" : "登录数理智学" }}</h2>
        <p class="auth-intro">
          登录后，小逻会把你的做题历史、错题复盘和阶段规划绑定到当前账号。
        </p>
      </header>

      <div class="auth-fields">
        <label class="field">
          用户名
          <input v-model.trim="username" autocomplete="username" placeholder="请输入用户名" required />
        </label>
        <label class="field">
          密码
          <input
            v-model="password"
            :autocomplete="isRegister ? 'new-password' : 'current-password'"
            :placeholder="isRegister ? '至少 6 位密码' : '请输入密码'"
            type="password"
            required
          />
        </label>
        <label v-if="isRegister" class="field">
          确认密码
          <input v-model="passwordConfirm" autocomplete="new-password" placeholder="请再次输入密码" type="password" required />
        </label>
      </div>

      <div class="auth-actions">
        <button class="primary-button wide" :disabled="user.authLoading" type="submit">
          {{ user.authLoading ? "处理中..." : isRegister ? "注册并进入" : "登录" }}
        </button>
        <button class="ghost-button wide" type="button" @click="toggleMode">
          {{ isRegister ? "已有账号，去登录" : "还没有账号，去注册" }}
        </button>
      </div>
      <p class="form-error" aria-live="polite">{{ errorMessage || user.authError }}</p>
    </form>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { useUserStore } from "../stores/user";

const props = defineProps({
  visible: { type: Boolean, default: false }
});
const emit = defineEmits(["close"]);
const user = useUserStore();
const username = ref("");
const password = ref("");
const passwordConfirm = ref("");
const errorMessage = ref("");
const isRegister = computed(() => user.authMode === "register");

function closeFromKeyboard(event) {
  if (props.visible && event.key === "Escape") {
    emit("close");
  }
}

function toggleMode() {
  user.setAuthMode(isRegister.value ? "login" : "register");
  errorMessage.value = "";
}

async function submit() {
  errorMessage.value = "";
  if (isRegister.value && password.value !== passwordConfirm.value) {
    errorMessage.value = "两次输入的密码不一致。";
    return;
  }
  if (isRegister.value && password.value.length < 6) {
    errorMessage.value = "密码至少需要 6 位。";
    return;
  }
  try {
    if (isRegister.value) {
      await user.register(username.value, password.value);
    } else {
      await user.login(username.value, password.value);
    }
    emit("close");
  } catch (error) {
    errorMessage.value = error.message || "认证失败";
  }
}

onMounted(() => window.addEventListener("keydown", closeFromKeyboard));
onBeforeUnmount(() => window.removeEventListener("keydown", closeFromKeyboard));
</script>
