<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import type { PageData } from './$types';
  import '$lib/styles/tokens.css';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import type { Map as MapLibreMap, GeoJSONSource, Marker } from 'maplibre-gl';

  import TopBar from '$lib/components/TopBar.svelte';
  import ContextPanel from '$lib/components/ContextPanel.svelte';
  import ActionBar from '$lib/components/ActionBar.svelte';
  import SearchOverlay from '$lib/components/SearchOverlay.svelte';
  import FilterOverlay from '$lib/components/FilterOverlay.svelte';
  import type { Edge, RenderableMapPoint } from '$lib/map/types';

  import { view, selection, systemState, enterFokus } from '$lib/stores/uiView';
  import { isSearchOpen, searchQuery } from '$lib/stores/searchStore';
  import { activeFilters } from '$lib/stores/filterStore';
  import { authStore } from '$lib/auth/store';
  import { isRecord } from '$lib/utils/guards';

  import { get } from 'svelte/store';

  import { currentBasemap, HAMMER_PARK_CENTER } from '$lib/map/config/basemap.current';
  import { resolveBasemapStyle } from '$lib/map/basemap';

  import { NodesOverlay } from '$lib/map/overlay/nodes';
  import { updateEdges } from '$lib/map/overlay/edges';
  import { setupKompositionInteraction } from '$lib/map/overlay/komposition';
  import { setupFocusInteraction } from '$lib/map/overlay/focus';
  import { setupActivityInteraction } from '$lib/map/overlay/activity';

  export let data: PageData;

  $: nodesData = (data.nodes || []).map((n) => ({
    id: n.id,
    title: n.title,
    lat: n.location.lat,
    lon: n.location.lon,
    summary: n.summary,
    info: n.info,
    type: 'node',
    modules: n.modules,
    created_at: n.created_at,
    updated_at: n.updated_at,
    kind: n.kind,
    tags: n.tags
  })) satisfies RenderableMapPoint[];

  let accountsData: RenderableMapPoint[] = [];
  $: {
    const newAccountsData: RenderableMapPoint[] = [];
    for (const a of data.accounts || []) {
      if (a.public_pos) {
        newAccountsData.push({
          id: a.id,
          title: a.title,
          lat: a.public_pos.lat,
          lon: a.public_pos.lon,
          summary: a.summary,
          type: a.type, // Pass through the domain type (e.g., 'garnrolle')
          modules: a.modules,
          created_at: a.created_at
        });
      }
    }
    accountsData = newAccountsData;
  }

  $: markersData = [...nodesData, ...accountsData];

  // Robust type guards
  function isEdge(e: unknown): e is Edge {
    if (!isRecord(e)) return false;
    return (
      typeof e.id === 'string' &&
      typeof e.source_id === 'string' &&
      typeof e.target_id === 'string' &&
      typeof e.edge_kind === 'string'
    );
  }

  $: validEdges = (data.edges || []).filter(isEdge);

  let pointIds = new Set<string>();
  $: {
    const ids = new Set<string>();
    for (const p of markersData) {
      ids.add(p.id);
    }
    pointIds = ids;
  }

  $: edgesData = validEdges.filter(e => pointIds.has(e.source_id) && pointIds.has(e.target_id));

  // Search logic moved from SearchOverlay to orchestrator
  let filteredResults: RenderableMapPoint[] = [];
  let searchMatchIds = new Set<string>();

  $: {
    if ($isSearchOpen && $searchQuery.trim().length > 0) {
      const q = $searchQuery.toLowerCase();
      // Search operates strictly on currently visible/filtered markers
      filteredResults = searchBaseData.filter(m => {
        const titleMatch = m.title?.toLowerCase().includes(q);
        const summaryMatch = m.summary?.toLowerCase().includes(q);
        return titleMatch || summaryMatch;
      }).slice(0, 10);
      searchMatchIds = new Set(filteredResults.map(r => r.id));
    } else {
      filteredResults = [];
      searchMatchIds = new Set();
    }
  }

  let mapContainer: HTMLDivElement | null = null;
  let map: MapLibreMap | null = null;
  let isLoading = true;
  let lastFocusedElement: HTMLElement | null = null;

  let nodesOverlay: NodesOverlay | null = null;

  function getFilterTypeKey(m: RenderableMapPoint): string {
    return m.type === 'node' ? (m.kind || 'Knoten') : 'Garnrolle';
  }

  let availableFilterTypes: { id: string, label: string, count: number }[] = [];
  let filteredMarkersData: RenderableMapPoint[] = [];

  // Derivation of filterable types
  $: availableFilterTypes = (() => {
    const counts = new Map<string, number>();
    for (const m of markersData) {
      const typeKey = getFilterTypeKey(m);
      counts.set(typeKey, (counts.get(typeKey) || 0) + 1);
    }
    return Array.from(counts.entries()).map(([id, count]) => ({
      id,
      label: id.charAt(0).toUpperCase() + id.slice(1),
      count
    })).sort((a, b) => a.label.localeCompare(b.label));
  })();

  $: filteredMarkersData = $activeFilters.size === 0
    ? markersData
    : markersData.filter(m => $activeFilters.has(getFilterTypeKey(m)));

  $: searchBaseData = $activeFilters.size === 0 ? markersData : filteredMarkersData;

  // Reactive update for markers and search highlight strictly handled in overlay update
  $: if (nodesOverlay && filteredMarkersData && $view) {
    (async () => {
      await nodesOverlay.update(filteredMarkersData, $view.showNodes, searchMatchIds);
    })();
  }

  // Reactive update for edges
  $: if (map && markersData && edgesData && $view && map.getStyle()) {
     if (map.isStyleLoaded()) {
        updateEdges(map, edgesData, filteredMarkersData, $view.showEdges);
     } else {
        map.once('styledata', () => updateEdges(map!, edgesData, filteredMarkersData, $view.showEdges));
     }
  }


  function normalizeSelectionType(type: string | undefined): 'node' | 'account' | 'garnrolle' {
    if (type === 'account' || type === 'garnrolle') {
      return type;
    }
    return 'node';
  }

  function focusAndFlyToPoint(item: RenderableMapPoint) {
    const itemType = normalizeSelectionType(item.type);

    enterFokus({ type: itemType, id: item.id, data: item });

    const lat = item.lat;
    const lon = item.lon;
    if (map && typeof lat === 'number' && typeof lon === 'number' && !isNaN(lat) && !isNaN(lon)) {
      const currentZoom = map.getZoom();
      map.flyTo({
        center: [lon, lat],
        zoom: Math.max(currentZoom, 14),
        speed: 0.8,
        curve: 1
      });
    }
  }

  function handleSearchSelect(event: CustomEvent<RenderableMapPoint>) {
    focusAndFlyToPoint(event.detail);
  }

  // Restore focus when selection is closed or state becomes navigation
  $: if (($systemState === 'navigation' || !$selection) && lastFocusedElement) {
    const elToFocus = lastFocusedElement;
    lastFocusedElement = null; // Clear immediately to prevent loop

    // Use tick() to wait for DOM updates (e.g. context panel removed)
    // and try to focus safely.
    tick().then(() => {
      if (elToFocus && document.body.contains(elToFocus)) {
        try {
          elToFocus.focus();
        } catch (e) {
          // ignore focus errors
        }
      }
    });
  }

  async function toggleLogin() {
    if ($authStore.authenticated) {
      await authStore.logout();
    } else {
      try {
        await authStore.devLogin('7d97a42e-3704-4a33-a61f-0e0a6b4d65d8');
      } catch (e: any) {
        // Simple UI feedback for dev login issues
        window.alert(`Login failed: ${e.message}\nCheck console for details.`);
      }
    }
  }

  let cleanupKomposition: (() => void) | undefined = undefined;
  let cleanupFocus: (() => void) | undefined = undefined;
  let cleanupActivity: (() => void) | undefined = undefined;
  let unsubscribeSysState: (() => void) | undefined = undefined;

  onMount(() => {
    const handleMarkerClick = (e: Event) => {
      const target = e.target as HTMLElement;
      const markerBtn = target.closest('.map-marker') as HTMLButtonElement | null;
      if (!markerBtn || !nodesOverlay) return;

      const id = markerBtn.dataset.id;
      if (!id) return;

      const entry = nodesOverlay.getActiveMarker(id);
      if (!entry) return;

      lastFocusedElement = markerBtn;
      focusAndFlyToPoint(entry.item);
    };

    (async () => {
      const maplibregl = await import('maplibre-gl');
      const pmtiles = await import('pmtiles');

      const container = mapContainer;
      if (!container) {
        return;
      }
      container.addEventListener('click', handleMarkerClick);

      try {
        maplibregl.addProtocol('pmtiles', new pmtiles.Protocol().tile);
      } catch (e) {
        // Idempotent registration: ignore if already added (e.g. during HMR)
      }

      map = new maplibregl.Map({
        container,
        style: resolveBasemapStyle(currentBasemap),
        center: currentBasemap.center,
        zoom: currentBasemap.zoom,
        minZoom: currentBasemap.minZoom ?? 10,
        maxZoom: currentBasemap.maxZoom ?? 18,
        pitch: currentBasemap.pitch ?? 0,
        bearing: currentBasemap.bearing ?? 0,
        attributionControl: false,
        transformRequest: (url, resourceType) => {
          if (url.startsWith('pmtiles://')) {
             const remainder = url.replace('pmtiles://', '');
             // A bare alias contains no slashes.
             // If there are slashes, it's already a fully qualified or relative HTTP path wrapped in pmtiles://
             if (!remainder.includes('/')) {
               return {
                 url: `pmtiles://${window.location.origin}/local-basemap/${remainder}`
               };
             }
          }
          return { url };
        }
      });
      map.addControl(new maplibregl.NavigationControl({ showZoom: true }), 'bottom-right');
      map.addControl(new maplibregl.AttributionControl({ compact: false, customAttribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors' }), 'bottom-right');

      // Architecture Note: Basemap provides orientation. Overlays (nodes, edges, activity, etc.) carry domain meaning.
      nodesOverlay = new NodesOverlay(map);
      cleanupKomposition = setupKompositionInteraction(map);
      let sysStateStr = '';
      unsubscribeSysState = systemState.subscribe(val => { sysStateStr = val; });
      cleanupFocus = setupFocusInteraction(map, () => sysStateStr);
      cleanupActivity = setupActivityInteraction(map);

      const loadingTimeout = setTimeout(() => {
        isLoading = false;
      }, 10000);

      const finishLoading = () => {
        clearTimeout(loadingTimeout);
        isLoading = false;

        const currentSelection = get(selection);
        const currentSystemState = get(systemState);

        if (!currentSelection && currentSystemState === 'navigation') {
          const currentZoom = map?.getZoom() ?? 14;
          map?.flyTo({
            center: [HAMMER_PARK_CENTER.lon, HAMMER_PARK_CENTER.lat],
            zoom: Math.max(currentZoom, 14),
            speed: 0.8,
            curve: 1
          });
        }
      };

      map.once('load', finishLoading);
      map.on('error', () => {
        clearTimeout(loadingTimeout);
        isLoading = false;
      });

      // Expose map for testing
      if (import.meta.env.MODE === 'test' || import.meta.env.DEV) {
        (window as any).__TEST_MAP__ = map;
      }
    })();

    return () => {
      import('maplibre-gl').then(maplibregl => {
         try { maplibregl.removeProtocol('pmtiles'); } catch (e) { /* ignore */ }
      }).catch(() => { /* ignore */ });

      if (import.meta.env.MODE === 'test' || import.meta.env.DEV) {
        delete (window as any).__TEST_MAP__;
      }
      cleanupKomposition?.();
      cleanupFocus?.();
      cleanupActivity?.();
      unsubscribeSysState?.();
      nodesOverlay?.destroy();
      if (map && typeof map.remove === 'function') map.remove();
      mapContainer?.removeEventListener('click', handleMarkerClick);
    };
  });
</script>

<style>
  .shell{
    position:relative;
    height:100dvh;
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

  #map :global(.marker-account) {
    background-image: var(--marker-icon);
    background-size: contain;
    background-repeat: no-repeat;
    background-position: center;

    background-color: transparent;
    border: none;
    box-shadow: none;

    width: var(--marker-size, 34px);
    height: var(--marker-size, 34px);
    transform: none;
    border-radius: 0;
  }

  @media (hover: hover) and (pointer: fine) {
    #map :global(.map-marker:hover){
      transform: scale(1.2);
      z-index: 10;
    }
    #map :global(.marker-account:hover){
      transform: scale(1.2);
    }
  }

  #map :global(.map-marker:focus-visible){
    outline:2px solid var(--fg);
    outline-offset:2px;
    z-index: 10;
  }

  #map :global(.map-marker.search-highlight) {
    outline: 2px solid var(--primary, #005fcc);
    outline-offset: 2px;
    box-shadow: 0 0 8px 2px var(--primary, rgba(0,95,204,0.6));
    z-index: 5;
  }

  #map :global(.marker-account.search-highlight) {
    outline: 2px solid var(--primary, #005fcc);
    outline-offset: 2px;
    box-shadow: 0 0 8px 2px var(--primary, rgba(0,95,204,0.6));
  }

  #map :global(.marker-account:focus-visible) {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
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

  .debug-badge {
    position: absolute;
    top: 60px;
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
  <ContextPanel />
  <SearchOverlay {filteredResults} on:select={handleSearchSelect} />
  <FilterOverlay availableTypes={availableFilterTypes} />
  <ActionBar />
  {#if import.meta.env.DEV || import.meta.env.MODE === 'test'}
    <div class="debug-badge" data-testid="debug-badge">
      Nodes: {nodesData.length} / Accounts: {accountsData.length} / Edges: {edgesData.length}
      <br>
      {#if import.meta.env.PUBLIC_GEWEBE_API_BASE}
        Mode: REMOTE<br>
        API: {import.meta.env.PUBLIC_GEWEBE_API_BASE}
      {:else}
        Mode: DEMO (local)<br>
        Origin: {typeof window !== 'undefined' ? window.location.origin : 'server'}
      {/if}
      <br>
      <button on:click={toggleLogin} style="pointer-events: auto; margin-top: 4px; font-size: 10px; cursor: pointer;" data-testid="debug-logout">
        {$authStore.authenticated ? 'Logout' : 'Login Demo'}
      </button>
    </div>
  {/if}
  <TopBar />
  <div id="map" bind:this={mapContainer}></div>
  {#if isLoading}
    <div class="loading-overlay">
      <div class="spinner"></div>
    </div>
  {/if}
</main>
