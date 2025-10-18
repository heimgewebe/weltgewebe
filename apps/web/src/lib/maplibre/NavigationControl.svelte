<script lang="ts">
  import type { ControlPosition } from "maplibre-gl";
  import { onDestroy } from "svelte";
  import { get } from "svelte/store";
  import { useMapContext } from "./context";

  export let position: ControlPosition = "top-right";
  export let visualizePitch = true;
  export let showCompass = true;
  export let showZoom = true;

  const context = useMapContext();

  let control: import("maplibre-gl").NavigationControl | null = null;
  let signature: string | null = null;
  let lastMap: import("maplibre-gl").Map | null = null;

  const unsubscribe = context.map.subscribe((map) => {
    ensureControl(map);
  });

  $: ensureControl(get(context.map));

  function ensureControl(map: import("maplibre-gl").Map | null) {
    if (!map || !context.maplibre) {
      if (control && lastMap) {
        lastMap.removeControl(control);
        control = null;
      }
      signature = null;
      lastMap = map;
      return;
    }

    const nextSignature = JSON.stringify({ position, visualizePitch, showCompass, showZoom });
    if (control && signature === nextSignature && lastMap === map) {
      return;
    }

    if (control && lastMap) {
      lastMap.removeControl(control);
      control = null;
    }

    control = new context.maplibre.NavigationControl({ visualizePitch, showCompass, showZoom });
    map.addControl(control, position);
    signature = nextSignature;
    lastMap = map;
  }

  onDestroy(() => {
    unsubscribe();
    const map = get(context.map);
    if (control && map) {
      map.removeControl(control);
    } else if (control && lastMap) {
      lastMap.removeControl(control);
    }
    control = null;
    lastMap = null;
  });
</script>
