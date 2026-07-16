<script lang="ts">
  import { onMount, tick } from "svelte";
  import type { PageData } from "./$types";
  import "$lib/styles/tokens.css";
  import "maplibre-gl/dist/maplibre-gl.css";
  import type { Map as MapLibreMap } from "maplibre-gl";

  import TopBar from "$lib/components/TopBar.svelte";
  import ContextPanel from "$lib/components/ContextPanel.svelte";
  import ToolFan from "$lib/components/ToolFan.svelte";
  import SearchOverlay from "$lib/components/SearchOverlay.svelte";
  import SearchDirectionIndicators from "$lib/components/SearchDirectionIndicators.svelte";
  import FilterOverlay from "$lib/components/FilterOverlay.svelte";
  import type { MapEntityViewModel } from "$lib/map/types";
  import {
    deriveSearchDirectionIndicators,
    resolveInitialMapCamera,
    type SearchDirectionIndicator,
    type ViewportBounds,
  } from "$lib/map/searchNavigation";

  import { page } from "$app/stores";
  import { invalidate } from "$app/navigation";

  import {
    view,
    selection,
    systemState,
    contextPanelOpen,
    enterKomposition,
    leaveToNavigation,
    lastCreatedNodeId,
  } from "$lib/stores/uiView";
  import {
    activeFilters,
    isFilterOpen,
    closeFilter,
  } from "$lib/stores/filterStore";
  import {
    isSearchOpen,
    searchQuery,
    closeSearch,
  } from "$lib/stores/searchStore";
  import {
    openSearchExclusive,
    openFilterExclusive,
  } from "$lib/stores/overlayManager";
  import {
    parseMapUrlState,
    type MapUrlFocus,
    type ParsedMapUrlState,
  } from "$lib/map/urlState";
  import {
    deriveFailedResourceLabels,
    deriveMarkerCounts,
    deriveAvailableFilterTypes,
    deriveFilteredMarkers,
    deriveSearchResults,
    deriveSearchMatchIds,
    deriveVisibleEdges,
    selectMapEntity,
  } from "$lib/stores/mapView";
  import { authStore, type AuthStatus } from "$lib/auth/store";
  import { get } from "svelte/store";

  import { currentBasemap } from "$lib/map/config/basemap.current";
  import { resolveBasemapStyle, rewritePmtilesUrl } from "$lib/map/basemap";
  import { getGarnrolleMarkerScale } from "$lib/map/markerScale";
  import { buildMapScene } from "$lib/map/scene";

  import { NodesOverlay } from "$lib/map/overlay/nodes";
  import { updateEdges } from "$lib/map/overlay/edges";
  import { setupKompositionInteraction } from "$lib/map/overlay/komposition";
  import { setupFocusInteraction } from "$lib/map/overlay/focus";

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
    loadState: data.loadState ?? "ok",
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
  $: searchBaseMarkers =
    $activeFilters.size === 0 ? markersData : filteredMarkersData;
  $: filteredResults = deriveSearchResults(
    searchBaseMarkers,
    $searchQuery,
    $isSearchOpen,
  );
  $: searchMatchIds = deriveSearchMatchIds(filteredResults);
  $: edgesData = deriveVisibleEdges(scene.edges, filteredMarkersData);

  let mapContainer: HTMLDivElement | null = null;
  let map: MapLibreMap | null = null;
  let mapStyleReady = false;
  let isLoading = true;
  let lastFocusedElement: HTMLElement | null = null;

  let nodesOverlay: NodesOverlay | null = null;
  let searchDirectionIndicators: SearchDirectionIndicator[] = [];
  let searchDirectionFrame: number | null = null;

  async function resolveInitialAuthStatus(
    timeoutMs = 2500,
  ): Promise<AuthStatus> {
    const known = get(authStore);
    if (known.authenticated) return known;

    return new Promise((resolve) => {
      let settled = false;
      const finish = (status: AuthStatus) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timeout);
        resolve(status);
      };
      const timeout = window.setTimeout(() => {
        finish(get(authStore));
      }, timeoutMs);

      authStore.checkAuth().then(finish, () => finish(get(authStore)));
    });
  }

  function getUsableSearchViewport(): ViewportBounds | null {
    if (!mapContainer) return null;
    const mapRect = mapContainer.getBoundingClientRect();
    const edgeInset = 28;
    let left = edgeInset;
    let top = edgeInset;
    let right = mapRect.width - edgeInset;
    let bottom = mapRect.height - edgeInset;

    const topBarRect = document
      .querySelector<HTMLElement>(".topbar")
      ?.getBoundingClientRect();
    if (topBarRect)
      top = Math.max(top, topBarRect.bottom - mapRect.top + edgeInset);

    const searchRect = document
      .querySelector<HTMLElement>('[data-testid="search-overlay"]')
      ?.getBoundingClientRect();
    if (searchRect) {
      top = Math.max(top, searchRect.bottom - mapRect.top + edgeInset);
    }

    const filterRect = document
      .querySelector<HTMLElement>('[data-testid="filter-overlay"]')
      ?.getBoundingClientRect();
    if (filterRect) {
      top = Math.max(top, filterRect.bottom - mapRect.top + edgeInset);
    }

    const toolTriggerRect = document
      .querySelector<HTMLElement>('[data-testid="tool-fan-trigger"]')
      ?.getBoundingClientRect();
    if (toolTriggerRect && toolTriggerRect.height > 0) {
      bottom = Math.min(bottom, toolTriggerRect.top - mapRect.top - edgeInset);
    }

    const panelRect = document
      .querySelector<HTMLElement>('[data-testid="context-panel"]')
      ?.getBoundingClientRect();
    if (panelRect && panelRect.left > mapRect.left) {
      right = Math.min(right, panelRect.left - mapRect.left - edgeInset);
    }

    return right > left && bottom > top ? { left, top, right, bottom } : null;
  }

  function updateSearchDirectionIndicators() {
    if (
      !map ||
      !$isSearchOpen ||
      !$searchQuery.trim() ||
      filteredResults.length === 0
    ) {
      searchDirectionIndicators = [];
      return;
    }
    const bounds = getUsableSearchViewport();
    if (!bounds) {
      searchDirectionIndicators = [];
      return;
    }
    const projected = filteredResults.map((item) => ({
      item,
      point: map!.project([item.lon, item.lat]),
    }));
    searchDirectionIndicators = deriveSearchDirectionIndicators(
      projected,
      bounds,
    );
  }

  function scheduleSearchDirectionIndicators() {
    if (searchDirectionFrame !== null) return;
    searchDirectionFrame = window.requestAnimationFrame(() => {
      searchDirectionFrame = null;
      updateSearchDirectionIndicators();
    });
  }

  function updateGarnrolleMarkerScale() {
    if (!map || !mapContainer) return;

    mapContainer.style.setProperty(
      "--garnrolle-marker-scale",
      getGarnrolleMarkerScale(map.getZoom()).toFixed(3),
    );
  }

  // Reactive update for markers and search highlight strictly handled in overlay update
  $: if (nodesOverlay && filteredMarkersData && $view) {
    (async () => {
      await nodesOverlay.update(
        filteredMarkersData,
        $view.showNodes,
        searchMatchIds,
      );
    })();
  }

  $: {
    filteredResults;
    $isSearchOpen;
    $searchQuery;
    $contextPanelOpen;
    if (map) tick().then(scheduleSearchDirectionIndicators);
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
    if (
      map &&
      typeof lat === "number" &&
      typeof lon === "number" &&
      Number.isFinite(lat) &&
      Number.isFinite(lon)
    ) {
      const currentZoom = map.getZoom();
      map.flyTo({
        center: [lon, lat],
        zoom: Math.max(currentZoom, 14),
        speed: 0.8,
        curve: 1,
      });
    }
  }

  function handleSearchSelect(event: CustomEvent<MapEntityViewModel>) {
    focusAndFlyToPoint(event.detail);
  }

  function handleSearchDirectionSelect(event: CustomEvent<MapEntityViewModel>) {
    closeSearch();
    focusAndFlyToPoint(event.detail);
  }

  function handleRelatedSelect(
    event: CustomEvent<{ type: "node" | "garnrolle"; id: string }>,
  ) {
    const related = markersData.find(
      (item) => item.id === event.detail.id && item.type === event.detail.type,
    );
    if (related) focusAndFlyToPoint(related);
  }

  async function handleDomainChanged(
    event: CustomEvent<{ action: "updated" | "deleted" }>,
  ) {
    if (event.detail.action === "deleted") leaveToNavigation();
    await invalidate("weltgewebe:domain-data");
  }

  // After KompositionPanel creates a node (+ its account->node edge) and
  // reloads route data, focus/fly-to it once it shows up in the freshly
  // rebuilt scene. Retries on later markersData updates while unresolved
  // (e.g. the reload is still in flight when this first runs).
  $: if ($lastCreatedNodeId) {
    const created = markersData.find(
      (m) => m.id === $lastCreatedNodeId && m.type === "node",
    );
    if (created) {
      focusAndFlyToPoint(created);
      lastCreatedNodeId.set(null);
    }
  }

  // --- URL addressing (UI Interaction Doctrine, first slice) -----------------
  // The URL is an addressing layer, not a second state machine: it maps query
  // parameters onto the existing uiView / overlay stores. uiView stays the
  // single source of truth and there is no store -> URL synchronisation here.
  //
  // Two intents are kept strictly apart:
  //  - Immediate intents (compose=node, lens=filter|search) need no map data and
  //    are applied as soon as the URL is known. They also leave any stale
  //    focus/composition state so the addressed surface always starts clean.
  //  - Focus intents (focus=node|garnrolle|account:<id>) need the scene entities
  //    and only count as resolved once their target is actually found.
  // Priority is compose > focus > lens. A valid-but-unresolved focus deliberately
  // blocks the lens fallback so a deep link never lands on the wrong surface.
  function findMapEntityForFocus(
    focus: MapUrlFocus,
    items: MapEntityViewModel[],
  ): MapEntityViewModel | null {
    return (
      items.find((item) => item.type === focus.type && item.id === focus.id) ??
      null
    );
  }

  function applyImmediateMapUrlAddressing(parsed: ParsedMapUrlState) {
    if (parsed.compose) {
      closeSearch();
      closeFilter();
      enterKomposition({
        mode: parsed.compose === "garnrolle" ? "place-garnrolle" : "new-knoten",
        source: "tool-fan",
      });
      return;
    }
    // A valid focus takes precedence: leave stale focus/composition and close
    // overlays now; the focus pass resolves the target once data is available.
    // While it is unresolved, no lower-priority lens fallback may run.
    if (parsed.focus) {
      closeSearch();
      closeFilter();
      leaveToNavigation();
      return;
    }
    // Lens-only (or empty / invalid-lens) URL: leave any prior focus/composition
    // first. If the URL still addresses a valid lens, use the exclusive overlay
    // helpers so cross-overlay focus-restore suppression stays intact (and the
    // search query is not cleared unnecessarily). If it addresses no valid lens,
    // close stale lens overlays — this matters for same-route/popstate
    // transitions (e.g. /map?lens=filter -> /map) where stores are not reset.
    leaveToNavigation();
    if (parsed.lens === "filter") {
      openFilterExclusive();
      return;
    }
    if (parsed.lens === "search") {
      openSearchExclusive();
      return;
    }
    closeSearch();
    closeFilter();
  }

  function tryApplyFocusMapUrlAddressing(
    parsed: ParsedMapUrlState,
    items: MapEntityViewModel[],
  ): boolean {
    if (!parsed.focus) return true;
    const item = findMapEntityForFocus(parsed.focus, items);
    if (!item) return false;
    closeSearch();
    closeFilter();
    focusAndFlyToPoint(item);
    return true;
  }

  // Separate locks: immediate intents fire once per distinct query; focus only
  // locks once its target is resolved, and retries while it stays unresolved.
  // `null` sentinels (not '') ensure the very first render — including plain
  // `/map` with an empty query — runs through the effect and leaves stale state.
  let lastAppliedImmediateUrlSearch: string | null = null;
  let lastResolvedFocusUrlSearch: string | null = null;
  $: {
    const search = $page.url.search;
    const parsed = parseMapUrlState($page.url.searchParams);
    if (search !== lastAppliedImmediateUrlSearch) {
      lastAppliedImmediateUrlSearch = search;
      applyImmediateMapUrlAddressing(parsed);
      // compose is final; without a valid focus there is nothing for the focus
      // pass to do. Either way the focus lock is satisfied for this query.
      if (parsed.compose || !parsed.focus) {
        lastResolvedFocusUrlSearch = search;
      }
    }
    // Focus resolves directly against the live entity list, so the data
    // dependency stays visible to Svelte without an artificial key. A retry can
    // still happen on a later markersData change while focus is unresolved.
    if (
      parsed.focus &&
      search !== lastResolvedFocusUrlSearch &&
      markersData.length > 0
    ) {
      if (tryApplyFocusMapUrlAddressing(parsed, markersData)) {
        lastResolvedFocusUrlSearch = search;
      }
    }
  }

  // Restore focus when selection is closed or state becomes navigation
  $: if (($systemState === "navigation" || !$selection) && lastFocusedElement) {
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
        await authStore.devLogin("7d97a42e-3704-4a33-a61f-0e0a6b4d65d8");
      } catch (e: any) {
        // Simple UI feedback for dev login issues
        window.alert(`Login failed: ${e.message}\nCheck console for details.`);
      }
    }
  }

  let cleanupKomposition: (() => void) | undefined = undefined;
  let cleanupFocus: (() => void) | undefined = undefined;
  let unsubscribeSysState: (() => void) | undefined = undefined;

  const shouldExposeTestMap =
    import.meta.env.DEV ||
    import.meta.env.VITE_PUBLIC_ENABLE_TEST_MAP === "true";

  onMount(() => {
    let maplibreModule: any = null;
    // onMount returns its cleanup synchronously while the initialiser below is
    // still suspended on `await import('maplibre-gl')`. If the component is
    // destroyed in that window the cleanup finds `map`/`nodesOverlay` still
    // undefined and tears down nothing, and the initialiser would then go on to
    // build a map, bind listeners and register protocols that nobody ever
    // removes. Every await in the initialiser therefore re-checks this flag.
    let destroyed = false;
    // Hoisted so the cleanup can clear it; otherwise a component destroyed
    // before the style loads leaves a 10s timer pointing at dead state.
    let loadingTimeout: ReturnType<typeof setTimeout> | undefined = undefined;
    const handleSearchViewportChange = () => {
      scheduleSearchDirectionIndicators();
    };
    const handleMarkerClick = (e: Event) => {
      const target = e.target as HTMLElement;
      const markerBtn = target.closest(
        ".map-marker",
      ) as HTMLButtonElement | null;
      if (!markerBtn || !nodesOverlay) return;

      const id = markerBtn.dataset.id;
      if (!id) return;

      const entry = nodesOverlay.getActiveMarker(id);
      if (!entry) return;

      lastFocusedElement = markerBtn;
      focusAndFlyToPoint(entry.item);
    };

    (async () => {
      const [maplibregl, initialAuth] = await Promise.all([
        import("maplibre-gl"),
        resolveInitialAuthStatus(),
      ]);
      if (destroyed) return;
      const container = mapContainer;
      if (!container) {
        return;
      }

      let transformRequestFn:
        | ((url: string, resourceType?: any) => { url: string })
        | undefined = undefined;

      // PMTiles dev infrastructure is intentionally prepared now, including the runtime
      // dependency 'pmtiles'. The current runtime stays strictly on 'remote-style', since
      // real local artifact proof is still missing. This setup exists solely to reduce later
      // activation cost and does NOT claim that 'local-sovereign' is already working end-to-end.
      if (currentBasemap.mode === "local-sovereign") {
        const pmtiles = await import("pmtiles");
        if (destroyed) return;
        try {
          maplibregl.addProtocol("pmtiles", new pmtiles.Protocol().tile);
        } catch (e: any) {
          if (!e.message?.includes("already registered")) {
            console.warn("Unexpected error registering PMTiles protocol:", e);
          }
        }

        transformRequestFn = (url: string, resourceType?: any) => {
          return { url: rewritePmtilesUrl(url, window.location.origin) };
        };
      }

      // Past the last await boundary: from here on the cleanup below observes
      // every resource this initialiser creates. `maplibreModule` gates the
      // pmtiles protocol removal, so it must not be published before the
      // protocol is actually registered.
      maplibreModule = maplibregl;
      container.addEventListener("click", handleMarkerClick);

      const initialUrlState = parseMapUrlState(get(page).url.searchParams);
      const initialCamera = resolveInitialMapCamera(
        markersData,
        initialAuth,
        initialUrlState.focus,
        [currentBasemap.center[0], currentBasemap.center[1]],
        currentBasemap.zoom,
      );

      map = new maplibregl.Map({
        container,
        style: resolveBasemapStyle(currentBasemap),
        center: initialCamera.center,
        zoom: initialCamera.zoom,
        minZoom: currentBasemap.minZoom ?? 10,
        maxZoom: currentBasemap.maxZoom ?? 18,
        pitch: currentBasemap.pitch ?? 0,
        bearing: currentBasemap.bearing ?? 0,
        attributionControl: false,
        transformRequest: transformRequestFn,
      });
      updateGarnrolleMarkerScale();
      map.on("zoom", updateGarnrolleMarkerScale);
      map.addControl(
        new maplibregl.NavigationControl({ showZoom: true }),
        "bottom-right",
      );
      map.addControl(
        new maplibregl.AttributionControl({
          compact: false,
          customAttribution:
            '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
        }),
        "bottom-right",
      );

      // Architecture Note: Basemap provides orientation. Overlays (nodes, edges, etc.) carry domain meaning.
      nodesOverlay = new NodesOverlay(map);
      cleanupKomposition = setupKompositionInteraction(map);
      let sysStateStr = "";
      unsubscribeSysState = systemState.subscribe((val) => {
        sysStateStr = val;
      });
      cleanupFocus = setupFocusInteraction(map, () => sysStateStr);
      map.on("move", handleSearchViewportChange);
      map.on("resize", handleSearchViewportChange);

      loadingTimeout = setTimeout(() => {
        isLoading = false;
      }, 10000);

      const finishLoading = () => {
        clearTimeout(loadingTimeout);
        isLoading = false;
        mapStyleReady = true;
        scheduleSearchDirectionIndicators();
      };

      map.once("load", finishLoading);
      map.on("error", () => {
        clearTimeout(loadingTimeout);
        isLoading = false;
      });

      // Expose map for testing
      if (shouldExposeTestMap) {
        (window as any).__TEST_MAP__ = map;
      }
    })();

    return () => {
      // Signals the async initialiser to stop at its next await boundary, so a
      // component destroyed mid-import never finishes building a map.
      destroyed = true;
      if (loadingTimeout !== undefined) {
        clearTimeout(loadingTimeout);
        loadingTimeout = undefined;
      }
      if (shouldExposeTestMap) {
        delete (window as any).__TEST_MAP__;
      }
      cleanupKomposition?.();
      cleanupFocus?.();
      unsubscribeSysState?.();
      if (searchDirectionFrame !== null) {
        window.cancelAnimationFrame(searchDirectionFrame);
        searchDirectionFrame = null;
      }
      searchDirectionIndicators = [];
      nodesOverlay?.destroy();
      if (map) {
        map.off("zoom", updateGarnrolleMarkerScale);
        map.off("move", handleSearchViewportChange);
        map.off("resize", handleSearchViewportChange);
        if (typeof map.remove === "function") map.remove();
      }
      mapContainer?.removeEventListener("click", handleMarkerClick);
      if (currentBasemap.mode === "local-sovereign" && maplibreModule) {
        try {
          maplibreModule.removeProtocol("pmtiles");
        } catch (e: any) {
          if (!e.message?.includes("not registered")) {
            console.warn("Unexpected error removing PMTiles protocol:", e);
          }
        }
      }
    };
  });
</script>

<main
  class="shell"
  class:panel-open={$contextPanelOpen}
  class:search-open={$isSearchOpen}
  class:filter-open={$isFilterOpen}
>
  {#if loadState === "partial"}
    <div class="degraded-banner" role="alert" data-testid="load-state-partial">
      Einige Kartendaten konnten nicht geladen werden ({failedLabels.join(
        ", ",
      )}).
    </div>
  {/if}
  {#if loadState === "failed"}
    <div
      class="degraded-banner degraded-banner--failed"
      role="alert"
      data-testid="load-state-failed"
    >
      Kartendaten konnten nicht geladen werden.
    </div>
  {/if}

  <ContextPanel
    on:selectRelated={handleRelatedSelect}
    on:domainChanged={handleDomainChanged}
  />
  <SearchOverlay {filteredResults} on:select={handleSearchSelect} />
  <SearchDirectionIndicators
    indicators={searchDirectionIndicators}
    on:select={handleSearchDirectionSelect}
  />
  <FilterOverlay {availableTypes} filteredResults={filteredMarkersData} />
  <ToolFan />
  {#if import.meta.env.DEV || import.meta.env.MODE === "test"}
    <div class="debug-badge" data-testid="debug-badge">
      Nodes: {markerCounts.nodes} / Accounts: {markerCounts.accounts} / Edges: {edgesData.length}
      <br />
      API: {diagnostics.apiMode} / Basemap: {diagnostics.basemapMode}
      {#if diagnostics.degraded}
        <br />⚠ Load: {loadState}
      {/if}
      <br />
      <button
        on:click={toggleLogin}
        style="pointer-events: auto; margin-top: 4px; font-size: 10px; cursor: pointer;"
        data-testid="debug-logout"
      >
        {$authStore.authenticated ? "Logout" : "Login Demo"}
      </button>
    </div>
  {/if}
  <TopBar />
  <div
    id="map"
    class:panel-open={$contextPanelOpen}
    class:search-open={$isSearchOpen}
    class:filter-open={$isFilterOpen}
    bind:this={mapContainer}
  ></div>
  {#if isLoading}
    <div class="loading-overlay">
      <div class="spinner"></div>
    </div>
  {/if}
</main>

<style>
  .shell {
    position: relative;
    height: 100dvh;
    height: calc(
      100dvh - env(safe-area-inset-top) - env(safe-area-inset-bottom)
    );
    width: 100vw;
    overflow: hidden;
    background: var(--bg);
    color: var(--text);
    padding-top: env(safe-area-inset-top);
    padding-bottom: env(safe-area-inset-bottom);
  }
  #map {
    position: absolute;
    inset: 0;
  }
  #map :global(canvas) {
    filter: grayscale(0.2) saturate(0.75) brightness(1.03) contrast(0.95);
  }

  /*
   * MapLibre owns the outer marker transform and updates it every render frame.
   * Weltgewebe effects belong on the inner visual so markers stay map-locked.
   */
  #map :global(.map-marker) {
    appearance: none;
    -webkit-appearance: none;
    width: 44px;
    height: 44px;
    min-width: 0;
    min-height: 0;
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    border: 0;
    border-radius: 0;
    background: transparent;
    display: grid;
    place-items: center;
    color: var(--bg);
    cursor: pointer;
    box-shadow: none;
    transition: none;
  }

  #map :global(.map-marker__visual) {
    width: 24px;
    height: 24px;
    box-sizing: border-box;
    border-radius: 999px;
    border: 2px solid var(--panel-border);
    background: var(--accent, #ff8c42);
    display: grid;
    place-items: center;
    color: var(--bg);
    box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.25);
    align-self: end;
    justify-self: center;
    transform-origin: center;
    transition: transform 0.15s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    pointer-events: none;
  }

  #map :global(.marker-account) {
    width: 44px;
    height: 44px;
  }

  #map :global(.marker-account__visual) {
    width: 44px;
    height: 44px;
    background: transparent;
    border: none;
    box-shadow: none;
    border-radius: 0;
    transform-origin: center bottom;
  }

  #map :global(.marker-account__icon) {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
    transform: scale(var(--garnrolle-marker-scale, 1));
    transform-origin: center bottom;
    pointer-events: none;
    user-select: none;
    -webkit-user-drag: none;
  }

  @media (hover: hover) and (pointer: fine) {
    #map :global(.map-marker:hover .map-marker__visual) {
      transform: scale(1.2);
    }
    #map :global(.map-marker:hover) {
      z-index: 10;
    }
  }

  #map :global(.map-marker:focus-visible) {
    outline: 2px solid var(--fg);
    outline-offset: 2px;
    z-index: 10;
  }

  #map :global(.map-marker.search-highlight) {
    outline: 2px solid var(--primary, #005fcc);
    outline-offset: 2px;
    box-shadow: 0 0 8px 2px var(--primary, rgba(0, 95, 204, 0.6));
    z-index: 5;
  }

  #map :global(.marker-account.search-highlight) {
    outline: 2px solid var(--primary, #005fcc);
    outline-offset: 2px;
    box-shadow: 0 0 8px 2px var(--primary, rgba(0, 95, 204, 0.6));
  }

  #map :global(.marker-account:focus-visible) {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
  }

  #map :global(.maplibregl-ctrl-bottom-right) {
    right: calc(var(--tool-fan-collapsed-width) + 28px) !important;
    bottom: calc(env(safe-area-inset-bottom) + 12px) !important;
  }

  :global(.tool-fan.expanded) ~ #map :global(.maplibregl-ctrl-bottom-right) {
    right: 256px !important;
  }

  #map :global(.maplibregl-ctrl-group button) {
    width: 44px;
    height: 44px;
  }

  @media (min-width: 769px) {
    #map.panel-open :global(.maplibregl-ctrl-bottom-right) {
      right: calc(
        var(--context-panel-width) + var(--tool-fan-collapsed-width) + 28px
      ) !important;
    }

    :global(.tool-fan.expanded.panel-open)
      ~ #map.panel-open
      :global(.maplibregl-ctrl-bottom-right) {
      right: calc(var(--context-panel-width) + 256px) !important;
    }
  }

  @media (max-width: 768px) {
    #map.panel-open :global(.maplibregl-ctrl-bottom-right) {
      top: calc(env(safe-area-inset-top) + var(--toolbar-offset) + 8px);
      right: 10px !important;
      bottom: auto !important;
    }
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
    border: 3px solid rgba(255, 255, 255, 0.1);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

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

  .degraded-banner--failed {
    background: rgba(180, 40, 40, 0.9);
  }
</style>
