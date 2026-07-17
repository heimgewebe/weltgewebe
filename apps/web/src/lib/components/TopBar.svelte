<script lang="ts">
  import Garnrolle from "./Garnrolle.svelte";
  import GovernanceFan from "./GovernanceFan.svelte";
  import { contextPanelOpen } from "$lib/stores/uiView";
</script>

<div class="topbar" class:panel-open={$contextPanelOpen} role="toolbar" aria-label="Navigation">
  <div class="topbar-spacer" aria-hidden="true"></div>
  <div class="governance-slot"><GovernanceFan /></div>
  <div class="actions"><Garnrolle /></div>
</div>

<style>
  .topbar {
    position: absolute;
    inset: 0 0 auto 0;
    min-height: var(--toolbar-offset);
    z-index: var(--z-map-topbar);
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
    align-items: center;
    padding: env(safe-area-inset-top) 12px 0;
    background: linear-gradient(180deg, rgba(0, 0, 0, 0.46), rgba(0, 0, 0, 0));
    color: var(--text);
    pointer-events: none;
    transition: right var(--motion-ui);
  }

  .governance-slot {
    justify-self: center;
    pointer-events: auto;
  }

  .actions {
    justify-self: end;
    display: flex;
    align-items: center;
    pointer-events: auto;
  }

  @media (min-width: 769px) {
    .topbar.panel-open { right: var(--context-panel-width); }
  }

  @media (prefers-reduced-motion: reduce) {
    .topbar { transition: none; }
  }
</style>
