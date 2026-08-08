<script lang="ts">
  import { onMount } from "svelte";
  import GovernanceFan from "./GovernanceFan.svelte";
  import { contextPanelOpen } from "$lib/stores/uiView";

  let AuthSlot: any;
  onMount(() => {
    void import("./TopBarAuth.svelte").then((module) => {
      AuthSlot = module.default;
    });
  });
</script>

<div
  class="topbar"
  class:panel-open={$contextPanelOpen}
  role="toolbar"
  aria-label="Navigation"
>
  <div class="governance-slot">
    <GovernanceFan />
  </div>
  {#if AuthSlot}
    <svelte:component this={AuthSlot} />
  {/if}
</div>

<style>
  .topbar {
    position: absolute;
    inset: 0 0 auto 0;
    min-height: var(--toolbar-offset);
    z-index: var(--z-map-topbar);
    display: grid;
    grid-template-columns: minmax(44px, 1fr) auto minmax(44px, 1fr);
    align-items: center;
    padding: env(safe-area-inset-top) 12px 0;
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--bg) 88%, transparent),
      transparent
    );
    color: var(--text);
    pointer-events: none;
    transition: right var(--motion-ui);
  }

  .governance-slot {
    grid-column: 2;
    justify-self: center;
    pointer-events: auto;
  }

  @media (min-width: 769px) {
    .topbar.panel-open {
      right: var(--context-panel-width);
      --governance-fan-menu-width: max(
        304px,
        calc(100vw - var(--context-panel-width) - 24px)
      );
    }
  }

  @media (max-width: 420px) {
    .topbar {
      grid-template-columns: auto minmax(0, 1fr) auto;
    }

    .governance-slot {
      grid-column: 1;
      justify-self: start;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .topbar {
      transition: none;
    }
  }
</style>
