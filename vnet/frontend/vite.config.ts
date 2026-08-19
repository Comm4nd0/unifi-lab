import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The console is served by Django in production, so the build lands in
// ../backend/web where whitenoise and the SPA view can pick it up.
export default defineConfig({
  plugins: [react()],
  resolve: {
    // `.pathname` is percent-encoded and keeps a leading slash ahead of the
    // drive letter on Windows, so decode it and drop that slash.
    alias: {
      "@": decodeURIComponent(new URL("./src", import.meta.url).pathname).replace(
        /^\/(?=[A-Za-z]:)/,
        "",
      ),
    },
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
