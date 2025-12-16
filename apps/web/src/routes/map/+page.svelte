<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import type { PageData } from './$types';
  import {
    drawerQueryDefaults,
    readDrawerParam,
    writeDrawerParam,
    type DrawerKey
  } from './drawerDefaults';
  import '$lib/styles/tokens.css';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import type { Map as MapLibreMap } from 'maplibre-gl';
  import TopBar from '$lib/components/TopBar.svelte';
  import Drawer from '$lib/components/Drawer.svelte';
  import TimelineDock from '$lib/components/TimelineDock.svelte';
  import type { Node } from './types';

  export let data: PageData;

  type MapPoint = {
    id: string;
    title: string;
    lat: number;
    lon: number;
  };

  const markersData = (data.nodes || []).map((n) => ({
    id: n.id,
    title: n.title,
    lat: n.location.lat,
    lon: n.location.lon
  })) satisfies MapPoint[];

  let mapContainer: HTMLDivElement | null = null;
  let map: MapLibreMap | null = null;

  let leftOpen = data.leftOpen ?? drawerQueryDefaults.l;     // linke Spalte (Webrat/Nähstübchen)
  let rightOpen = data.rightOpen ?? drawerQueryDefaults.r;   // Filter / Info
  let topOpen = data.topOpen ?? drawerQueryDefaults.t;       // Gewebekonto

  let selected: MapPoint | null = null;
  const markerCleanupFns: Array<() => void> = [];

  type DrawerInstance = InstanceType<typeof Drawer> & {
    setOpener?: (el: HTMLElement | null) => void;
    focus?: () => void;
  };
  let rightDrawerRef: DrawerInstance | null = null;
  let topDrawerRef: DrawerInstance | null = null;
  let openerButtons: {
    left: HTMLButtonElement | null;
    right: HTMLButtonElement | null;
    top: HTMLButtonElement | null;
  } = { left: null, right: null, top: null };

  let showEdges = false;

  function setQuery(next: Partial<Record<DrawerKey, boolean>>) {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    (['l', 'r', 't'] as const).forEach((key) => {
      const value = next[key];
      if (value !== undefined) {
        writeDrawerParam(url.searchParams, key, value);
      }
    });
    history.replaceState(history.state, '', url);
  }

  function syncFromLocation() {
    if (typeof window === 'undefined') return;
    const q = new URLSearchParams(window.location.search);
    leftOpen = readDrawerParam(q, 'l');
    rightOpen = readDrawerParam(q, 'r');
    if (!rightOpen) {
      selected = null;
    }
    topOpen = readDrawerParam(q, 't');
  }

  function setLeftOpen(next: boolean) {
    if (leftOpen === next) return;
    leftOpen = next;
    setQuery({ l: leftOpen });
  }

  function toggleLeft() {
    setLeftOpen(!leftOpen);
  }

  function setRightOpen(next: boolean) {
    if (rightOpen === next) return;
    rightOpen = next;
    if (!rightOpen) {
      selected = null;
    }
    setQuery({ r: rightOpen });
  }

  function toggleRight() {
    setRightOpen(!rightOpen);
  }

  function setTopOpen(next: boolean) {
    if (topOpen === next) return;
    topOpen = next;
    setQuery({ t: topOpen });
  }

  function toggleTop() {
    setTopOpen(!topOpen);
  }

  type SwipeIntent =
    | 'open-left'
    | 'close-left'
    | 'open-right'
    | 'close-right'
    | 'open-top'
    | 'close-top';

  type SwipeState = {
    pointerId: number;
    intent: SwipeIntent;
    startX: number;
    startY: number;
  } | null;

  let swipeState: SwipeState = null;

  function startSwipe(e: PointerEvent, intent: SwipeIntent) {
    const allowMouse = (window as any).__E2E__ === true;
    if (e.pointerType !== 'touch' && e.pointerType !== 'pen' && !allowMouse) return;

    if (
      (intent === 'open-left' && leftOpen) ||
      (intent === 'close-left' && !leftOpen) ||
      (intent === 'open-right' && rightOpen) ||
      (intent === 'close-right' && !rightOpen) ||
      (intent === 'open-top' && topOpen) ||
      (intent === 'close-top' && !topOpen)
    ) {
      return;
    }

    swipeState = {
      pointerId: e.pointerId,
      intent,
      startX: e.clientX,
      startY: e.clientY
    };
  }

  function finishSwipe(e: PointerEvent) {
    if (!swipeState || swipeState.pointerId !== e.pointerId) {
      return;
    }

    const dx = e.clientX - swipeState.startX;
    const dy = e.clientY - swipeState.startY;
    const absX = Math.abs(dx);
    const absY = Math.abs(dy);
    const threshold = 60;
    const { intent } = swipeState;
    
    // Clear swipeState immediately to prevent duplicate processing
    swipeState = null;

    switch (intent) {
      case 'open-left':
        if (!leftOpen && dx > threshold && absX > absY) {
          setLeftOpen(true);
        }
        break;
      case 'close-left':
        if (leftOpen && -dx > threshold && absX > absY) {
          setLeftOpen(false);
        }
        break;
      case 'open-right':
        if (!rightOpen && -dx > threshold && absX > absY) {
          setRightOpen(true);
        }
        break;
      case 'close-right':
        if (rightOpen && dx > threshold && absX > absY) {
          setRightOpen(false);
        }
        break;
      case 'open-top':
        if (!topOpen && dy > threshold && absY > absX) {
          setTopOpen(true);
        }
        break;
      case 'close-top':
        if (topOpen && -dy > threshold && absY > absX) {
          setTopOpen(false);
        }
        break;
    }
  }

  function cancelSwipe(e: PointerEvent) {
    if (swipeState && swipeState.pointerId === e.pointerId) {
      swipeState = null;
    }
  }

  function handleDrawerPointerDown(event: Event, intent: SwipeIntent) {
    if (event instanceof PointerEvent) {
      startSwipe(event, intent);
    }
  }



  function handleOpeners(
    event: CustomEvent<{
      left: HTMLButtonElement | null;
      right: HTMLButtonElement | null;
      top: HTMLButtonElement | null;
    }>
  ) {
    openerButtons = event.detail;
  }

  $: if (rightDrawerRef) {
    rightDrawerRef.setOpener?.(openerButtons.right ?? null);
  }
  $: if (topDrawerRef) {
    topDrawerRef.setOpener?.(openerButtons.top ?? null);
  }

  let keyHandler: ((e: KeyboardEvent) => void) | null = null;
  let popHandler: ((event: PopStateEvent) => void) | null = null;
  onMount(() => {
    const pointerUp = (event: PointerEvent) => finishSwipe(event);
    const pointerCancel = (event: PointerEvent) => cancelSwipe(event);
    window.addEventListener('pointerup', pointerUp);
    window.addEventListener('pointercancel', pointerCancel);

    syncFromLocation();
    popHandler = () => syncFromLocation();
    window.addEventListener('popstate', popHandler);

    keyHandler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (topOpen) {
          setTopOpen(false);
          return;
        }
        if (rightOpen) {
          setRightOpen(false);
          return;
        }
        if (leftOpen) {
          setLeftOpen(false);
          return;
        }
      }
      if (e.key === '[') toggleLeft();
      if (e.key === ']') toggleRight();
      if (e.altKey && (e.key === 'g' || e.key === 'G')) toggleTop();
    };
    window.addEventListener('keydown', keyHandler);

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

      markerCleanupFns.forEach((fn) => fn());
      markerCleanupFns.length = 0;

      for (const item of markersData) {
        const element = document.createElement('button');
        element.type = 'button';
        element.className = 'map-marker';
        element.setAttribute('aria-label', item.title);
        element.title = item.title;
        const handleClick = async () => {
          selected = item;
          setRightOpen(true);
          await tick();
          if (rightDrawerRef && typeof rightDrawerRef.focus === 'function') {
            // Fokus gezielt auf den Info-Drawer legen, sobald er sichtbar ist.
            rightDrawerRef.focus();
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
    })();

    return () => {
      window.removeEventListener('pointerup', pointerUp);
      window.removeEventListener('pointercancel', pointerCancel);
      if (keyHandler) window.removeEventListener('keydown', keyHandler);
      if (popHandler) window.removeEventListener('popstate', popHandler);
    };
  });
  onDestroy(() => {
    if (keyHandler) window.removeEventListener('keydown', keyHandler);
    if (popHandler) window.removeEventListener('popstate', popHandler);
    if (map && typeof map.remove === 'function') map.remove();
    markerCleanupFns.forEach((fn) => fn());
    markerCleanupFns.length = 0;
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
  /* Swipe-Edge-Zonen über Tokens (OS-Gesten-freundlich) */
  .edge{ position:absolute; z-index:29; }
  .edge.left{ left:var(--edge-inset-x); top:80px; bottom:80px; width:var(--edge-left-width); touch-action: pan-y; }
  .edge.right{ right:var(--edge-inset-x); top:80px; bottom:80px; width:var(--edge-right-width); touch-action: pan-y; }
  .edge.top{ left:var(--edge-inset-x); right:var(--edge-inset-x); top:var(--edge-inset-top); height:var(--edge-top-height); touch-action: pan-y; }
  .edgeHit{ position:absolute; inset:0; }
  /* Linke Spalte: oben Webrat, unten Nähstübchen (hälftig) */
  .leftStack{
    position:absolute;
    left: var(--drawer-gap);
    top:calc(var(--toolbar-offset) + env(safe-area-inset-top));
    bottom:calc(var(--toolbar-offset) + env(safe-area-inset-bottom));
    width:var(--drawer-width);
    z-index:26;
    display:grid; grid-template-rows: 1fr 1fr; gap:var(--drawer-gap);
    transform: translateX(calc(-1 * var(--drawer-width) - var(--drawer-slide-offset)));
    transition: transform .18s ease;
    pointer-events: none;
  }
  .leftStack.open{ transform:none; pointer-events: auto; }
  .panel{
    background:var(--panel); border:1px solid var(--panel-border); border-radius: var(--radius);
    box-shadow: var(--shadow); color:var(--text); padding:var(--drawer-gap); overflow:auto;
  }
  .panel h3{ margin:0 0 8px 0; font-size:14px; color:var(--muted); letter-spacing:.2px; }
  .muted{ color:var(--muted); font-size:13px; }
  .infoPanel{ margin-bottom: var(--drawer-gap); }
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
  }
  #map :global(.map-marker:focus-visible){
    outline:2px solid var(--fg);
    outline-offset:2px;
  }
  .layerToggles{
    position:absolute;
    right:var(--drawer-gap);
    top:calc(var(--toolbar-offset) + env(safe-area-inset-top) + 8px);
    display:flex;
    gap:8px;
    align-items:center;
    z-index:28;
    background:rgba(0,0,0,0.4);
    backdrop-filter: blur(8px);
    padding:6px 8px;
    border-radius:12px;
    border:1px solid var(--panel-border);
    box-shadow: var(--shadow);
  }
  .layerToggles .toggle{
    appearance:none;
    border:1px solid var(--panel-border);
    background:var(--panel);
    color:var(--text);
    border-radius:10px;
    padding:6px 10px;
    cursor:pointer;
    box-shadow: var(--shadow);
  }
  .layerToggles .toggle[aria-pressed="true"]{
    background:var(--accent, #ff8c42);
    border-color:var(--accent, #ff8c42);
    color:var(--bg);
  }
  .layerToggles .toggle:disabled{
    opacity:0.65;
    cursor:not-allowed;
  }
  .layerToggles a{
    color:var(--text);
    text-decoration:underline;
    font-size:14px;
  }
  @media (max-width: 900px){
    .leftStack{ --drawer-width: 320px; }
    .layerToggles{ left:var(--drawer-gap); right:auto; flex-wrap:wrap; }
  }
  @media (max-width: 380px){
    .leftStack{ --drawer-width: 300px; }
  }
  @media (prefers-reduced-motion: reduce){
    .leftStack{ transition: none; }
  }
</style>

<main class="shell">
  <TopBar
    onToggleLeft={toggleLeft}
    onToggleRight={toggleRight}
    onToggleTop={toggleTop}
    {leftOpen}
    {rightOpen}
    {topOpen}
    on:openers={handleOpeners}
  />

  <!-- Linke Spalte: Webrat / Nähstübchen -->
  <div
    id="left-stack"
    class="leftStack"
    class:open={leftOpen}
    aria-hidden={!leftOpen ? 'true' : 'false'}
    on:pointerdown={(event) => handleDrawerPointerDown(event, 'close-left')}
  >
    <div class="panel">
      <h3>Webrat</h3>
      <div class="muted">Beratung, Anträge, Matrix (Stub)</div>
    </div>
    <div class="panel">
      <h3>Nähstübchen</h3>
      <div class="muted">Ideen, Entwürfe, Skizzen (Stub)</div>
    </div>
  </div>

  <!-- Rechter Drawer: Suche/Filter -->
  <Drawer
    bind:this={rightDrawerRef}
    id="filter-drawer"
    title="Suche & Filter"
    side="right"
    open={rightOpen}
    on:pointerdown={(event) => handleDrawerPointerDown(event, 'close-right')}
  >
    {#if selected}
      <div class="panel infoPanel">
        <strong>{selected.title}</strong>
        <div class="muted">Kurzbeschreibung folgt (Stub)</div>
        <div class="muted">Weitere Details folgen (Stub)</div>
      </div>
    {/if}
    <div class="panel" style="padding:8px;">
      <div class="muted">Typ · Zeit · H3 · Delegation · Radius (Stub)</div>
    </div>
  </Drawer>

  <!-- Top Drawer: Gewebekonto -->
  <Drawer
    bind:this={topDrawerRef}
    id="account-drawer"
    title="Gewebekonto"
    side="top"
    open={topOpen}
    role="dialog"
    on:pointerdown={(event) => handleDrawerPointerDown(event, 'close-top')}
  >
    <div class="panel" style="padding:8px;">
      <div class="muted">Saldo / Delegationen / Verbindlichkeiten (Stub)</div>
    </div>
  </Drawer>

  <!-- Karte -->
  <div id="map" bind:this={mapContainer}></div>

  <div class="edge left" role="presentation" on:pointerdown={(event) => startSwipe(event, 'open-left')}>
    <div class="edgeHit"></div>
  </div>
  <div class="edge right" role="presentation" on:pointerdown={(event) => startSwipe(event, 'open-right')}>
    <div class="edgeHit"></div>
  </div>
  <div class="edge top" role="presentation" on:pointerdown={(event) => handleDrawerPointerDown(event, 'open-top')}>
    <div class="edgeHit"></div>
  </div>

  <div class="layerToggles" role="toolbar" aria-label="Struktur-Overlay">
    <button class="toggle" type="button" disabled>
      Strukturknoten
    </button>
    <button
      class="toggle"
      type="button"
      aria-pressed={showEdges}
      on:click={() => (showEdges = !showEdges)}
    >
      Fäden
    </button>
    <a href="/archive/">Archiv ansehen</a>
  </div>

  <!-- Zeitleiste -->
  <TimelineDock />
</main>
