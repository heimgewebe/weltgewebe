import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  // Siehe https://svelte.dev/docs/kit/integrations für Preprocessor-Infos
  preprocess: vitePreprocess(),

  kit: {
    // adapter-auto ist eine Factory – hier **aufrufen**:
    adapter: adapter(),
    /**
     * Align Vite runtime resolution with tsconfig.json "paths".
     * Matches:
     *   "$lib/*"        -> "src/lib/*"
     *   "$components/*" -> "src/lib/components/*"
     *   "$stores/*"     -> "src/lib/stores/*"
     *   "$routes/*"     -> "src/routes/*"
     */
    alias: {
      $lib: "src/lib",
      $components: "src/lib/components",
      $stores: "src/lib/stores",
      $routes: "src/routes",
    },
  },
};

export default config;
