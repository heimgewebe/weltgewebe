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
