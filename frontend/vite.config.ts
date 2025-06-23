import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    host: true,
    proxy: {
      "/api": {
        target: "http://localhost:12000",
        changeOrigin: true,
        secure: false,
        // Don't rewrite the path - keep /api/v1 intact
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
  define: {
    global: "globalThis",
  },
});
