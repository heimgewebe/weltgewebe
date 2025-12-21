<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import type { PageData } from './$types';
  import '$lib/styles/tokens.css';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import type { Map as MapLibreMap } from 'maplibre-gl';

  import TopBar from '$lib/components/TopBar.svelte';
  import ViewPanel from '$lib/components/ViewPanel.svelte';
  import SelectionCard from '$lib/components/SelectionCard.svelte';
  import TimelineDock from '$lib/components/TimelineDock.svelte';

  import { view, selection } from '$lib/stores/uiView';

  export let data: PageData;

  type MapPoint = {
    id: string;
    title: string;
    lat: number;
    lon: number;
  };

  $: markersData = (data.nodes || []).map((n) => ({
    id: n.id,
    title: n.title,
    lat: n.location.lat,
    lon: n.location.lon
  })) satisfies MapPoint[];

  let mapContainer: HTMLDivElement | null = null;
  let map: MapLibreMap | null = null;
  let isLoading = true;
  let lastFocusedElement: HTMLElement | null = null;
  const markerCleanupFns: Array<() => void> = [];

  // Update markers when data changes or view toggles change
  async function updateMarkers(points: MapPoint[]) {
    if (!map) return;
    const maplibregl = await import('maplibre-gl');

    markerCleanupFns.forEach((fn) => fn());
    markerCleanupFns.length = 0;

    if (!$view.showNodes) return; // Hide nodes if toggle is off

    for (const item of points) {
      const element = document.createElement('button');
      element.type = 'button';
      element.className = 'map-marker';
      element.setAttribute('aria-label', item.title);
      element.title = item.title;

      const handleClick = async (e: Event) => {
        // Capture focus for restoration later
        lastFocusedElement = e.currentTarget as HTMLElement;

        $selection = { type: 'node', id: item.id, data: item };

        // Robust coordinate check before flying
        const lat = item.lat;
        const lon = item.lon;
        if (typeof lat === 'number' && typeof lon === 'number' && !isNaN(lat) && !isNaN(lon)) {
          map?.flyTo({
            center: [lon, lat],
            zoom: Math.max(map.getZoom(), 14),
            speed: 0.8,
            curve: 1
          });
        }
      };
      element.addEventListener('click', handleClick);

      const marker = new maplibregl.Marker({ element, anchor: 'bottom' })
        .setLngLat([item.lon, item.lat])
        .addTo(map);

      // Re-apply accessibility attributes after addTo() to ensure they persist
      element.setAttribute('aria-label', item.title);
      element.title = item.title;

      markerCleanupFns.push(() => {
        element.removeEventListener('click', handleClick);
        marker.remove();
      });
    }
  }

  // Reactive update
  $: if (map && markersData && $view) {
    updateMarkers(markersData);
  }

  // Restore focus when selection is closed
  $: if (!$selection && lastFocusedElement) {
    // Check if element is still in document (it might be gone if view changed)
    if (document.body.contains(lastFocusedElement)) {
      lastFocusedElement.focus();
    }
    lastFocusedElement = null;
  }

  // Handle Edges visibility (Stub implementation for now as we don't have edges data in this file yet, but logic is prepared)
  $: if (map && $view) {
    // if ($view.showEdges) { ... render edges ... } else { ... remove edges ... }
  }

  onMount(() => {
    (async () => {
      const maplibregl = await import('maplibre-gl');
      const container = mapContainer;
      if (!container) {
        return;
      }
      // Hamburg-Mitte: 10.00, 53.55 — Zoom 13
      map = new maplibregl.Map({
        container,
        style: 'https://demotiles.maplibre.org/style.json',
        center: [10.00, 53.55],
        zoom: 13
      });
      map.addControl(new maplibregl.NavigationControl({ showZoom:true }), 'bottom-right');

      // Fail-safe loading state
      const loadingTimeout = setTimeout(() => {
        isLoading = false;
      }, 10000);

      const finishLoading = () => {
        clearTimeout(loadingTimeout);
        isLoading = false;
      };

      map.on('load', finishLoading);
      map.on('error', finishLoading);
    })();

    return () => {
      if (map && typeof map.remove === 'function') map.remove();
      markerCleanupFns.forEach((fn) => fn());
      markerCleanupFns.length = 0;
    };
  });
</script>

<style>
  .shell{
    position:relative;
    height:100dvh;
    /* keep the raw dynamic viewport height as a fallback for browsers missing safe-area support */
    height:calc(100dvh - env(safe-area-inset-top) - env(safe-area-inset-bottom));
    width:100vw;
    overflow:hidden;
    background:var(--bg);
    color:var(--text);
    padding-top: env(safe-area-inset-top);
    padding-bottom: env(safe-area-inset-bottom);
  }
  #map{ position:absolute; inset:0; }
  #map :global(canvas){ filter: grayscale(0.2) saturate(0.75) brightness(1.03) contrast(0.95); }

  #map :global(.map-marker){
    width:24px;
    height:24px;
    border-radius:999px;
    border:2px solid var(--panel-border);
    background:var(--accent, #ff8c42);
    display:grid;
    place-items:center;
    color:var(--bg);
    cursor:pointer;
    box-shadow:0 0 0 2px rgba(0,0,0,0.25);
    transition: transform 0.15s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  }
  @media (hover: hover) and (pointer: fine) {
    #map :global(.map-marker:hover){
      transform: scale(1.2);
      z-index: 10;
    }
  }
  #map :global(.map-marker:focus-visible){
    outline:2px solid var(--fg);
    outline-offset:2px;
    z-index: 10;
  }

  .loading-overlay {
    position: absolute;
    inset: 0;
    background: var(--bg);
    display: grid;
    place-items: center;
    z-index: 50;
    transition: opacity 0.3s;
  }
  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid rgba(255,255,255,0.1);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>

<main class="shell">
  <TopBar />
  <ViewPanel />

  <!-- Karte -->
  <div id="map" bind:this={mapContainer}></div>

  {#if isLoading}
    <div class="loading-overlay">
      <div class="spinner"></div>
    </div>
  {/if}

  <SelectionCard />

  <!-- Zeitleiste -->
  <TimelineDock />
</main>
