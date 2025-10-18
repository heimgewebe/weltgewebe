<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import '$lib/styles/tokens.css';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import TopBar from '$lib/components/TopBar.svelte';
  import Drawer from '$lib/components/Drawer.svelte';
  import TimelineDock from '$lib/components/TimelineDock.svelte';

  let mapContainer: HTMLDivElement | null = null;
  let map: any = null;

  let leftOpen = true;     // linke Spalte (Webrat + Nähstübchen)
  let rightOpen = false;   // Filter
  let topOpen = false;     // Gewebekonto-Drawer

  function toggleLeft(){ leftOpen = !leftOpen; }
  function toggleRight(){ rightOpen = !rightOpen; }
  function toggleTop(){ topOpen = !topOpen; }

  let keyHandler: ((e: KeyboardEvent) => void) | null = null;
  onMount(async () => {
    const maplibregl = await import('maplibre-gl');
    // Hamburg-Hamm grob: 10.05, 53.55 — Zoom 13
    map = new maplibregl.Map({
      container: mapContainer!,
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
    height:calc(100dvh - env(safe-area-inset-top) - env(safe-area-inset-bottom));
    width:100vw;
    overflow:hidden;
    background:var(--bg);
    color:var(--text);
    padding-top:0;
    padding-top: env(safe-area-inset-top);
    padding-bottom:0;
    padding-bottom: env(safe-area-inset-bottom);
  }
  #map{ position:absolute; inset:0; }
  #map :global(canvas){ filter: grayscale(0.2) saturate(0.75) brightness(1.03) contrast(0.95); }
  /* Linke Spalte: oben Webrat, unten Nähstübchen (hälftig) */
  .leftStack{
    position:absolute;
    left:12px;
    top:64px;
    top:calc(64px + env(safe-area-inset-top));
    bottom:64px;
    bottom:calc(64px + env(safe-area-inset-bottom));
    width:360px;
    z-index:26;
    display:grid; grid-template-rows: 1fr 1fr; gap:12px;
    transform: translateX(-380px); transition: transform .18s ease;
  }
  .leftStack.open{ transform:none; }
  .panel{
    background:var(--panel); border:1px solid var(--panel-border); border-radius: var(--radius);
    box-shadow: var(--shadow); color:var(--text); padding:12px; overflow:auto;
  }
  .panel h3{ margin:0 0 8px 0; font-size:14px; color:var(--muted); letter-spacing:.2px; }
  .muted{ color:var(--muted); font-size:13px; }
  @media (max-width: 900px){
    .leftStack{ width:320px; }
  }
  @media (max-width: 380px){
    .leftStack{ width:300px; transform: translateX(-320px); }
  }
  @media (prefers-reduced-motion: reduce){
    .leftStack{ transition: none; }
  }
</style>

<div class="shell">
  <TopBar {onToggleLeft} {onToggleRight} {onToggleTop}/>

  <!-- Linke Spalte: Webrat / Nähstübchen -->
  <div class="leftStack {leftOpen ? 'open' : ''}">
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
  <Drawer title="Suche & Filter" side="right" open={rightOpen}>
    <div class="panel" style="padding:8px;">
      <div class="muted">Typ · Zeit · H3 · Delegation · Radius (Stub)</div>
    </div>
  </Drawer>

  <!-- Top Drawer: Gewebekonto -->
  <Drawer title="Gewebekonto" side="top" open={topOpen}>
    <div class="panel" style="padding:8px;">
      <div class="muted">Saldo / Delegationen / Verbindlichkeiten (Stub)</div>
    </div>
  </Drawer>

  <!-- Karte -->
  <div id="map" bind:this={mapContainer}></div>

  <!-- Zeitleiste -->
  <TimelineDock />
</div>

