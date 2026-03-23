<script lang="ts">
  import { tick } from 'svelte';
  import { isFilterOpen, activeFilters, closeFilter, toggleFilterType, clearFilters } from '$lib/stores/filterStore';
  import { contextPanelOpen } from '$lib/stores/uiView';
  import { restoreTarget } from '$lib/utils/focusManager';

  export let availableTypes: { id: string, label: string, count: number }[] = [];

  let overlayEl: HTMLDivElement;
  let closeBtnEl: HTMLButtonElement;
  let wasOpen = false;

  // Set focus when filter opens
  $: {
    if ($isFilterOpen) {
      wasOpen = true;
      (async () => {
        await tick();
        if ($isFilterOpen && overlayEl) {
          const firstCheckboxEl = overlayEl.querySelector('input[type="checkbox"]') as HTMLInputElement;
          if (firstCheckboxEl) {
            firstCheckboxEl.focus();
          } else if (closeBtnEl) {
            closeBtnEl.focus();
          }
        }
      })();
    } else {
      if (wasOpen) {
        wasOpen = false;
        restoreTarget('filter');
      }
    }
  }

  function handleGlobalKeydown(e: KeyboardEvent) {
    if (!$isFilterOpen) return;
    if (e.key === 'Escape') {
      closeFilter();
    }
  }
</script>

<svelte:window on:keydown={handleGlobalKeydown} />

{#if $isFilterOpen}
  <div bind:this={overlayEl} class="filter-overlay" class:panel-open={$contextPanelOpen} data-testid="filter-overlay" role="dialog" aria-label="Filter" aria-modal="false">
    <div class="filter-header">
      <h3>Filter</h3>
      <div class="header-actions">
        {#if $activeFilters.size > 0}
          <button class="clear-btn" on:click={clearFilters}>Alle löschen</button>
        {/if}
        <button class="close-btn" bind:this={closeBtnEl} on:click={closeFilter} aria-label="Filter schließen">✕</button>
      </div>
    </div>

    <div class="filter-content">
      {#if availableTypes.length > 0}
        <fieldset class="filter-group">
          <legend>Knotenarten & Garnrollen</legend>
          <ul class="filter-list">
            {#each availableTypes as type}
              <li>
                <label class="filter-item">
                  <input
                    type="checkbox"
                    checked={$activeFilters.has(type.id)}
                    on:change={() => toggleFilterType(type.id)}
                  />
                  <span class="filter-label">{type.label}</span>
                  <span class="filter-count">({type.count})</span>
                </label>
              </li>
            {/each}
          </ul>
        </fieldset>
      {:else}
        <div class="no-filters" role="status">Keine filterbaren Elemente vorhanden</div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .filter-overlay {
    position: fixed;
    bottom: var(--map-bottom-ui-offset, 60px); /* strictly bound to ActionBar + safe-area */
    left: 0;
    right: 0;
    background: var(--panel, #fff);
    border-top: 1px solid var(--panel-border, rgba(0,0,0,0.1));
    z-index: 39; /* just below ActionBar */
    padding: 1rem;
    box-shadow: 0 -4px 16px rgba(0,0,0,0.1);
    display: flex;
    flex-direction: column;
    max-height: 50vh;
  }

  /* Desktop: adjust layout to avoid overlapping ContextPanel */
  @media (min-width: 769px) {
    .filter-overlay.panel-open {
      right: var(--context-panel-width, 400px);
    }
  }

  .filter-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }

  .filter-header h3 {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
  }

  .header-actions {
    display: flex;
    gap: 1rem;
    align-items: center;
  }

  .clear-btn {
    background: none;
    border: none;
    color: var(--primary, #005fcc);
    font-size: 0.9rem;
    cursor: pointer;
    text-decoration: underline;
    padding: 0;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 1.2rem;
    cursor: pointer;
    color: var(--text);
    padding: 0 0.5rem;
  }

  .filter-content {
    overflow-y: auto;
  }

  .filter-group {
    border: none;
    padding: 0;
    margin: 0;
  }

  .filter-group legend {
    margin: 0 0 0.5rem 0;
    font-size: 0.9rem;
    color: var(--muted, #666);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .filter-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .filter-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    padding: 0.25rem 0;
  }

  .filter-item input[type="checkbox"] {
    width: 1.1rem;
    height: 1.1rem;
    cursor: pointer;
  }

  .filter-label {
    flex: 1;
    font-size: 1rem;
    color: var(--text, #333);
  }

  .filter-count {
    font-size: 0.9rem;
    color: var(--muted, #666);
  }

  .no-filters {
    padding: 1rem;
    text-align: center;
    color: var(--muted, #666);
  }
</style>
