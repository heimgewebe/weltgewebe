import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  // Siehe https://svelte.dev/docs/kit/integrations für Preprocessor-Infos
  preprocess: vitePreprocess(),

  kit: {
    // adapter-auto ist eine Factory – hier **aufrufen**:
    adapter: adapter(),

    prerender: {
      handleHttpError: ({ path, message }) => {
        // Suppress 404 errors for development-only routes (e.g., /_dev)
        // which are blocked in production builds via +page.server.ts.
        if (path.startsWith("/_dev") && message.includes("404")) {
          return;
        }
        // Fail the build for other errors
        throw new Error(message);
      },
    },

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
