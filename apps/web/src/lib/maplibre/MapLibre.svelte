<script lang="ts">
  import { createEventDispatcher, onMount } from "svelte";
  import "maplibre-gl/dist/maplibre-gl.css";
  import type { FitBoundsOptions, LngLatBoundsLike, LngLatLike, MapOptions } from "maplibre-gl";
  import { initMapContext } from "./context";

  const dispatch = createEventDispatcher();
  const context = initMapContext();

  export let style: string;
  export let center: LngLatLike | undefined;
  export let zoom: number | undefined;
  export let minZoom: number | undefined;
  export let maxZoom: number | undefined;
  export let bounds: LngLatBoundsLike | undefined;
  export let fitBoundsOptions: FitBoundsOptions | undefined;
  export let attributionControl = false;
  export let interactive: boolean | undefined;
  export let options: Partial<MapOptions> = {};

  let container: HTMLDivElement | undefined;
  let map: import("maplibre-gl").Map | null = null;
  let containerProps: Record<string, unknown> = {};

  $: ({ style: _omitStyle, ...containerProps } = $$restProps);

  onMount(async () => {
    const maplibreModule = await import("maplibre-gl");
    context.maplibre = maplibreModule;

    if (!container) {
      return;
    }

    const initialOptions: MapOptions = {
      container,
      style,
      attributionControl,
      ...options
    } as MapOptions;

    if (center) {
      initialOptions.center = normalizeLngLat(center);
    }

    if (zoom !== undefined) {
      initialOptions.zoom = zoom;
    }

    if (minZoom !== undefined) {
      initialOptions.minZoom = minZoom;
    }

    if (maxZoom !== undefined) {
      initialOptions.maxZoom = maxZoom;
    }

    if (interactive !== undefined) {
      initialOptions.interactive = interactive;
    }

    map = new maplibreModule.Map(initialOptions);
    context.map.set(map);

    map.on("load", () => dispatch("load", { map }));
    map.on("error", (event) => dispatch("error", event));

    if (bounds) {
      map.fitBounds(bounds, fitBoundsOptions);
    }

    return () => {
      map?.remove();
      map = null;
      context.map.set(null);
      context.maplibre = null;
    };
  });

  $: if (map && center) {
    map.setCenter(normalizeLngLat(center));
  }

  $: if (map && zoom !== undefined) {
    map.setZoom(zoom);
  }

  $: if (map && bounds) {
    map.fitBounds(bounds, fitBoundsOptions);
  }

  function normalizeLngLat(value: LngLatLike): LngLatLike {
    if (Array.isArray(value)) {
      return value;
    }

    return [value.lng, value.lat];
  }
</script>

<div bind:this={container} {...containerProps}>
  <slot />
</div>
