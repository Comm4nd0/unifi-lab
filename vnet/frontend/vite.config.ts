import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The console is served by Django in production, so the build lands in
// ../backend/web where whitenoise and the SPA view can pick it up.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": new URL("./src", import.meta.url).pathname },
  },
  build: {
    outDir: "../backend/web",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        // Change this if the API runs somewhere other than the default port.
        target: "http://127.0.0.1:8003",
        changeOrigin: true,
      },
    },
  },
});
