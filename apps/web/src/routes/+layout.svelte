<script lang="ts">
  import '../app.css';
  import '$lib/styles/tokens.css';
  import { onMount } from 'svelte';
  import { ensureInertPolyfill } from '$lib/utils/inert-polyfill';
  import { setUAClasses } from '$lib/utils/ua-flags';
  import type { LayoutData } from './$types';
  import { updateStore } from '$lib/stores/updateStore';
  import UpdateBanner from '$lib/components/UpdateBanner.svelte';

  export let data: LayoutData;

  onMount(() => {
    setUAClasses();
    const q = new URLSearchParams(window.location.search);
    const disable = q.get('noinert') === '1' || (window as any).__NO_INERT__ === true;
    if (!disable) ensureInertPolyfill();
    updateStore.init();
  });
</script>

<svelte:head>
  <title>Weltgewebe – Commons gemeinsam verwalten</title>
  <meta name="description" content="Das Weltgewebe macht Commons, Knoten, Garnrollen und ihre Beziehungen auf einer gemeinsamen Karte sichtbar und verwaltbar." />
  <meta name="application-name" content="Weltgewebe" />
  <link rel="manifest" href="/manifest.webmanifest" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  {#if data?.canonical}
    <link rel="canonical" href={data.canonical} />
  {/if}
</svelte:head>

<UpdateBanner />

<slot />
