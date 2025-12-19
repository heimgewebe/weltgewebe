<script lang="ts">
  import { view, viewPanelOpen } from '$lib/stores/uiView';
  import { slide } from 'svelte/transition';

  function close() {
    $viewPanelOpen = false;
  }
</script>

<style>
  .view-panel {
    position: absolute;
    z-index: 40;
    background: var(--panel);
    border: 1px solid var(--panel-border);
    box-shadow: var(--shadow);
    border-radius: var(--radius);
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    color: var(--text);
  }

  /* Desktop: Top Right */
  @media (min-width: 600px) {
    .view-panel {
      top: calc(var(--toolbar-offset) + env(safe-area-inset-top) + 8px);
      right: 12px;
      width: 280px;
    }
  }

  /* Mobile: Bottom Sheet */
  @media (max-width: 599px) {
    .view-panel {
      bottom: 0;
      left: 0;
      right: 0;
      border-radius: 16px 16px 0 0;
      border-bottom: none;
      padding-bottom: max(16px, env(safe-area-inset-bottom) + 16px);
    }
  }

  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
  }

  .section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  label {
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    font-size: 14px;
  }

  input[type="checkbox"] {
    width: 16px;
    height: 16px;
    accent-color: var(--accent);
  }

  .backdrop {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.2);
    z-index: 39;
  }
</style>

{#if $viewPanelOpen}
  <div class="backdrop" on:click={close} on:keydown={(e) => e.key === 'Escape' && close()} role="button" tabindex="-1" aria-label="Close view panel"></div>
  <div class="view-panel" transition:slide={{ duration: 200, axis: 'y' }}>
    <h3>Ansicht</h3>

    <div class="section">
      <label>
        <input type="checkbox" bind:checked={$view.showNodes}>
        Knoten anzeigen
      </label>
      <label>
        <input type="checkbox" bind:checked={$view.showEdges}>
        Fäden anzeigen
      </label>
      <label>
        <input type="checkbox" bind:checked={$view.showGovernance}>
        Anträge & Governance
      </label>
    </div>

    {#if $view.showSearch}
      <hr style="border: 0; border-top: 1px solid var(--panel-border); width: 100%; margin: 0;">
      <div class="section">
        <label>
          Suche (Stub)
          <input type="text" placeholder="Suchen..." style="width: 100%; padding: 6px; border-radius: 4px; border: 1px solid var(--panel-border); background: var(--bg); color: var(--text);">
        </label>
      </div>
    {/if}

    <div class="section">
      <button on:click={close} style="padding: 6px; background: var(--bg); border: 1px solid var(--panel-border); border-radius: 4px; cursor: pointer; color: var(--text);">
        Schließen
      </button>
    </div>
  </div>
{/if}
