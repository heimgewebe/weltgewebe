<script lang="ts">
  import { createEventDispatcher, tick } from "svelte";
  import {
    isFilterOpen,
    activeFilters,
    closeFilter,
    toggleFilterType,
    clearFilters,
  } from "$lib/stores/filterStore";
  import { contextPanelOpen } from "$lib/stores/uiView";
  import { restoreTarget, suppressNextRestore } from "$lib/utils/focusManager";
  import type { MapEntityViewModel } from "$lib/map/types";
  import { nodeKindLabel } from "$lib/ui/productLanguage";

  export let availableTypes: { id: string; label: string; count: number }[] =
    [];
  export let filteredResults: MapEntityViewModel[] = [];
  const dispatch = createEventDispatcher<{ select: MapEntityViewModel }>();
  $: showResults = $activeFilters.size > 0;
  $: listedResults = showResults ? filteredResults.slice(0, 50) : [];

  let overlayEl: HTMLDivElement;
  let closeBtnEl: HTMLButtonElement;
  let wasOpen = false;

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

  function selectResult(result: MapEntityViewModel) {
    suppressNextRestore("filter");
    dispatch("select", result);
    closeFilter();
  }
  function resultType(result: MapEntityViewModel): string {
    return result.type === "garnrolle"
      ? "Garnrolle"
      : nodeKindLabel(result.kind);
  }
  function filterLabel(type: { id: string; label: string }): string {
    return type.id === "Garnrolle" ? "Garnrolle" : nodeKindLabel(type.id);
  }
  function handleGlobalKeydown(e: KeyboardEvent) {
    if ($isFilterOpen && !e.defaultPrevented && e.key === "Escape")
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
    aria-label="Filter"
    aria-modal="false"
  >
    <div class="filter-header">
      <h3>Filter</h3>
      <div class="header-actions">
        {#if $activeFilters.size > 0}<button
            class="clear-btn"
            on:click={clearFilters}>Auswahl zurücksetzen</button
          >{/if}
        <button
          class="close-btn"
          bind:this={closeBtnEl}
          on:click={closeFilter}
          aria-label="Filter schließen">✕</button
        >
      </div>
    </div>

    <div class="filter-content">
      {#if availableTypes.length > 0}
        <fieldset class="filter-group">
          <legend>Sichtbare Elemente</legend>
          <ul class="filter-list">
            {#each availableTypes as type}
              <li>
                <label class="filter-item"
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
          Keine filterbaren Elemente vorhanden
        </div>
      {/if}

      {#if showResults}
        <section
          class="filter-results"
          aria-labelledby="filter-results-heading"
        >
          <h4 id="filter-results-heading">
            Treffer ({filteredResults.length})
          </h4>
          {#if listedResults.length > 0}
            <ul class="filter-result-list">
              {#each listedResults as result}
                <li>
                  <button
                    type="button"
                    class="filter-result"
                    data-testid={`filter-result-${result.type}-${result.id}`}
                    on:click={() => selectResult(result)}
                    ><span class="filter-result-main"
                      ><span class="filter-result-title">{result.title}</span
                      >{#if result.summary}<span class="filter-result-summary"
                          >{result.summary}</span
                        >{/if}</span
                    ><span class="filter-result-type">{resultType(result)}</span
                    ></button
                  >
                </li>
              {/each}
            </ul>
            {#if filteredResults.length > listedResults.length}<p
                class="result-limit-note"
              >
                Die ersten {listedResults.length} Treffer werden angezeigt.
              </p>{/if}
          {:else}
            <p class="no-results" role="status">
              Keine Treffer für diese Auswahl.
            </p>
          {/if}
        </section>
      {:else}
        <p class="filter-hint">
          Wähle mindestens eine Art aus, um die Karte einzugrenzen.
        </p>
      {/if}
    </div>
  </div>
{/if}

<style>
  .filter-overlay {
    position: fixed;
    bottom: var(--map-bottom-ui-offset);
    left: 0;
    right: 0;
    background: var(--panel);
    border-top: 1px solid var(--panel-border);
    z-index: 39;
    padding: 1rem;
    box-shadow: var(--shadow);
    display: flex;
    flex-direction: column;
    max-height: 50dvh;
    box-sizing: border-box;
  }
  .filter-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
    flex: 0 0 auto;
  }
  .filter-header h3 {
    margin: 0;
    font-size: 1.1rem;
  }
  .header-actions {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }
  .clear-btn {
    background: none;
    border: none;
    color: var(--accent);
    font-size: 0.9rem;
    cursor: pointer;
    min-height: 44px;
    padding: 0 0.5rem;
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
    min-height: 0;
  }
  .filter-group {
    border: none;
    padding: 0;
    margin: 0;
  }
  .filter-group legend,
  .filter-results h4 {
    margin: 0 0 0.5rem;
    font-size: 0.78rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .filter-list,
  .filter-result-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.35rem;
  }
  .filter-item {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    cursor: pointer;
    min-height: 44px;
    padding: 0 0.25rem;
  }
  .filter-item input {
    width: 1.2rem;
    height: 1.2rem;
  }
  .filter-label {
    flex: 1;
    font-size: 1rem;
  }
  .filter-count {
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }
  .filter-results {
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--panel-border);
  }
  .filter-result {
    width: 100%;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.65rem 0.75rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 8px;
    background: var(--panel-solid);
    color: var(--text);
    text-align: left;
    cursor: pointer;
  }
  .filter-result:hover,
  .filter-result:focus-visible {
    border-color: var(--accent);
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
    color: var(--muted);
    font-size: 0.85rem;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .filter-result-type {
    flex: 0 0 auto;
    color: var(--muted);
    font-size: 0.8rem;
  }
  .filter-hint,
  .result-limit-note,
  .no-results,
  .no-filters {
    color: var(--muted);
    margin: 0.75rem 0 0;
  }

  @media (min-width: 769px) {
    .filter-overlay {
      left: 50%;
      right: auto;
      width: min(720px, calc(100vw - 2rem));
      transform: translateX(-50%);
      border: 1px solid var(--panel-border);
      border-bottom: 0;
      border-radius: 12px 12px 0 0;
    }
    .filter-overlay.panel-open {
      left: calc((100vw - var(--context-panel-width)) / 2);
      width: min(720px, calc(100vw - var(--context-panel-width) - 2rem));
    }
  }
</style>
