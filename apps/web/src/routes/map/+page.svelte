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
    summary?: string;
    type?: 'node' | 'account';
  };

  $: nodesData = (data.nodes || []).map((n) => ({
    id: n.id,
    title: n.title,
    lat: n.location.lat,
    lon: n.location.lon,
    summary: n.summary,
    type: 'node'
  })) satisfies MapPoint[];

  $: accountsData = (data.accounts || [])
    .filter((a) => a.public_pos) // Only show accounts with a visible public position
    .map((a) => ({
      id: a.id,
      title: a.title,
      lat: a.public_pos.lat,
      lon: a.public_pos.lon,
      summary: a.summary,
      type: 'account'
    })) satisfies MapPoint[];

  $: markersData = [...nodesData, ...accountsData];

  $: edgesData = (data.edges || []);

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
      element.className = item.type === 'account' ? 'map-marker marker-account' : 'map-marker';
      element.setAttribute('aria-label', item.title);
      element.title = item.title;

      const handleClick = async (e: Event) => {
        // Capture focus for restoration later
        lastFocusedElement = e.currentTarget as HTMLElement;

        $selection = { type: item.type || 'node', id: item.id, data: item };

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

    // Force flyTo first marker if available to ensure visibility
    if (points.length > 0) {
      const first = points[0];
      // Only auto-fly if we are fairly sure we want to (optional, per Step 2 instruction)
      // map.flyTo({ center: [first.lon, first.lat], zoom: 14, animate: true });
    }
  }

  // Update edges on map
  function updateEdges(edges: any[], points: MapPoint[]) {
    if (!map) return;

    // Clean up existing layers/sources if they exist
    if (map.getLayer('edges-layer')) map.removeLayer('edges-layer');
    if (map.getSource('edges-source')) map.removeSource('edges-source');

    if (!$view.showEdges || edges.length === 0) return;

    const features = [];

    // Helper to find location of a node/account
    const findLoc = (id: string) => points.find(p => p.id === id);

    for (const edge of edges) {
      const source = findLoc(edge.source_id);
      const target = findLoc(edge.target_id);

      if (source && target) {
        const feature: GeoJSON.Feature<GeoJSON.LineString> = {
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: [
              [source.lon, source.lat],
              [target.lon, target.lat]
            ]
          },
          properties: {
             id: edge.id,
             kind: edge.edge_kind
          }
        };
        features.push(feature);
      }
    }

    if (features.length === 0) return;

    map.addSource('edges-source', {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features: features
      }
    });

    map.addLayer({
      id: 'edges-layer',
      type: 'line',
      source: 'edges-source',
      layout: {
        'line-join': 'round',
        'line-cap': 'round'
      },
      paint: {
        'line-color': '#888',
        'line-width': 2,
        'line-dasharray': [2, 1]
      }
    });

    // Ensure edges are below markers
    // Note: markers are HTML elements overlaying the canvas, so lines (canvas) are automatically below.
    // However, if we had other layers, we might need 'beforeId'.
  }

  // Reactive update for markers
  $: if (map && markersData && $view) {
    updateMarkers(markersData);
  }

  // Reactive update for edges
  $: if (map && markersData && edgesData && $view && map.getStyle()) {
     // Ensure style is loaded before adding layers
     if (map.isStyleLoaded()) {
        updateEdges(edgesData, markersData);
     } else {
        map.once('styledata', () => updateEdges(edgesData, markersData));
     }
  }


  // Restore focus when selection is closed
  $: if (!$selection && lastFocusedElement) {
    // Check if element is still in document (it might be gone if view changed)
    if (document.body.contains(lastFocusedElement)) {
      lastFocusedElement.focus();
    }
    lastFocusedElement = null;
  }

  function jumpToDemo() {
    if (!map) return;
    // Jump to the demo area (Hamburg) where fairschenkbox and gewebespinnerAYE are located
    // Box: 53.5604 (Garnrolle) to 53.5588 (Fairschenkbox) -> roughly center 53.5596, 10.0616
    map.flyTo({
      center: [10.0616, 53.5596],
      zoom: 15,
      animate: true
    });
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

        // Initial flyTo if markers exist (Step 2 mini-patch)
        if (markersData.length > 0) {
           map?.flyTo({
             center: [markersData[0].lon, markersData[0].lat],
             zoom: 14,
             animate: true
           });
        }
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
  /* Accounts specific style */
  #map :global(.marker-account) {
    background: var(--primary, #007acc);
    border-radius: 4px; /* Square/Diamond for distinction */
    transform: rotate(45deg);
  }

  @media (hover: hover) and (pointer: fine) {
    #map :global(.map-marker:hover){
      transform: scale(1.2);
      z-index: 10;
    }
    #map :global(.marker-account:hover){
      transform: rotate(45deg) scale(1.2);
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

  .demo-btn {
    position: absolute;
    bottom: 24px;
    left: 24px;
    z-index: 20;
    padding: 8px 16px;
    background: var(--surface);
    border: 1px solid var(--panel-border);
    border-radius: 8px;
    cursor: pointer;
    font-weight: bold;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
  }
  .demo-btn:hover {
    background: var(--panel-bg);
  }

  .debug-badge {
    position: absolute;
    top: 60px; /* Below TopBar */
    right: 10px;
    z-index: 20;
    padding: 4px 8px;
    background: rgba(0, 0, 0, 0.7);
    color: #fff;
    font-size: 10px;
    border-radius: 4px;
    pointer-events: none;
    font-family: monospace;
  }
</style>

<main class="shell">
  <div class="debug-badge">
    Nodes: {nodesData.length} / Accounts: {accountsData.length} / Edges: {edgesData.length}
    <br>
    {#if import.meta.env.PUBLIC_GEWEBE_API_BASE}
      Mode: REMOTE<br>
      API: {import.meta.env.PUBLIC_GEWEBE_API_BASE}
    {:else}
      Mode: DEMO (local)<br>
      Origin: {typeof window !== 'undefined' ? window.location.origin : 'server'}
    {/if}
  </div>
  <TopBar />
  <ViewPanel />

  <!-- Karte -->
  <div id="map" bind:this={mapContainer}></div>

  <button class="demo-btn" on:click={jumpToDemo}>
    Zur Demo springen
  </button>

  {#if isLoading}
    <div class="loading-overlay">
      <div class="spinner"></div>
    </div>
  {/if}

  <SelectionCard />

  <!-- Zeitleiste -->
  <TimelineDock />
</main>
