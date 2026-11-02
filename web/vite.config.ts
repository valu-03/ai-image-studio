/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  server: {
    port: 5178,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8790",
      "/files": "http://127.0.0.1:8790",
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
  test: { environment: "node", include: ["src/**/*.test.{ts,tsx}"] },
});
