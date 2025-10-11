<script lang="ts">
  import AppShell from "$lib/components/AppShell.svelte";
  import DrawerLeft from "$lib/components/DrawerLeft.svelte";
  import DrawerRight from "$lib/components/DrawerRight.svelte";
  import Legend from "$lib/components/Legend.svelte";
  import { MapLibre, Marker, NavigationControl, ScaleControl } from "svelte-maplibre-gl";

  const center = { lng: 10.0, lat: 53.55 };
  const ui = {
    timeCursor: "T-0",
    layers: { strukturknoten: true, faeden: false },
    drawers: { left: true, right: true }
  } as const;

  const strukturknoten = [
    { id: "webrat", name: "Webrat", lng: 10.01, lat: 53.56 },
    { id: "naehstuebchen", name: "Nähstübchen", lng: 9.99, lat: 53.55 },
    { id: "gewebekonto", name: "Gewebekonto", lng: 10.03, lat: 53.54 },
    { id: "ron", name: "RoN", lng: 10.02, lat: 53.545 }
  ];
</script>

<AppShell timeCursor={ui.timeCursor} title="Weltgewebe – Click-Dummy">
  <div slot="topright" class="row" aria-label="Layer-Stub">
    <button class="btn" type="button" aria-pressed={ui.layers.strukturknoten} disabled>Strukturknoten</button>
    <button class="btn" type="button" aria-pressed={ui.layers.faeden} disabled>Fäden</button>
  </div>

  <div class="map-wrapper">
    <MapLibre
      style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"
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
  </div>

  {#if ui.drawers.left}
    <DrawerLeft />
  {/if}
  {#if ui.drawers.right}
    <DrawerRight />
  {/if}
  <Legend />
</AppShell>

<style>
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
  .map-wrapper {
    position: absolute;
    inset: 0;
  }
</style>
