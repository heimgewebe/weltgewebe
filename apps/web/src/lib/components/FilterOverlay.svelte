<script lang="ts">
  import { createEventDispatcher, tick } from 'svelte';
  import { isFilterOpen, activeFilters, closeFilter, toggleFilterType, clearFilters } from '$lib/stores/filterStore';
  import { contextPanelOpen } from '$lib/stores/uiView';
  import { restoreTarget, suppressNextRestore } from '$lib/utils/focusManager';
  import type { MapEntityViewModel } from '$lib/map/types';

  export let availableTypes: { id: string, label: string, count: number }[] = [];
  export let filteredResults: MapEntityViewModel[] = [];

  const dispatch = createEventDispatcher<{ select: MapEntityViewModel }>();
  $: listedResults = filteredResults.slice(0, 50);

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

  function selectResult(result: MapEntityViewModel) {
    suppressNextRestore('filter');
    dispatch('select', result);
    closeFilter();
  }

  function resultType(result: MapEntityViewModel): string {
    return result.type === 'garnrolle' ? 'Garnrolle' : result.kind || 'Knoten';
  }

  function handleGlobalKeydown(e: KeyboardEvent) {
    if (!$isFilterOpen) return;
    // Respect capture-phase handlers (e.g. Garnrolle menu) that own this Escape
    if (e.defaultPrevented) return;
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

      <section class="filter-results" aria-labelledby="filter-results-heading">
        <h4 id="filter-results-heading">Treffer ({filteredResults.length})</h4>
        {#if listedResults.length > 0}
          <ul class="filter-result-list">
            {#each listedResults as result}
              <li>
                <button
                  type="button"
                  class="filter-result"
                  data-testid={`filter-result-${result.type}-${result.id}`}
                  on:click={() => selectResult(result)}
                >
                  <span class="filter-result-main">
                    <span class="filter-result-title">{result.title}</span>
                    {#if result.summary}
                      <span class="filter-result-summary">{result.summary}</span>
                    {/if}
                  </span>
                  <span class="filter-result-type">{resultType(result)}</span>
                </button>
              </li>
            {/each}
          </ul>
          {#if filteredResults.length > listedResults.length}
            <p class="result-limit-note">Die ersten {listedResults.length} Treffer werden angezeigt.</p>
          {/if}
        {:else}
          <p class="no-results" role="status">Keine Treffer für diese Filter.</p>
        {/if}
      </section>
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
    min-width: 44px;
    min-height: 44px;
    display: grid;
    place-items: center;
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

  .filter-results {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--panel-border, rgba(0,0,0,0.1));
  }

  .filter-results h4 {
    margin: 0 0 0.5rem;
    font-size: 0.9rem;
    color: var(--muted, #666);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .filter-result-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.5rem;
  }

  .filter-result {
    width: 100%;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.65rem 0.75rem;
    border: 1px solid var(--panel-border, rgba(0,0,0,0.1));
    border-radius: var(--radius, 6px);
    background: var(--panel, #fff);
    color: var(--text, #333);
    text-align: left;
    cursor: pointer;
  }

  .filter-result:hover,
  .filter-result:focus-visible {
    border-color: var(--primary, #005fcc);
    outline: none;
  }

  .filter-result-main {
    min-width: 0;
    display: grid;
    gap: 0.15rem;
  }

  .filter-result-title {
    font-weight: 600;
  }

  .filter-result-summary {
    overflow: hidden;
    color: var(--muted, #666);
    font-size: 0.85rem;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .filter-result-type {
    flex: 0 0 auto;
    color: var(--muted, #666);
    font-size: 0.8rem;
  }

  .result-limit-note,
  .no-results,
  .no-filters {
    padding: 1rem;
    text-align: center;
    color: var(--muted, #666);
  }
</style>
