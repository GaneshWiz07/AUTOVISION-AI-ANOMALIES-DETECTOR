import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    extensions: [".ts", ".tsx", ".js", ".jsx", ".json"],
  },
  esbuild: {
    jsx: "automatic",
  },
  server: {
    port: 3000,
    host: true,
    proxy: {
      "/api": {
        target: "https://autovision-ai-server.onrender.com",
        changeOrigin: true,
        secure: true,
        // Don't rewrite the path - keep /api/v1 intact
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    // Increase chunk size warning limit
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["react", "react-dom"],
          router: ["react-router-dom"],
        },
      },
    },
  },
  define: {
    global: "globalThis",
  },
});
