import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: fileURLToPath(new URL("../../ki_knowledge/django_site/static/django_site/workbench/", import.meta.url)),
    emptyOutDir: true,
    manifest: "manifest.json",
    rollupOptions: {
      input: fileURLToPath(new URL("src/main.tsx", import.meta.url)),
      output: { entryFileNames: "assets/workbench-[hash].js" },
    },
  },
  worker: { format: "es" },
});
