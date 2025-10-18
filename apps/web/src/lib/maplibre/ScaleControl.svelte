<script lang="ts">
  import type { ControlPosition } from "maplibre-gl";
  import { onDestroy } from "svelte";
  import { get } from "svelte/store";
  import { useMapContext } from "./context";

  export let position: ControlPosition = "bottom-left";
  export let maxWidth: number | undefined;
  export let unit: "imperial" | "metric" | "nautical" | undefined;

  const context = useMapContext();

  type ScaleControlOptions = ConstructorParameters<typeof import("maplibre-gl").ScaleControl>[0];

  let control: import("maplibre-gl").ScaleControl | null = null;
  let signature: string | null = null;
  let lastMap: import("maplibre-gl").Map | null = null;

  const unsubscribe = context.map.subscribe((map) => {
    ensureControl(map);
  });

  $: ensureControl(get(context.map));

  function ensureControl(map: import("maplibre-gl").Map | null) {
    if (control && lastMap && lastMap !== map) {
      lastMap.removeControl(control);
      control = null;
    }

    if (!map || !context.maplibre) {
      signature = null;
      lastMap = map;
      return;
    }

    const nextSignature = JSON.stringify({ position, maxWidth, unit });
    if (control && signature === nextSignature && lastMap === map) {
      return;
    }

    if (control && lastMap) {
      lastMap.removeControl(control);
      control = null;
    }

    const options: ScaleControlOptions = {};

    if (maxWidth !== undefined) {
      options.maxWidth = maxWidth;
    }

    if (unit) {
      options.unit = unit;
    }

    control = new context.maplibre.ScaleControl(options);
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
