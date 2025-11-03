### 📄 apps/web/src/routes/+layout.svelte

**Größe:** 805 B | **md5:** `4f9a070fe164fe56d1472deff592ba73`

```svelte
<script lang="ts">
  import '../app.css';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import '$lib/styles/tokens.css';
  import { onMount } from 'svelte';
  import { ensureInertPolyfill } from '$lib/utils/inert-polyfill';
  import { setUAClasses } from '$lib/utils/ua-flags';
  import { page } from '$app/stores';
  import { get } from 'svelte/store';

  export let data: any;

  onMount(() => {
    setUAClasses();
    // Toggle: ?noinert=1 schaltet Polyfill ab (Debug/Kompat)
    const q = new URLSearchParams(get(page).url.search);
    const disable = q.get('noinert') === '1' || (window as any).__NO_INERT__ === true;
    if (!disable) ensureInertPolyfill();
  });
</script>

<svelte:head>
  {#if data?.canonical}
    <link rel="canonical" href={data.canonical} />
  {/if}
</svelte:head>

<slot />
```

### 📄 apps/web/src/routes/+layout.ts

**Größe:** 192 B | **md5:** `9b63a9d01fca0cbe127d9a061b9f5d59`

```typescript
import type { LayoutLoad } from './$types';

export const load: LayoutLoad = ({ url }) => {
  const canonical = new URL(url.pathname, url.origin).toString();

  return {
    canonical
  };
};
```

### 📄 apps/web/src/routes/+page.server.ts

**Größe:** 101 B | **md5:** `f4319851426d4c10ea877e8e5de3f83d`

```typescript
import { redirect } from '@sveltejs/kit';

export function load() {
  throw redirect(307, '/map');
}
```

### 📄 apps/web/src/routes/+page.svelte

**Größe:** 232 B | **md5:** `904b1cf6094055486b945161db807a50`

```svelte
<!-- Platzhalter-Seite, damit die Route "/" existiert und
     der Redirect in +page.server.ts ausgeführt werden kann.
     (In CI/SSR wird sofort umgeleitet.) -->

<noscript>
  Weiterleitung… <a href="/map">/map</a>
</noscript>
```

