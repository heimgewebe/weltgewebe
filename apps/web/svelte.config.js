import adapter from '@sveltejs/adapter-auto';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  // Siehe https://svelte.dev/docs/kit/integrations für Preprocessor-Infos
  preprocess: vitePreprocess(),

  kit: {
    // adapter-auto ist eine Factory – hier **aufrufen**:
    adapter: adapter()
  }
};

export default config;
