import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  esbuild: {
    jsx: "automatic",
    loader: "jsx",
  },
  resolve: {
    extensions: [".js", ".jsx", ".json"],
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@lib": path.resolve(__dirname, "./src/lib"),
      "@components": path.resolve(__dirname, "./src/components"),
      "@pages": path.resolve(__dirname, "./src/pages"),
      "@contexts": path.resolve(__dirname, "./src/contexts"),
    },
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
