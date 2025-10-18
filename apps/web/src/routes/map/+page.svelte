<script lang="ts">
  import AppShell from "$lib/components/AppShell.svelte";
  import DrawerLeft from "$lib/components/DrawerLeft.svelte";
  import DrawerRight from "$lib/components/DrawerRight.svelte";
  import GewebekontoWidget from "$lib/components/GewebekontoWidget.svelte";
  import Legend from "$lib/components/Legend.svelte";
  import { onMount } from "svelte";
  import { MapLibre, Marker, NavigationControl, ScaleControl } from "svelte-maplibre-gl";

  const center = { lng: 10.0, lat: 53.55 };
  const ui = {
    timeCursor: "T-0",
    layers: { strukturknoten: true, faeden: false },
    drawers: { left: true, right: true }
  } as const;

  // TODO(Gate B, tracked in policies/roadmap.md): Replace external Carto basemap with self-hosted tiles and fonts.
  const mapStyleUrl = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";

  let mounted = false;
  onMount(() => {
    mounted = true;
  });

  const strukturknoten = [
    { id: "webrat", name: "Webrat", lng: 10.01, lat: 53.56 },
    { id: "naehstuebchen", name: "Nähstübchen", lng: 9.99, lat: 53.55 },
    { id: "gewebekonto", name: "Gewebekonto", lng: 10.03, lat: 53.54 },
    { id: "ron", name: "RoN", lng: 10.02, lat: 53.545 }
  ];
</script>

<AppShell timeCursor={ui.timeCursor} title="Weltgewebe – Click-Dummy">
  <GewebekontoWidget slot="gewebekonto" note="Nur UI – Buchungen folgen in Gate B" />

  <div slot="topright" class="layer-toggle" aria-label="Layer-Stub">
    <button class="btn" type="button" aria-pressed={ui.layers.strukturknoten} disabled>Strukturknoten</button>
    <button class="btn" type="button" aria-pressed={ui.layers.faeden} disabled>Fäden</button>
  </div>

  <div class="map-stage">
    <div class="map-canvas">
      {#if mounted}
        <MapLibre
          class="maplibre"
          style={mapStyleUrl}
          center={center}
          zoom={12}
          attributionControl
          on:error={(event) => console.warn("MapLibre error", event.detail)}
        >
          <NavigationControl position="top-left" />
          <ScaleControl />

          {#if ui.layers.strukturknoten}
            {#each strukturknoten as k}
              <Marker lngLat={{ lng: k.lng, lat: k.lat }} anchor="bottom" draggable={false} aria-label={k.name}>
                <div class="badge" title={k.name}>{k.name}</div>
              </Marker>
            {/each}
          {/if}
        </MapLibre>
      {:else}
        <div
          class="maplibre maplibre--placeholder"
          role="img"
          aria-label="Kartenplatzhalter: Interaktive Karte lädt nach dem Initialisieren."
        ></div>
      {/if}
    </div>

    {#if ui.drawers.left}
      <DrawerLeft />
    {/if}
    {#if ui.drawers.right}
      <DrawerRight />
    {/if}
    <Legend />
  </div>
</AppShell>

<style>
  .layer-toggle {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .layer-toggle :global(.btn:focus-visible) {
    outline: 2px solid rgba(112, 184, 255, 0.9);
    outline-offset: 2px;
    border-radius: 999px;
  }

  @media (min-width: 42rem) {
    .layer-toggle {
      justify-content: flex-end;
    }
  }

  .map-stage {
    position: relative;
    height: 100%;
    isolation: isolate;
  }

  .map-canvas {
    position: absolute;
    inset: 0;
    overflow: hidden;
  }

  .maplibre {
    width: 100%;
    height: 100%;
  }

  .maplibre--placeholder {
    background: linear-gradient(135deg, rgba(38, 50, 64, 0.65), rgba(16, 24, 33, 0.65));
  }

  :global(.maplibregl-ctrl) {
    color: var(--fg);
  }

  :global(.maplibregl-ctrl button) {
    background: #101821;
    border-color: #263240;
  }

  :global(.maplibregl-ctrl button:hover) {
    background: #121e29;
  }

  :global(.maplibregl-ctrl-group) {
    box-shadow: none;
  }
</style>
