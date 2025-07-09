import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { copyFileSync } from "fs";

// Custom plugin to copy _redirects file
const copyRedirects = () => ({
  name: 'copy-redirects',
  closeBundle() {
    try {
      copyFileSync('public/_redirects', 'dist/_redirects');
      console.log('_redirects file copied to dist/');
    } catch (error) {
      console.warn('Could not copy _redirects file:', error.message);
    }
  }
});

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), copyRedirects()],
  esbuild: {
    jsx: "automatic",
    loader: "jsx",
  },
  resolve: {
    extensions: [".js", ".jsx", ".json"],
    alias: {
      "@": "/src",
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
      external: [],
    },
  },
  preview: {
    port: 4173,
    host: true,
  },
  define: {
    global: "globalThis",
  },
});
