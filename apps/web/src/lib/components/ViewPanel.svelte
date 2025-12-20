<script lang="ts">
  import { view, viewPanelOpen } from '$lib/stores/uiView';
  import { slide } from 'svelte/transition';
  import { onMount } from 'svelte';

  function close() {
    $viewPanelOpen = false;
  }

  function onKeyDown(e: KeyboardEvent) {
    if ($viewPanelOpen && e.key === 'Escape') {
      e.preventDefault();
      close();
    }
  }
</script>

<svelte:window on:keydown={onKeyDown} />

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

  .search-label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    cursor: default;
    align-items: flex-start;
  }

  input[type="checkbox"] {
    width: 16px;
    height: 16px;
    accent-color: var(--accent);
  }

  input[type="text"] {
    width: 100%;
    padding: 6px;
    border-radius: 4px;
    border: 1px solid var(--panel-border);
    background: var(--bg);
    color: var(--text);
  }

  .backdrop {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.2);
    z-index: 39;
  }
</style>

{#if $viewPanelOpen}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="backdrop" on:click={close}></div>
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
        <label for="search-input" class="search-label">
          Suche (Stub)
        </label>
        <input id="search-input" type="text" placeholder="Suchen...">
      </div>
    {/if}

    <div class="section">
      <button on:click={close} style="padding: 6px; background: var(--bg); border: 1px solid var(--panel-border); border-radius: 4px; cursor: pointer; color: var(--text);">
        Schließen
      </button>
    </div>
  </div>
{/if}
