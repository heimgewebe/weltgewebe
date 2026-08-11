<script lang="ts">
  export let panelOpen = false;
  export let searchOpen = false;
  export let filterOpen = false;
  export let loading = true;
  export let mapElement: HTMLDivElement | null = null;
</script>

<main
  class="shell"
  class:panel-open={panelOpen}
  class:search-open={searchOpen}
  class:filter-open={filterOpen}
>
  <slot />
  <div
    id="map"
    class:panel-open={panelOpen}
    class:search-open={searchOpen}
    class:filter-open={filterOpen}
    class:map-loading={loading}
    bind:this={mapElement}
  ></div>
</main>

<style>
  .shell {
    position: relative;
    height: 100dvh;
    height: calc(
      100dvh - env(safe-area-inset-top) - env(safe-area-inset-bottom)
    );
    width: 100vw;
    overflow: hidden;
    background: var(--bg);
    color: var(--text);
    padding-top: env(safe-area-inset-top);
    padding-bottom: env(safe-area-inset-bottom);
  }
  #map {
    position: absolute;
    inset: 0;
  }
  #map.map-loading {
    opacity: 0;
    pointer-events: none;
  }
  #map :global(canvas) {
    filter: grayscale(0.2) saturate(0.75) brightness(1.03) contrast(0.95);
  }

  #map :global(.maplibregl-ctrl-bottom-right) {
    right: calc(
      env(safe-area-inset-right) + var(--map-control-edge)
    ) !important;
    bottom: calc(
      env(safe-area-inset-bottom) + var(--map-control-edge)
    ) !important;
  }

  #map :global(.maplibregl-ctrl-bottom-left) {
    left: calc(env(safe-area-inset-left) + var(--map-control-edge)) !important;
    bottom: calc(
      env(safe-area-inset-bottom) + var(--map-control-edge)
    ) !important;
  }

  #map :global(.maplibregl-ctrl-group button) {
    width: 44px;
    height: 44px;
  }

  @media (min-width: 769px) {
    #map.panel-open :global(.maplibregl-ctrl-bottom-right) {
      right: calc(
        var(--context-panel-width) + env(safe-area-inset-right) +
          var(--map-control-edge)
      ) !important;
    }
  }

  @media (max-width: 768px) {
    #map.panel-open :global(.maplibregl-ctrl-bottom-right),
    #map.panel-open :global(.maplibregl-ctrl-bottom-left) {
      top: calc(env(safe-area-inset-top) + var(--toolbar-offset) + 8px);
      bottom: auto !important;
    }

    #map.panel-open :global(.maplibregl-ctrl-bottom-right) {
      right: calc(env(safe-area-inset-right) + 10px) !important;
    }

    #map.panel-open :global(.maplibregl-ctrl-bottom-left) {
      left: calc(env(safe-area-inset-left) + 10px) !important;
    }
  }
</style>
