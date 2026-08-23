import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget = env.VITE_API_PROXY_TARGET;
  const proxy = proxyTarget
    ? Object.fromEntries(
        ["/api", "/docs", "/openapi.json"].map((path) => [
          path,
          { target: proxyTarget, changeOrigin: true }
        ])
      )
    : {};

  return {
    plugins: [vue()],
    build: {
      chunkSizeWarningLimit: 600,
      rollupOptions: {
        output: {
          manualChunks: {
            vue: ["vue", "vue-router", "pinia"],
            echarts: ["echarts"]
          }
        }
      }
    },
    server: {
      port: 5173,
      proxy
    }
  };
});
