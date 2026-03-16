<script lang="ts">
  import { tick } from 'svelte';
  import { isSearchOpen, searchQuery, closeSearch } from '$lib/stores/searchStore';
  import { enterFokus, contextPanelOpen } from '$lib/stores/uiView';
  import type { RenderableMapPoint } from '$lib/map/types';

  export let markersData: RenderableMapPoint[] = [];

  let inputEl: HTMLInputElement;

  // focus on input when search opens
  $: if ($isSearchOpen) {
    (async () => {
      await tick();
      if ($isSearchOpen && inputEl) {
        inputEl.focus();
      }
    })();
  }

  let filteredResults: RenderableMapPoint[] = [];
  $: filteredResults = $searchQuery.trim().length > 0
    ? markersData.filter(m => {
        const titleMatch = m.title?.toLowerCase().includes($searchQuery.toLowerCase());
        const summaryMatch = m.summary?.toLowerCase().includes($searchQuery.toLowerCase());
        return titleMatch || summaryMatch;
      }).slice(0, 10)
    : [];

  function toSupportedSelectionType(type: string | undefined): 'node' | 'account' | 'garnrolle' {
    if (type === 'node' || type === 'account' || type === 'garnrolle') {
      return type;
    }
    return 'node';
  }

  function onSelect(item: RenderableMapPoint) {
    const selectionType = toSupportedSelectionType(item.type);
    enterFokus({ type: selectionType, id: item.id, data: item });
    closeSearch();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (!$isSearchOpen) return;
    if (e.key === 'Escape') {
      closeSearch();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if $isSearchOpen}
  <div class="search-overlay" class:panel-open={$contextPanelOpen} data-testid="search-overlay">
    <div class="search-box">
      <input
        bind:this={inputEl}
        bind:value={$searchQuery}
        type="text"
        placeholder="Gewebe durchsuchen..."
        aria-label="Suchbegriff"
      />
      <button class="close-btn" on:click={closeSearch} aria-label="Suche schließen">✕</button>
    </div>

    {#if $searchQuery.trim().length > 0}
      <ul class="results">
        {#each filteredResults as result}
          <li>
            <button class="result-btn" on:click={() => onSelect(result)}>
              <span class="result-title">{result.title}</span>
              <span class="result-type">{result.type === 'node' ? 'Knoten' : 'Garnrolle'}</span>
            </button>
          </li>
        {:else}
          <li class="no-results">Keine Treffer für "{$searchQuery}"</li>
        {/each}
      </ul>
    {/if}
  </div>
{/if}

<style>
  .search-overlay {
    position: fixed;
    bottom: 60px; /* above ActionBar */
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
    .search-overlay.panel-open {
      right: var(--context-panel-width, 400px);
    }
  }

  .search-box {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }

  .search-box input {
    flex: 1;
    padding: 0.75rem;
    border: 1px solid var(--panel-border, #ccc);
    border-radius: 8px;
    font-size: 1rem;
    background: var(--bg, #f9f9f9);
    color: var(--text, #333);
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 1.2rem;
    cursor: pointer;
    color: var(--text);
    padding: 0 0.5rem;
  }

  .results {
    list-style: none;
    padding: 0;
    margin: 0;
    overflow-y: auto;
  }

  .results li {
    border-bottom: 1px solid var(--panel-border, rgba(0,0,0,0.05));
  }

  .results li:last-child {
    border-bottom: none;
  }

  .result-btn {
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    padding: 0.75rem 0.5rem;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text);
  }

  .result-btn:hover {
    background: rgba(0,0,0,0.02);
  }

  .result-title {
    font-weight: 500;
  }

  .result-type {
    font-size: 0.8rem;
    color: var(--muted, #666);
    background: rgba(0,0,0,0.05);
    padding: 2px 6px;
    border-radius: 4px;
  }

  .no-results {
    padding: 1rem;
    text-align: center;
    color: var(--muted, #666);
  }
</style>
