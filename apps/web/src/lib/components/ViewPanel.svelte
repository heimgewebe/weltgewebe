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
    /* Glass Effect */
    background: color-mix(in srgb, var(--panel) 88%, transparent);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
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
      /* Padding bottom to respect safe area + some visual breathing room */
      padding-bottom: max(24px, env(safe-area-inset-bottom) + 16px);
    }
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
  }

  .close-btn {
    appearance: none;
    background: transparent;
    border: none;
    color: var(--muted);
    font-size: 20px;
    line-height: 1;
    padding: 4px;
    cursor: pointer;
    border-radius: 4px;
  }
  .close-btn:hover {
    background: rgba(0,0,0,0.05);
    color: var(--text);
  }

  .section {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  /* Switch Toggle Styles */
  .toggle-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
  }

  .toggle-label {
    display: flex;
    flex-direction: column;
  }
  .toggle-title {
    font-size: 15px;
    font-weight: 500;
  }
  .toggle-desc {
    font-size: 12px;
    color: var(--muted);
  }

  .switch {
    position: relative;
    width: 40px;
    height: 24px;
    background: var(--panel-border);
    border-radius: 99px;
    transition: background 0.2s;
    flex-shrink: 0;
  }
  .switch::after {
    content: "";
    position: absolute;
    top: 2px;
    left: 2px;
    width: 20px;
    height: 20px;
    background: #fff;
    border-radius: 50%;
    transition: transform 0.2s;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  }
  input[type="checkbox"] {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
  }
  input:checked + .switch {
    background: var(--accent);
  }
  input:checked + .switch::after {
    transform: translateX(16px);
  }
  input:focus-visible + .switch {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  /* Search Styles */
  .separator {
    border: 0;
    border-top: 1px solid var(--panel-border);
    width: 100%;
    margin: 4px 0;
  }

  .search-label {
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 4px;
    display: block;
  }

  .search-input {
    width: 100%;
    padding: 8px 10px;
    border-radius: 6px;
    border: 1px solid var(--panel-border);
    background: rgba(255,255,255,0.05); /* slightly lighter on dark, darker on light? assuming dark/panel vars handle it */
    color: var(--text);
    font-size: 14px;
  }
  .search-input:focus {
    outline: 2px solid var(--accent);
    border-color: transparent;
  }

  .backdrop {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.2);
    z-index: 39;
    backdrop-filter: blur(1px);
  }

  @media (prefers-reduced-motion: reduce) {
    .view-panel {
      transition: none !important;
    }
    .switch, .switch::after {
      transition: none !important;
    }
  }
</style>

{#if $viewPanelOpen}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="backdrop" on:click={close}></div>
  <div class="view-panel" transition:slide={{ duration: 180, axis: 'y' }}>
    <div class="header">
      <h3>Ansicht</h3>
      <button class="close-btn" on:click={close} aria-label="Schließen">✕</button>
    </div>

    <div class="section">
      <label class="toggle-row">
        <span class="toggle-label">
          <span class="toggle-title">Knoten</span>
          <span class="toggle-desc">Orte & Strukturen</span>
        </span>
        <input type="checkbox" bind:checked={$view.showNodes}>
        <div class="switch"></div>
      </label>

      <label class="toggle-row">
        <span class="toggle-label">
          <span class="toggle-title">Fäden</span>
          <span class="toggle-desc">Verbindungen</span>
        </span>
        <input type="checkbox" bind:checked={$view.showEdges}>
        <div class="switch"></div>
      </label>

      <label class="toggle-row">
        <span class="toggle-label">
          <span class="toggle-title">Governance</span>
          <span class="toggle-desc">Anträge & Prozesse</span>
        </span>
        <input type="checkbox" bind:checked={$view.showGovernance}>
        <div class="switch"></div>
      </label>
    </div>

    {#if $view.showSearch}
      <hr class="separator">
      <div>
        <label for="search-input" class="search-label">Suche</label>
        <input id="search-input" class="search-input" type="text" placeholder="Filtern...">
      </div>
    {/if}
  </div>
{/if}
