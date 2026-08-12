import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  build: {
    chunkSizeWarningLimit: 1200,
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
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true
      },
      "/docs": {
        target: "http://localhost:8000",
        changeOrigin: true
      },
      "/openapi.json": {
        target: "http://localhost:8000",
        changeOrigin: true
      }
    }
  }
});
