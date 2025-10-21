<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { get } from 'svelte/store';
  import '$lib/styles/tokens.css';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import type { Map as MapLibreMap } from 'maplibre-gl';
  import TopBar from '$lib/components/TopBar.svelte';
  import Drawer from '$lib/components/Drawer.svelte';
  import TimelineDock from '$lib/components/TimelineDock.svelte';

  let mapContainer: HTMLDivElement | null = null;
  let map: MapLibreMap | null = null;

  let leftOpen = true;     // linke Spalte (Webrat/Nähstübchen)
  let rightOpen = false;   // Filter
  let topOpen = false;     // Gewebekonto

  const defaultQueryState = { l: leftOpen, r: rightOpen, t: topOpen } as const;

  function setQuery(next: { l?: boolean; r?: boolean; t?: boolean }) {
    const { pathname, search } = get(page).url;
    const p = new URLSearchParams(search);
    if (next.l !== undefined) {
      if (next.l === defaultQueryState.l) {
        p.delete('l');
      } else {
        p.set('l', next.l ? '1' : '0');
      }
    }
    if (next.r !== undefined) {
      if (next.r === defaultQueryState.r) {
        p.delete('r');
      } else {
        p.set('r', next.r ? '1' : '0');
      }
    }
    if (next.t !== undefined) {
      if (next.t === defaultQueryState.t) {
        p.delete('t');
      } else {
        p.set('t', next.t ? '1' : '0');
      }
    }
    const query = p.toString();
    const target = query ? `${pathname}?${query}` : pathname;
    // noScroll/replaceState damit der Verlauf sauber bleibt
    goto(target, { replaceState: true, noScroll: true, keepfocus: true });
  }

  function toggleLeft(){ leftOpen = !leftOpen; setQuery({ l: leftOpen }); }
  function toggleRight(){ rightOpen = !rightOpen; setQuery({ r: rightOpen }); }
  function toggleTop(){ topOpen = !topOpen; setQuery({ t: topOpen }); }

  let keyHandler: ((e: KeyboardEvent) => void) | null = null;
  onMount(async () => {
    // Initial aus URL lesen
    const { search } = get(page).url;
    const q = new URLSearchParams(search);
    leftOpen = q.get('l') ? q.get('l') === '1' : leftOpen;
    rightOpen = q.get('r') ? q.get('r') === '1' : rightOpen;
    topOpen = q.get('t') ? q.get('t') === '1' : topOpen;

    const maplibregl = await import('maplibre-gl');
    const container = mapContainer;
    if (!container) {
      return;
    }
    // Hamburg-Hamm grob: 10.05, 53.55 — Zoom 13
    map = new maplibregl.Map({
      container,
      style: 'https://demotiles.maplibre.org/style.json',
      center: [10.05, 53.55],
      zoom: 13
    });
    map.addControl(new maplibregl.NavigationControl({ showZoom:true }), 'bottom-right');

    keyHandler = (e: KeyboardEvent) => {
      if (e.key === '[') toggleLeft();
      if (e.key === ']') toggleRight();
      if (e.altKey && (e.key === 'g' || e.key === 'G')) toggleTop();
    };
    window.addEventListener('keydown', keyHandler);
  });
  onDestroy(() => {
    if (keyHandler) window.removeEventListener('keydown', keyHandler);
    if (map && typeof map.remove === 'function') map.remove();
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
  }
  .leftStack.open{ transform:none; }
  .panel{
    background:var(--panel); border:1px solid var(--panel-border); border-radius: var(--radius);
    box-shadow: var(--shadow); color:var(--text); padding:var(--drawer-gap); overflow:auto;
  }
  .panel h3{ margin:0 0 8px 0; font-size:14px; color:var(--muted); letter-spacing:.2px; }
  .muted{ color:var(--muted); font-size:13px; }
  @media (max-width: 900px){
    .leftStack{ --drawer-width: 320px; }
  }
  @media (max-width: 380px){
    .leftStack{ --drawer-width: 300px; }
  }
  @media (prefers-reduced-motion: reduce){
    .leftStack{ transition: none; }
  }
</style>

<div class="shell">
  <TopBar
    onToggleLeft={toggleLeft}
    onToggleRight={toggleRight}
    onToggleTop={toggleTop}
    {leftOpen}
    {rightOpen}
    {topOpen}
  />

  <!-- Linke Spalte: Webrat / Nähstübchen -->
  <div
    id="left-stack"
    class="leftStack"
    class:open={leftOpen}
    aria-hidden={!leftOpen}
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
  <Drawer id="filter-drawer" title="Suche & Filter" side="right" open={rightOpen}>
    <div class="panel" style="padding:8px;">
      <div class="muted">Typ · Zeit · H3 · Delegation · Radius (Stub)</div>
    </div>
  </Drawer>

  <!-- Top Drawer: Gewebekonto -->
  <Drawer id="account-drawer" title="Gewebekonto" side="top" open={topOpen}>
    <div class="panel" style="padding:8px;">
      <div class="muted">Saldo / Delegationen / Verbindlichkeiten (Stub)</div>
    </div>
  </Drawer>

  <!-- Karte -->
  <div id="map" bind:this={mapContainer}></div>

  <!-- Zeitleiste -->
  <TimelineDock />
</div>

