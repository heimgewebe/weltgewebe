import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";
export default defineConfig({
  plugins: [sveltekit()],
  preview: {
    port: process.env.PREVIEW_PORT ? Number(process.env.PREVIEW_PORT) : 5173,
  },
});
