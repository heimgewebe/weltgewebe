<script lang="ts">
  import { tick } from "svelte";
  import {
    isFilterOpen,
    activeFilters,
    closeFilter,
    toggleFilterType,
    clearFilters,
  } from "$lib/stores/filterStore";
  import { contextPanelOpen } from "$lib/stores/uiView";
  import { restoreTarget } from "$lib/utils/focusManager";
  import type { MapEntityViewModel } from "$lib/map/types";
  import { nodeKindLabel } from "$lib/ui/productLanguage";

  export let availableTypes: { id: string; label: string; count: number }[] =
    [];
  export let filteredResults: MapEntityViewModel[] = [];

  let overlayEl: HTMLDivElement;
  let closeBtnEl: HTMLButtonElement;
  let wasOpen = false;

  $: activeCount = $activeFilters.size;

  $: {
    if ($isFilterOpen) {
      wasOpen = true;
      (async () => {
        await tick();
        const first = overlayEl?.querySelector(
          'input[type="checkbox"]',
        ) as HTMLInputElement | null;
        (first || closeBtnEl)?.focus();
      })();
    } else if (wasOpen) {
      wasOpen = false;
      restoreTarget("filter");
    }
  }

  function filterLabel(type: { id: string; label: string }): string {
    return type.id === "Garnrolle" ? "Garnrollen" : nodeKindLabel(type.id);
  }
  function handleGlobalKeydown(e: KeyboardEvent) {
    if (!$isFilterOpen || e.defaultPrevented || e.repeat || e.key !== "Escape")
      return;
    e.preventDefault();
    closeFilter();
  }
</script>

<svelte:window on:keydown={handleGlobalKeydown} />

{#if $isFilterOpen}
  <div
    bind:this={overlayEl}
    class="filter-overlay"
    class:panel-open={$contextPanelOpen}
    data-testid="filter-overlay"
    role="dialog"
    aria-label="Karteninhalt"
    aria-modal="false"
  >
    <div class="filter-header">
      <div>
        <span class="eyebrow">Kartenlinse</span>
        <h3>Karteninhalt</h3>
      </div>
      <button
        class="close-btn"
        bind:this={closeBtnEl}
        on:click={closeFilter}
        aria-label="Karteninhalt schließen">✕</button
      >
    </div>

    <p class="filter-summary" aria-live="polite">
      {activeCount === 0
        ? `Alle ${filteredResults.length} Elemente sichtbar`
        : activeCount === 1
          ? `1 Auswahl aktiv · ${filteredResults.length} Elemente sichtbar`
          : `${activeCount} Auswahlen aktiv · ${filteredResults.length} Elemente sichtbar`}
    </p>

    {#if availableTypes.length > 0}
      <fieldset class="filter-group">
        <legend>Was soll auf der Karte erscheinen?</legend>
        <ul class="filter-list">
          {#each availableTypes as type}
            <li>
              <label
                class="filter-item"
                class:active={$activeFilters.has(type.id)}
                ><input
                  type="checkbox"
                  checked={$activeFilters.has(type.id)}
                  on:change={() => toggleFilterType(type.id)}
                /><span class="filter-label">{filterLabel(type)}</span><span
                  class="filter-count">{type.count}</span
                ></label
              >
            </li>
          {/each}
        </ul>
      </fieldset>
    {:else}
      <div class="no-filters" role="status">
        Keine auswählbaren Elemente vorhanden
      </div>
    {/if}

    {#if activeCount > 0}
      <button class="clear-btn" type="button" on:click={clearFilters}
        >Alles wieder zeigen</button
      >
    {/if}
  </div>
{/if}

<style>
  .filter-overlay {
    position: fixed;
    top: calc(env(safe-area-inset-top) + var(--toolbar-offset) + 10px);
    right: calc(16px + env(safe-area-inset-right));
    width: min(380px, calc(100vw - 32px));
    max-height: min(440px, calc(100dvh - 112px));
    z-index: var(--z-map-lens);
    padding: 0.9rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 16px;
    background: rgba(20, 22, 28, 0.95);
    box-shadow: var(--shadow);
    backdrop-filter: blur(var(--map-lens-blur));
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    overflow-y: auto;
  }
  .filter-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }
  .filter-header h3 {
    margin: 0.1rem 0 0;
    font-size: 1.15rem;
  }
  .eyebrow {
    color: var(--muted);
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
  }
  .close-btn {
    background: none;
    border: none;
    font-size: 1.2rem;
    cursor: pointer;
    color: var(--text);
    min-width: 44px;
    min-height: 44px;
    display: grid;
    place-items: center;
  }
  .filter-summary {
    margin: 0.45rem 0 0.75rem;
    color: var(--muted);
    font-size: 0.82rem;
  }
  .filter-group {
    border: 0;
    padding: 0;
    margin: 0;
  }
  .filter-group legend {
    margin: 0 0 0.55rem;
    color: var(--muted);
    font-size: 0.78rem;
  }
  .filter-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.45rem;
  }
  .filter-item {
    min-height: 44px;
    padding: 0.45rem 0.6rem;
    border: 1px solid var(--panel-border);
    border-radius: 12px;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    background: rgba(15, 17, 21, 0.72);
  }
  .filter-item.active {
    border-color: var(--accent);
    background: var(--accent-soft);
  }
  .filter-item input {
    width: 1.15rem;
    height: 1.15rem;
    margin: 0;
    accent-color: var(--accent);
  }
  .filter-label {
    min-width: 0;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .filter-count {
    color: var(--muted);
    font-size: 0.78rem;
    font-variant-numeric: tabular-nums;
  }
  .clear-btn {
    min-height: 44px;
    margin-top: 0.75rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 12px;
    background: transparent;
    color: var(--accent);
    cursor: pointer;
    font-weight: 650;
  }
  .clear-btn:hover,
  .clear-btn:focus-visible {
    background: var(--accent-soft);
  }
  .no-filters {
    color: var(--muted);
    padding: 0.75rem 0;
  }

  @media (min-width: 769px) {
    .filter-overlay.panel-open {
      right: calc(var(--context-panel-width) + 16px);
      width: min(380px, calc(100vw - var(--context-panel-width) - 32px));
    }
  }

  @media (prefers-reduced-transparency: reduce) {
    .filter-overlay {
      background: var(--panel-solid);
      backdrop-filter: none;
    }
  }

  @media (max-width: 520px) {
    .filter-overlay {
      top: calc(env(safe-area-inset-top) + var(--toolbar-offset) + 4px);
      left: 10px;
      right: 10px;
      width: auto;
      max-height: min(46dvh, 390px);
      padding: 0.75rem;
      border-radius: 14px;
    }
    .filter-list {
      grid-template-columns: 1fr;
    }
  }
</style>
