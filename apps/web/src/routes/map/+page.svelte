<script lang="ts">
  import { onMount, tick } from 'svelte';
  import type { PageData } from './$types';
  import '$lib/styles/tokens.css';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import type { Map as MapLibreMap } from 'maplibre-gl';

  import TopBar from '$lib/components/TopBar.svelte';
  import ContextPanel from '$lib/components/ContextPanel.svelte';
  import ActionBar from '$lib/components/ActionBar.svelte';
  import SearchOverlay from '$lib/components/SearchOverlay.svelte';
  import FilterOverlay from '$lib/components/FilterOverlay.svelte';
  import type { MapEntityViewModel } from '$lib/map/types';

  import { page } from '$app/stores';

  import { view, selection, systemState, enterKomposition } from '$lib/stores/uiView';
  import { activeFilters, closeFilter } from '$lib/stores/filterStore';
  import { isSearchOpen, searchQuery, closeSearch } from '$lib/stores/searchStore';
  import { openSearchExclusive, openFilterExclusive } from '$lib/stores/overlayManager';
  import { parseMapUrlState, type MapUrlFocus, type ParsedMapUrlState } from '$lib/map/urlState';
  import {
    deriveFailedResourceLabels,
    deriveMarkerCounts,
    deriveAvailableFilterTypes,
    deriveFilteredMarkers,
    deriveSearchResults,
    deriveSearchMatchIds,
    deriveVisibleEdges,
    getFilterTypeKey,
    selectMapEntity,
  } from '$lib/stores/mapView';
  import { authStore } from '$lib/auth/store';

  import { get } from 'svelte/store';

  import { currentBasemap, HAMMER_PARK_CENTER } from '$lib/map/config/basemap.current';
  import { resolveBasemapStyle, rewritePmtilesUrl } from '$lib/map/basemap';
  import { buildMapScene } from '$lib/map/scene';

  import { NodesOverlay } from '$lib/map/overlay/nodes';
  import { updateEdges } from '$lib/map/overlay/edges';
  import { setupKompositionInteraction } from '$lib/map/overlay/komposition';
  import { setupFocusInteraction } from '$lib/map/overlay/focus';

  export let data: PageData;

  // Phase 2: Build the scene from request-scoped route data. The scene stays
  // local to this component instance (never a module-level store), so no
  // request-specific data is shared across module state. The presentation
  // derivations live as pure functions in `$lib/stores/mapView` and are fed the
  // scene together with the ephemeral UI state (filters, search).
  $: scene = buildMapScene({
    nodes: data.nodes || [],
    accounts: data.accounts || [],
    edges: data.edges || [],
    loadState: data.loadState ?? 'ok',
    resourceStatus: data.resourceStatus ?? [],
    apiBase: import.meta.env.PUBLIC_GEWEBE_API_BASE,
    basemapMode: currentBasemap.mode,
  });

  // Presentation state derived via pure functions from the local scene + UI state.
  $: loadState = scene.loadState;
  $: diagnostics = scene.diagnostics;
  $: failedLabels = deriveFailedResourceLabels(scene);
  $: markersData = scene.entities;
  $: markerCounts = deriveMarkerCounts(markersData);
  $: availableTypes = deriveAvailableFilterTypes(markersData);
  $: filteredMarkersData = deriveFilteredMarkers(markersData, $activeFilters);
  // Search is scoped to the currently visible markers (filtered set when a
  // filter is active, otherwise the full set) so it never reaches hidden ones.
  $: searchBaseMarkers = $activeFilters.size === 0 ? markersData : filteredMarkersData;
  $: filteredResults = deriveSearchResults(searchBaseMarkers, $searchQuery, $isSearchOpen);
  $: searchMatchIds = deriveSearchMatchIds(filteredResults);
  $: edgesData = deriveVisibleEdges(scene.edges, filteredMarkersData);

  let mapContainer: HTMLDivElement | null = null;
  let map: MapLibreMap | null = null;
  let mapStyleReady = false;
  let isLoading = true;
  let lastFocusedElement: HTMLElement | null = null;
  let showFilterTooltip = false;
  let filterTooltipTimeout: number | null = null;

  let nodesOverlay: NodesOverlay | null = null;

  // Reactive update for markers and search highlight strictly handled in overlay update
  $: if (nodesOverlay && filteredMarkersData && $view) {
    (async () => {
      await nodesOverlay.update(filteredMarkersData, $view.showNodes, searchMatchIds);
    })();
  }

  // Reactive update for edges – only after map style is fully loaded
  $: if (map && mapStyleReady && edgesData && $view) {
     updateEdges(map, edgesData, filteredMarkersData, $view.showEdges);
  }

  function focusAndFlyToPoint(item: MapEntityViewModel) {
    // Selection state is owned by the map-view store (delegating to uiView);
    // the route only keeps the map-side concern (flyTo).
    selectMapEntity(item);

    const lat = item.lat;
    const lon = item.lon;
    if (map && typeof lat === 'number' && typeof lon === 'number' && Number.isFinite(lat) && Number.isFinite(lon)) {
      const currentZoom = map.getZoom();
      map.flyTo({
        center: [lon, lat],
        zoom: Math.max(currentZoom, 14),
        speed: 0.8,
        curve: 1
      });
    }
  }

  function handleSearchSelect(event: CustomEvent<MapEntityViewModel>) {
    focusAndFlyToPoint(event.detail);
  }

  // --- URL addressing (UI Interaction Doctrine, first slice) -----------------
  // The URL is an addressing layer, not a second state machine: it maps query
  // parameters onto the existing uiView / overlay stores. uiView stays the
  // single source of truth and there is no store -> URL synchronisation here.
  //
  // Two intents are kept strictly apart:
  //  - Immediate intents (compose=node, lens=filter|search) need no map data and
  //    are applied as soon as the URL is known.
  //  - Focus intents (focus=node|garnrolle|account:<id>) need the scene entities
  //    and only count as resolved once their target is actually found.
  // Priority is compose > focus > lens. A valid-but-unresolved focus deliberately
  // blocks the lens fallback so a deep link never lands on the wrong surface.
  function findMapEntityForFocus(focus: MapUrlFocus): MapEntityViewModel | null {
    return markersData.find((item) => item.type === focus.type && item.id === focus.id) ?? null;
  }

  function applyImmediateMapUrlAddressing(parsed: ParsedMapUrlState) {
    if (parsed.compose === 'node') {
      closeSearch();
      closeFilter();
      enterKomposition({ mode: 'new-knoten', source: 'action-bar' });
      return;
    }
    // A valid focus takes precedence. While it is unresolved, no lower-priority
    // lens fallback may run.
    if (parsed.focus) {
      return;
    }
    if (parsed.lens === 'filter') {
      openFilterExclusive();
      return;
    }
    if (parsed.lens === 'search') {
      openSearchExclusive();
      return;
    }
  }

  function tryApplyFocusMapUrlAddressing(parsed: ParsedMapUrlState): boolean {
    if (!parsed.focus) return true;
    const item = findMapEntityForFocus(parsed.focus);
    if (!item) return false;
    closeSearch();
    closeFilter();
    focusAndFlyToPoint(item);
    return true;
  }

  // Identity key over the addressable entities, so a focus retry can react to
  // entity *content* changes, not only to a changed list length.
  function mapEntityAddressKey(items: MapEntityViewModel[]): string {
    return items.map((item) => `${item.type}:${item.id}`).join('|');
  }

  // Separate locks: immediate intents fire once per distinct query; focus only
  // locks once its target is resolved, and retries while it stays unresolved.
  let lastAppliedImmediateUrlSearch = '';
  let lastResolvedFocusUrlSearch = '';
  let lastFocusAttemptKey = '';
  $: {
    const search = $page.url.search;
    const parsed = parseMapUrlState($page.url.searchParams);
    const entityAddressKey = mapEntityAddressKey(markersData);
    if (search !== lastAppliedImmediateUrlSearch) {
      lastAppliedImmediateUrlSearch = search;
      applyImmediateMapUrlAddressing(parsed);
      // compose is final and blocks focus/lens.
      if (parsed.compose === 'node') {
        lastResolvedFocusUrlSearch = search;
      }
      // Without a valid focus there is nothing left for the focus pass to do.
      if (!parsed.focus) {
        lastResolvedFocusUrlSearch = search;
      }
      // A new query string means a fresh focus attempt may run again.
      lastFocusAttemptKey = '';
    }
    if (
      parsed.focus &&
      search !== lastResolvedFocusUrlSearch &&
      entityAddressKey.length > 0
    ) {
      const focusAttemptKey = `${search}::${entityAddressKey}`;
      if (focusAttemptKey !== lastFocusAttemptKey) {
        lastFocusAttemptKey = focusAttemptKey;
        if (tryApplyFocusMapUrlAddressing(parsed)) {
          lastResolvedFocusUrlSearch = search;
        }
      }
    }
  }

  function handleZoomToOwnGarnrolle() {
    if (!$authStore.authenticated || !$authStore.account_id) return;
    const accountId = $authStore.account_id;
    // Find the marker corresponding to the user's account
    const userMarker = markersData.find(m => m.id === accountId && m.type === 'garnrolle');

    if (userMarker) {
      const typeKey = getFilterTypeKey(userMarker);
      const isFilteredOut = $activeFilters.size > 0 && !$activeFilters.has(typeKey);

      // Do not override filters: if the user's marker is filtered out, inform the user instead of mutating filter state.
      if (isFilteredOut) {
        if (filterTooltipTimeout !== null) {
          window.clearTimeout(filterTooltipTimeout);
        }
        showFilterTooltip = false; // brief reset for animation restart

        tick().then(() => {
          showFilterTooltip = true;
          filterTooltipTimeout = window.setTimeout(() => {
            showFilterTooltip = false;
            filterTooltipTimeout = null;
          }, 4000);
        });
      } else {
        focusAndFlyToPoint(userMarker);
      }
    }
    // Note: If no marker is found (e.g. not public/placed), this deliberately silently no-ops
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
  let unsubscribeSysState: (() => void) | undefined = undefined;

  const shouldExposeTestMap = import.meta.env.DEV || import.meta.env.VITE_PUBLIC_ENABLE_TEST_MAP === 'true';

  onMount(() => {
    let maplibreModule: any = null;
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
      maplibreModule = maplibregl;
      const container = mapContainer;
      if (!container) {
        return;
      }
      container.addEventListener('click', handleMarkerClick);

      let transformRequestFn: ((url: string, resourceType?: any) => { url: string }) | undefined = undefined;

      // PMTiles dev infrastructure is intentionally prepared now, including the runtime
      // dependency 'pmtiles'. The current runtime stays strictly on 'remote-style', since
      // real local artifact proof is still missing. This setup exists solely to reduce later
      // activation cost and does NOT claim that 'local-sovereign' is already working end-to-end.
      if (currentBasemap.mode === 'local-sovereign') {
        const pmtiles = await import('pmtiles');
        try {
          maplibregl.addProtocol('pmtiles', new pmtiles.Protocol().tile);
        } catch (e: any) {
          if (!e.message?.includes('already registered')) {
            console.warn('Unexpected error registering PMTiles protocol:', e);
          }
        }

        transformRequestFn = (url: string, resourceType?: any) => {
          return { url: rewritePmtilesUrl(url, window.location.origin) };
        };
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
        transformRequest: transformRequestFn,
      });
      map.addControl(new maplibregl.NavigationControl({ showZoom: true }), 'bottom-right');
      map.addControl(new maplibregl.AttributionControl({ compact: false, customAttribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors' }), 'bottom-right');

      // Architecture Note: Basemap provides orientation. Overlays (nodes, edges, etc.) carry domain meaning.
      nodesOverlay = new NodesOverlay(map);
      cleanupKomposition = setupKompositionInteraction(map);
      let sysStateStr = '';
      unsubscribeSysState = systemState.subscribe(val => { sysStateStr = val; });
      cleanupFocus = setupFocusInteraction(map, () => sysStateStr);

      const loadingTimeout = setTimeout(() => {
        isLoading = false;
      }, 10000);

      const finishLoading = () => {
        clearTimeout(loadingTimeout);
        isLoading = false;
        mapStyleReady = true;

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
      if (shouldExposeTestMap) {
        (window as any).__TEST_MAP__ = map;
      }
    })();

    return () => {
      if (filterTooltipTimeout !== null) {
        window.clearTimeout(filterTooltipTimeout);
        filterTooltipTimeout = null;
      }
      if (shouldExposeTestMap) {
        delete (window as any).__TEST_MAP__;
      }
      cleanupKomposition?.();
      cleanupFocus?.();
      unsubscribeSysState?.();
      nodesOverlay?.destroy();
      if (map && typeof map.remove === 'function') map.remove();
      mapContainer?.removeEventListener('click', handleMarkerClick);
      if (currentBasemap.mode === 'local-sovereign' && maplibreModule) {
        try {
          maplibreModule.removeProtocol('pmtiles');
        } catch (e: any) {
          if (!e.message?.includes('not registered')) {
            console.warn('Unexpected error removing PMTiles protocol:', e);
          }
        }
      }
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

  .filter-tooltip {
    position: fixed;
    top: 80px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg);
    color: var(--text);
    padding: 12px 16px;
    border-radius: 8px;
    border: 1px solid var(--panel-border);
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    z-index: 1000;
    font-size: 0.9rem;
    font-weight: 500;
    pointer-events: none;
    text-align: center;
    animation: fadeInOut 4s ease forwards;
  }

  @keyframes fadeInOut {
    0% { opacity: 0; transform: translate(-50%, -10px); }
    10% { opacity: 1; transform: translate(-50%, 0); }
    90% { opacity: 1; transform: translate(-50%, 0); }
    100% { opacity: 0; transform: translate(-50%, -10px); }
  }

  .degraded-banner {
    position: absolute;
    top: 60px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 30;
    padding: 8px 16px;
    background: rgba(180, 130, 0, 0.9);
    color: #fff;
    font-size: 0.85rem;
    font-weight: 500;
    border-radius: 6px;
    pointer-events: none;
    text-align: center;
    white-space: nowrap;
  }

  .degraded-banner--failed {
    background: rgba(180, 40, 40, 0.9);
  }
</style>

<main class="shell">
  {#if showFilterTooltip}
    <div class="filter-tooltip" role="status" aria-live="polite">
      Du hast Garnrollen per Filter ausgeblendet – auch deine eigene.
    </div>
  {/if}

  {#if loadState === 'partial'}
    <div class="degraded-banner" role="alert" data-testid="load-state-partial">
      Einige Kartendaten konnten nicht geladen werden ({failedLabels.join(', ')}).
    </div>
  {/if}
  {#if loadState === 'failed'}
    <div class="degraded-banner degraded-banner--failed" role="alert" data-testid="load-state-failed">
      Kartendaten konnten nicht geladen werden.
    </div>
  {/if}

  <ContextPanel />
  <SearchOverlay {filteredResults} on:select={handleSearchSelect} />
  <FilterOverlay availableTypes={availableTypes} />
  <ActionBar />
  {#if import.meta.env.DEV || import.meta.env.MODE === 'test'}
    <div class="debug-badge" data-testid="debug-badge">
      Nodes: {markerCounts.nodes} / Accounts: {markerCounts.accounts} / Edges: {edgesData.length}
      <br>
      API: {diagnostics.apiMode} / Basemap: {diagnostics.basemapMode}
      {#if diagnostics.degraded}
        <br>⚠ Load: {loadState}
      {/if}
      <br>
      <button on:click={toggleLogin} style="pointer-events: auto; margin-top: 4px; font-size: 10px; cursor: pointer;" data-testid="debug-logout">
        {$authStore.authenticated ? 'Logout' : 'Login Demo'}
      </button>
    </div>
  {/if}
  <TopBar on:zoomToOwnGarnrolle={handleZoomToOwnGarnrolle} />
  <div id="map" bind:this={mapContainer}></div>
  {#if isLoading}
    <div class="loading-overlay">
      <div class="spinner"></div>
    </div>
  {/if}
</main>
