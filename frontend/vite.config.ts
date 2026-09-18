import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Built assets land inside the FastAPI static tree and are served from /static/app/.
// The SPA itself is served at /app (see src/api/app.py).
export default defineConfig({
  base: "/static/app/",
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../src/api/static/app",
    emptyOutDir: true,
    target: "es2020",
    sourcemap: false,
    chunkSizeWarningLimit: 600,
  },
  server: {
    port: 5174,
    proxy: {
      "/api": "http://127.0.0.1:8088",
      "/static/vendor": "http://127.0.0.1:8088",
    },
  },
});
