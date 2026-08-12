<template>
  <section class="identity-page">
    <div class="identity-formula formula-one" aria-hidden="true">y = sin x</div>
    <div class="identity-formula formula-two" aria-hidden="true">∑ k = n(n+1) / 2</div>
    <div class="identity-formula formula-three" aria-hidden="true">∫ f(x)dx</div>
    <div class="identity-formula formula-four" aria-hidden="true">lim sin x / x = 1</div>

    <main class="identity-layout">
      <section class="identity-brand" aria-labelledby="brand-heading">
        <div class="identity-brand-lockup">
          <span class="identity-shield">Σ</span>
          <strong>数理智学</strong>
        </div>
        <div class="identity-brand-rule"><i></i></div>
        <h1 id="brand-heading">大学数学，从理解到掌握</h1>
        <p>以理解为起点，以思维为核心，构建系统化的大学数学学习体系。</p>
        <div class="identity-capabilities" aria-label="平台能力">
          <div><span>⌁</span><strong>学习诊断</strong><small>定位真实薄弱点</small></div>
          <div><span>师</span><strong>教师协作</strong><small>共建共享教学资源</small></div>
          <div><span>◇</span><strong>知识图谱</strong><small>梳理课程知识体系</small></div>
        </div>
      </section>

      <section
        class="identity-panel"
        :class="{ 'is-register': mode === 'register', 'is-teacher-register': mode === 'register' && role === 'teacher' }"
        aria-labelledby="auth-title"
      >
        <p class="identity-eyebrow">统一账号入口</p>
        <h2 id="auth-title">{{ mode === "login" ? "登录数理智学" : "创建数理智学账号" }}</h2>
        <p class="identity-intro">
          {{ mode === "login" ? "选择登录身份，进入对应的学习或教学工作台。" : "选择注册身份，建立属于你的数理智学账号。" }}
        </p>

        <div class="identity-role-switch" role="group" aria-label="选择账号身份">
          <button :class="{ active: role === 'student' }" type="button" @click="setRole('student')">
            <span>学</span><strong>学生{{ mode === "login" ? "登录" : "注册" }}</strong>
          </button>
          <button :class="{ active: role === 'teacher' }" type="button" @click="setRole('teacher')">
            <span>师</span><strong>教师{{ mode === "login" ? "登录" : "注册" }}</strong>
          </button>
        </div>
        <p class="identity-context">
          当前身份：<strong>{{ roleName }}</strong>
          <span>·</span>
          {{ role === "teacher" ? "进入教学工作台" : "进入学习中控台" }}
        </p>

        <form class="identity-form" @submit.prevent="submit">
          <label>
            <span>用户名</span>
            <input v-model.trim="username" autocomplete="username" placeholder="请输入用户名" required />
          </label>
          <label>
            <span>密码</span>
            <div class="identity-password-field">
              <input
                v-model="password"
                :autocomplete="mode === 'register' ? 'new-password' : 'current-password'"
                :type="showPassword ? 'text' : 'password'"
                :placeholder="mode === 'register' ? '至少 6 位密码' : '请输入密码'"
                required
              />
              <button type="button" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
                {{ showPassword ? "隐藏" : "显示" }}
              </button>
            </div>
          </label>
          <label v-if="mode === 'register'">
            <span>确认密码</span>
            <input v-model="passwordConfirm" autocomplete="new-password" type="password" placeholder="请再次输入密码" required />
          </label>
          <label v-if="mode === 'register' && role === 'teacher'">
            <span>教师邀请码</span>
            <input v-model.trim="teacherInviteCode" autocomplete="off" placeholder="请输入教师邀请码" required />
            <small>邀请码由系统管理员发放，用于验证教师身份。</small>
          </label>

          <div v-if="mode === 'login'" class="identity-form-options">
            <label class="identity-check"><input v-model="remember" type="checkbox" />记住登录状态</label>
            <button type="button" @click="showResetHelp">忘记密码</button>
          </div>

          <p v-if="formMessage" class="identity-message" :class="{ error: formError }" aria-live="polite">{{ formMessage }}</p>

          <button class="identity-submit" :disabled="user.authLoading" type="submit">
            {{ submitLabel }}
          </button>
        </form>

        <p class="identity-mode-link">
          {{ mode === "login" ? "还没有账号？" : "已有账号？" }}
          <button type="button" @click="toggleMode">{{ mode === "login" ? "创建账号" : "返回登录" }}</button>
        </p>

        <div class="identity-security-note">
          <span>✓</span>
          {{ role === "teacher" ? "教师注册需通过邀请码验证" : "个人学习数据仅绑定当前账号" }}
        </div>
        <footer><button type="button">隐私说明</button><i></i><button type="button">使用帮助</button></footer>
      </section>
    </main>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useUserStore } from "../stores/user";

const route = useRoute();
const router = useRouter();
const user = useUserStore();
const mode = ref(route.query.mode === "register" ? "register" : "login");
const role = ref(route.query.role === "teacher" ? "teacher" : "student");
const username = ref("");
const password = ref("");
const passwordConfirm = ref("");
const teacherInviteCode = ref("");
const remember = ref(true);
const showPassword = ref(false);
const formMessage = ref("");
const formError = ref(false);

const roleName = computed(() => (role.value === "teacher" ? "教师" : "学生"));
const submitLabel = computed(() => {
  if (user.authLoading) return "处理中...";
  if (mode.value === "register") return `创建${roleName.value}账号`;
  return `进入${role.value === "teacher" ? "教师端" : "学生端"}`;
});

function setRole(nextRole) {
  role.value = nextRole;
  teacherInviteCode.value = "";
  clearMessage();
  router.replace({ query: { ...route.query, mode: mode.value, role: nextRole } });
}

function toggleMode() {
  mode.value = mode.value === "login" ? "register" : "login";
  password.value = "";
  passwordConfirm.value = "";
  teacherInviteCode.value = "";
  clearMessage();
  router.replace({ query: { ...route.query, mode: mode.value, role: role.value } });
}

function clearMessage() {
  formMessage.value = "";
  formError.value = false;
  user.authError = "";
}

function showResetHelp() {
  formError.value = false;
  formMessage.value = "请联系系统管理员重置密码。";
}

function destination() {
  if (role.value === "teacher") return "/teacher";
  const redirect = String(route.query.redirect || "/");
  return redirect.startsWith("/") && !redirect.startsWith("//") && !redirect.startsWith("/teacher") ? redirect : "/";
}

async function submit() {
  clearMessage();
  if (mode.value === "register" && password.value !== passwordConfirm.value) {
    formError.value = true;
    formMessage.value = "两次输入的密码不一致。";
    return;
  }
  if (mode.value === "register" && password.value.length < 6) {
    formError.value = true;
    formMessage.value = "密码至少需要 6 位。";
    return;
  }
  try {
    if (mode.value === "register") {
      await user.register(username.value, password.value, role.value, teacherInviteCode.value, remember.value);
    } else {
      await user.login(username.value, password.value, role.value, remember.value);
    }
    await router.replace(destination());
  } catch (error) {
    formError.value = true;
    formMessage.value = error.message || `${roleName.value}账号认证失败。`;
  }
}
</script>
