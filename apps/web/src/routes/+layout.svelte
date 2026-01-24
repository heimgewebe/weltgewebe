<script lang="ts">
  import '../app.css';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import '$lib/styles/tokens.css';
  import { onMount } from 'svelte';
  import { ensureInertPolyfill } from '$lib/utils/inert-polyfill';
  import { setUAClasses } from '$lib/utils/ua-flags';
  import { page } from '$app/stores';
  import { get } from 'svelte/store';
  import type { LayoutData } from './$types';
  import AuthStatus from '$lib/auth/AuthStatus.svelte';

  export let data: LayoutData;

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

<AuthStatus />
<slot />
