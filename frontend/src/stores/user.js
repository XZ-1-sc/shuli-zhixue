import { defineStore } from "pinia";
import { apiGet, apiPost } from "../api/client";

const USER_KEY = "math_brain_current_user";
const SESSION_PREFIX = "math_brain_chat_session_";

function readStoredUser() {
  const raw = localStorage.getItem(USER_KEY) || sessionStorage.getItem(USER_KEY);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    return { ...parsed, role: parsed.role || "student" };
  } catch (error) {
    localStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(USER_KEY);
    return null;
  }
}

function randomSessionId() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export const useUserStore = defineStore("user", {
  state: () => ({
    user: readStoredUser(),
    authMode: "login",
    authError: "",
    authLoading: false
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.user),
    userId: (state) => state.user?.user_id || state.user?.id || null,
    username: (state) => state.user?.username || "未登录",
    role: (state) => state.user?.role || "student"
  },
  actions: {
    setAuthMode(mode) {
      this.authMode = mode;
      this.authError = "";
    },
    openAuth(mode = "login", role = "student") {
      const redirect = `${window.location.pathname}${window.location.search}`;
      const params = new URLSearchParams({ mode, role, redirect });
      this.authError = "";
      window.location.assign(`/auth?${params.toString()}`);
    },
    persistUser(data, remember = true) {
      this.user = { ...data, role: data.role || "student" };
      localStorage.removeItem(USER_KEY);
      sessionStorage.removeItem(USER_KEY);
      const storage = remember ? localStorage : sessionStorage;
      storage.setItem(USER_KEY, JSON.stringify(this.user));
    },
    async login(username, password, role = "student", remember = true) {
      this.authLoading = true;
      this.authError = "";
      try {
        const data = await apiPost("/api/login", { username, password, role, remember });
        this.persistUser(data, remember);
        return data;
      } catch (error) {
        this.authError = error.message || "登录失败";
        throw error;
      } finally {
        this.authLoading = false;
      }
    },
    async register(username, password, role = "student", teacherInviteCode = "", remember = true) {
      this.authLoading = true;
      this.authError = "";
      try {
        const data = await apiPost("/api/register", {
          username,
          password,
          role,
          teacher_invite_code: role === "teacher" ? teacherInviteCode : null,
          remember
        });
        this.persistUser(data, remember);
        return data;
      } catch (error) {
        this.authError = error.message || "注册失败";
        throw error;
      } finally {
        this.authLoading = false;
      }
    },
    async hydrateSession() {
      if (!this.user) {
        return null;
      }
      try {
        const data = await apiGet("/api/auth/me");
        this.persistUser(data, Boolean(localStorage.getItem(USER_KEY)));
        return data;
      } catch (error) {
        this.user = null;
        localStorage.removeItem(USER_KEY);
        sessionStorage.removeItem(USER_KEY);
        return null;
      }
    },
    async logout() {
      if (this.userId) {
        localStorage.removeItem(`${SESSION_PREFIX}${this.userId}`);
      }
      try {
        await apiPost("/api/auth/logout");
      } catch (error) {
        // Local logout must still succeed if the backend is unavailable.
      }
      this.user = null;
      localStorage.removeItem(USER_KEY);
      sessionStorage.removeItem(USER_KEY);
    },
    sessionId() {
      const userId = this.userId || "guest";
      const key = `${SESSION_PREFIX}${userId}`;
      const existing = localStorage.getItem(key);
      if (existing) {
        return existing;
      }
      const next = randomSessionId();
      localStorage.setItem(key, next);
      return next;
    },
    saveSessionId(sessionId) {
      const userId = this.userId || "guest";
      localStorage.setItem(`${SESSION_PREFIX}${userId}`, sessionId);
    }
  }
});
