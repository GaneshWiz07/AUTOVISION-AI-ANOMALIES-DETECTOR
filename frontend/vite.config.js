import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  esbuild: {
    jsx: "automatic",
    loader: "jsx",
  },
  resolve: {
    extensions: [".js", ".jsx", ".json"],
  },
  server: {
    port: 3000,
    host: true,
    proxy: {
      "/api": {
        target: "https://autovision-ai-server.onrender.com",
        changeOrigin: true,
        secure: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
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
