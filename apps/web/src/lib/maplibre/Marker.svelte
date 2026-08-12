<script lang="ts">
  import type { LngLatLike, MarkerOptions, PointLike } from "maplibre-gl";
  import { onDestroy } from "svelte";
  import { get } from "svelte/store";
  import { useMapContext } from "./context";

  type MarkerAnchor = NonNullable<MarkerOptions["anchor"]>;

  interface Props {
    lngLat: LngLatLike;
    anchor?: MarkerAnchor;
    draggable?: boolean;
    offset: PointLike | undefined;
    children?: import("svelte").Snippet;
    [key: string]: any;
  }

  let {
    lngLat,
    anchor = "center",
    draggable = false,
    offset,
    children,
    ...rest
  }: Props = $props();

  const context = useMapContext();

  let element: HTMLDivElement | undefined = $state();
  let marker: import("maplibre-gl").Marker | null = $state(null);
  let markerProps: Record<string, unknown> = $derived(rest);
  let currentAnchor: MarkerAnchor | null = $state(null);

  const unsubscribe = context.map.subscribe((map) => {
    recreateMarker(map);
  });

  onDestroy(unsubscribe);

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
      draggable,
    };

    if (offset !== undefined) {
      options.offset = offset;
    }

    marker = new context.maplibre.Marker(options).setLngLat(lngLat).addTo(map);
    currentAnchor = anchor;
  }

  onDestroy(() => {
    if (marker) {
      marker.remove();
      marker = null;
    }
  });
  $effect(() => {
    if (marker && lngLat) {
      marker.setLngLat(lngLat);
    }
  });
  $effect(() => {
    if (marker) {
      marker.setDraggable(draggable);
    }
  });
  $effect(() => {
    if (marker && offset !== undefined) {
      marker.setOffset(offset);
    }
  });
  $effect(() => {
    if (marker && anchor !== currentAnchor) {
      recreateMarker(get(context.map));
    }
  });
</script>

<div bind:this={element} {...markerProps}>
  {@render children?.()}
</div>
