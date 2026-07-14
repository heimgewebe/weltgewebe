<script lang="ts">
  import Garnrolle from "./Garnrolle.svelte";
  import { contextPanelOpen } from "$lib/stores/uiView";
</script>

<div
  class="topbar"
  class:panel-open={$contextPanelOpen}
  role="toolbar"
  aria-label="Navigation"
>
  <div class="spacer"></div>
  <a class="proposals-button" href="/antraege" data-testid="proposals-button">
    Anträge
  </a>
  <div class="actions">
    <Garnrolle />
  </div>
</div>

<style>
  .topbar {
    position: absolute;
    inset: 0 0 auto 0;
    min-height: 52px;
    z-index: 41;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: env(safe-area-inset-top) 12px 0 12px;
    background: linear-gradient(180deg, rgba(0, 0, 0, 0.55), rgba(0, 0, 0, 0));
    color: var(--text);
    pointer-events: none;
    transition: right 0.3s ease-in-out;
  }

  .spacer {
    flex: 1;
    pointer-events: none;
  }

  .proposals-button {
    position: absolute;
    left: 50%;
    top: calc(env(safe-area-inset-top) + 8px);
    transform: translateX(-50%);
    display: inline-flex;
    align-items: center;
    min-height: 38px;
    padding: 0 16px;
    border: 1px solid rgba(255, 255, 255, 0.42);
    border-radius: 999px;
    background: rgba(18, 31, 25, 0.8);
    color: #fff;
    text-decoration: none;
    font-weight: 720;
    backdrop-filter: blur(12px);
    pointer-events: auto;
  }

  .proposals-button:hover,
  .proposals-button:focus-visible {
    background: rgba(31, 91, 66, 0.94);
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 8px;
    pointer-events: auto;
  }

  @media (min-width: 769px) {
    .topbar.panel-open {
      right: var(--context-panel-width, 400px);
    }
  }
</style>
