<script lang="ts">
  import type { ControlPosition } from "maplibre-gl";
  import { onDestroy } from "svelte";
  import { get } from "svelte/store";
  import { useMapContext } from "./context";

  interface Props {
    position?: ControlPosition;
    visualizePitch?: boolean;
    showCompass?: boolean;
    showZoom?: boolean;
  }

  let {
    position = "top-right",
    visualizePitch = true,
    showCompass = true,
    showZoom = true,
  }: Props = $props();

  const context = useMapContext();

  let control: import("maplibre-gl").NavigationControl | null = null;
  let signature: string | null = null;
  let lastMap: import("maplibre-gl").Map | null = null;

  const unsubscribe = context.map.subscribe((map) => {
    ensureControl(map);
  });

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

    const nextSignature = JSON.stringify({
      position,
      visualizePitch,
      showCompass,
      showZoom,
    });
    if (control && signature === nextSignature && lastMap === map) {
      return;
    }

    if (control && lastMap) {
      lastMap.removeControl(control);
      control = null;
    }

    control = new context.maplibre.NavigationControl({
      visualizePitch,
      showCompass,
      showZoom,
    });
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
  $effect.pre(() => {
    ensureControl(get(context.map));
  });
</script>
