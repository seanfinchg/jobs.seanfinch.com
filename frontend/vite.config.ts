import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
  build: {
    // Netlify builds/deploys straight from this repo (no GitHub Pages
    // /docs convention anymore) -- the default dist/ is fine, and isn't
    // committed (see .gitignore).
    outDir: resolve(__dirname, "dist"),
    emptyOutDir: true,
  },
});
