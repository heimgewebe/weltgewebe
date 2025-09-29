<script lang="ts">
  import { browser } from "$app/environment";
  import { onDestroy, onMount } from "svelte";

  let mapHost: HTMLDivElement | null = null;
  let mapReady = false;
  let loading = false;
  let error: string | null = null;
  let map: import("maplibre-gl").Map | null = null;
  let mounted = false;

  type MapLibreModule = typeof import("maplibre-gl");

  function canInitialise(container: HTMLDivElement | null): container is HTMLDivElement {
    if (typeof window === "undefined") return false;
    if (!container || !container.isConnected) return false;
    const rect = container.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  async function enableMap() {
    if (!browser || loading || mapReady || !mounted) return;

    if (!canInitialise(mapHost)) {
      error = "Karte konnte nicht geladen werden.";
      return;
    }

    const container = mapHost;
    loading = true;
    error = null;

    try {
      const modulePromise = import("maplibre-gl");
      await import("maplibre-gl/dist/maplibre-gl.css");
      const mapModule = await modulePromise;

      const maplibregl = (mapModule as MapLibreModule & { default?: MapLibreModule }).default ??
        (mapModule as MapLibreModule);

      map = new maplibregl.Map({
        container,
        style: "https://demotiles.maplibre.org/style.json",
        center: [10.0, 53.55], // grob HH
        zoom: 10
      });
      map.scrollZoom.disable();

      const handleLoad = () => {
        loading = false;
        mapReady = true;
        map?.off("error", handleError);
      };

      const handleError = (event: { error?: unknown }) => {
        console.error(event?.error ?? event);
        error = "Karte konnte nicht geladen werden.";
        loading = false;
        mapReady = false;
        map?.off("load", handleLoad);
        map?.remove();
        map = null;
      };

      map.once("load", handleLoad);
      map.on("error", handleError);
    } catch (e) {
      error = "Karte konnte nicht geladen werden.";
      console.error(e);
      loading = false;
      mapReady = false;
      map?.remove();
      map = null;
    }
  }

  onMount(() => {
    mounted = true;
  });

  onDestroy(() => {
    map?.remove();
    map = null;
    mounted = false;
    mapReady = false;
    loading = false;
  });
</script>

<div style="position:fixed;inset:0;">
  <!-- Map-Fläche -->
  <div
    bind:this={mapHost}
    role="application"
    aria-label="Interactive Map"
    style="position:absolute;inset:0;background:#eef"
  ></div>

  <!-- Kleiner Drawer-Stub -->
  <aside style="position:absolute;left:1rem;top:1rem;background:#fff;padding:.75rem .9rem;border-radius:.5rem;box-shadow:0 2px 8px #0001;">
    <strong>Webrat</strong> · <em>Nähstübchen</em>
    <div style="margin-top:.5rem;">
      <button on:click={enableMap} disabled={mapReady || loading}>
        {mapReady ? "Karte aktiv" : (loading ? "Lade Karte…" : "Karte aktivieren")}
      </button>
      {#if error}<span role="alert" style="color:#b00;margin-left:.5rem;">{error}</span>{/if}
    </div>
  </aside>

  <!-- Timeline-Stub -->
  <footer style="position:absolute;left:0;right:0;bottom:0;background:#ffffffcc;padding:.5rem 1rem;border-top:1px solid #eee;">
    Timeline (stub)
  </footer>
</div>
