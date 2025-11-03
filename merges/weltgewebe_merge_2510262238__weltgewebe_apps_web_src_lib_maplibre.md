### 📄 weltgewebe/apps/web/src/lib/maplibre/MapLibre.svelte

**Größe:** 2 KB | **md5:** `c9b32f356f200f0927f72fa926e74c14`

```svelte
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
```

### 📄 weltgewebe/apps/web/src/lib/maplibre/Marker.svelte

**Größe:** 2 KB | **md5:** `68831b8c0a3634a486d5b537643f3517`

```svelte
<script lang="ts">
  import type { Anchor, LngLatLike, MarkerOptions, PointLike } from "maplibre-gl";
  import { onDestroy } from "svelte";
  import { get } from "svelte/store";
  import { useMapContext } from "./context";

  export let lngLat: LngLatLike;
  export let anchor: Anchor = "center";
  export let draggable = false;
  export let offset: PointLike | undefined;

  const context = useMapContext();

  let element: HTMLDivElement | undefined;
  let marker: import("maplibre-gl").Marker | null = null;
  let markerProps: Record<string, unknown> = {};
  let currentAnchor: Anchor = anchor;

  $: markerProps = $$restProps;

  const unsubscribe = context.map.subscribe((map) => {
    recreateMarker(map);
  });

  $: if (marker && lngLat) {
    marker.setLngLat(lngLat);
  }

  $: if (marker) {
    marker.setDraggable(draggable);
  }

  $: if (marker && offset !== undefined) {
    marker.setOffset(offset);
  }

  $: if (marker && anchor !== currentAnchor) {
    recreateMarker(get(context.map));
  }

  function recreateMarker(map: import("maplibre-gl").Map | null) {
    if (marker) {
      marker.remove();
      marker = null;
    }

    if (!map || !context.maplibre || !element) {
      return;
    }

    const options: MarkerOptions = {
      element,
      anchor,
      draggable
    };

    if (offset !== undefined) {
      options.offset = offset;
    }

    marker = new context.maplibre.Marker(options).setLngLat(lngLat).addTo(map);
    currentAnchor = anchor;
  }

  onDestroy(() => {
    unsubscribe();

    if (marker) {
      marker.remove();
      marker = null;
    }
  });
</script>

<div bind:this={element} {...markerProps}>
  <slot />
</div>
```

### 📄 weltgewebe/apps/web/src/lib/maplibre/NavigationControl.svelte

**Größe:** 2 KB | **md5:** `ddacf371d91ee0ea654400dfdc70dcc4`

```svelte
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
```

### 📄 weltgewebe/apps/web/src/lib/maplibre/ScaleControl.svelte

**Größe:** 2 KB | **md5:** `37e23429d60fa65d8c3c42b3ecb0a59d`

```svelte
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
```

### 📄 weltgewebe/apps/web/src/lib/maplibre/context.ts

**Größe:** 815 B | **md5:** `8b578cf40bcb3da406f2f04ca730f297`

```typescript
import type * as maplibregl from "maplibre-gl";
import { getContext, setContext } from "svelte";
import { writable, type Writable } from "svelte/store";

export const MAP_CONTEXT_KEY = Symbol("maplibre-context");

export type MapContextValue = {
  map: Writable<maplibregl.Map | null>;
  maplibre: typeof import("maplibre-gl") | null;
};

export function initMapContext(): MapContextValue {
  const value: MapContextValue = {
    map: writable<maplibregl.Map | null>(null),
    maplibre: null
  };

  setContext(MAP_CONTEXT_KEY, value);
  return value;
}

export function useMapContext(): MapContextValue {
  const context = getContext<MapContextValue | undefined>(MAP_CONTEXT_KEY);

  if (!context) {
    throw new Error("MapLibre components must be used inside a <MapLibre> container.");
  }

  return context;
}
```

### 📄 weltgewebe/apps/web/src/lib/maplibre/index.ts

**Größe:** 250 B | **md5:** `1d16218a92d62836dab4f0810c39f1cf`

```typescript
export { default as MapLibre } from "./MapLibre.svelte";
export { default as Marker } from "./Marker.svelte";
export { default as NavigationControl } from "./NavigationControl.svelte";
export { default as ScaleControl } from "./ScaleControl.svelte";
```

