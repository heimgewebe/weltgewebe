<script lang="ts">
  import { tick, createEventDispatcher } from 'svelte';
  import { isSearchOpen, searchQuery, closeSearch } from '$lib/stores/searchStore';
  import { contextPanelOpen } from '$lib/stores/uiView';
  import type { RenderableMapPoint } from '$lib/map/types';
  import { restoreTarget } from '$lib/utils/focusManager';

  export let filteredResults: RenderableMapPoint[] = [];

  const dispatch = createEventDispatcher<{
    select: RenderableMapPoint;
  }>();

  let inputEl: HTMLInputElement;
  let listEl: HTMLUListElement;
  let activeIndex = -1;
  let wasOpen = false;

  // focus on input when search opens and reset active index
  $: {
    if ($isSearchOpen) {
      wasOpen = true;
      (async () => {
        await tick();
        if ($isSearchOpen && inputEl) {
          inputEl.focus();
        }
      })();
    } else {
      activeIndex = -1;
      if (wasOpen) {
        wasOpen = false;
        restoreTarget('search');
      }
    }
  }

  // Reset activeIndex when results change
  $: if (filteredResults || $searchQuery) {
    activeIndex = -1;
  }

  function onSelect(item: RenderableMapPoint) {
    dispatch('select', item);
    closeSearch();
  }

  function handleGlobalKeydown(e: KeyboardEvent) {
    if (!$isSearchOpen) return;
    if (e.defaultPrevented) return;
    if (e.key === 'Escape') {
      closeSearch();
    }
  }

  function handleInputKeydown(e: KeyboardEvent) {
    if (!$isSearchOpen || filteredResults.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % filteredResults.length;
      scrollToActive();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIndex = activeIndex <= 0 ? filteredResults.length - 1 : activeIndex - 1;
      scrollToActive();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIndex >= 0 && activeIndex < filteredResults.length) {
        onSelect(filteredResults[activeIndex]);
      } else if (filteredResults.length > 0) {
        onSelect(filteredResults[0]);
      }
    } else if (e.key === 'Home') {
      e.preventDefault();
      activeIndex = 0;
      scrollToActive();
    } else if (e.key === 'End') {
      e.preventDefault();
      activeIndex = filteredResults.length - 1;
      scrollToActive();
    }
  }

  async function scrollToActive() {
    await tick();
    if (listEl && activeIndex >= 0) {
      const activeEl = listEl.children[activeIndex] as HTMLElement;
      if (activeEl) {
        activeEl.scrollIntoView({ block: 'nearest' });
      }
    }
  }
</script>

<svelte:window on:keydown={handleGlobalKeydown} />

{#if $isSearchOpen}
  <div class="search-overlay" class:panel-open={$contextPanelOpen} data-testid="search-overlay" role="dialog" aria-label="Suche" aria-modal="false">
    <div class="search-box">
      <input
        bind:this={inputEl}
        bind:value={$searchQuery}
        type="text"
        placeholder="Gewebe durchsuchen..."
        aria-label="Suchbegriff"
        aria-autocomplete="list"
        aria-controls={$searchQuery.trim().length > 0 && filteredResults.length > 0 ? "search-results-listbox" : undefined}
        aria-activedescendant={activeIndex >= 0 && filteredResults.length > 0 ? `search-result-${filteredResults[activeIndex]?.id}` : undefined}
        on:keydown={handleInputKeydown}
      />
      <button class="close-btn" on:click={closeSearch} aria-label="Suche schließen">✕</button>
    </div>

    {#if $searchQuery.trim().length > 0}
      {#if filteredResults.length > 0}
        <ul
          class="results"
          id="search-results-listbox"
          role="listbox"
          aria-label="Suchergebnisse"
          bind:this={listEl}
        >
          {#each filteredResults as result, index}
            <li
              id={`search-result-${result.id}`}
              class="result-item"
              role="option"
              aria-selected={activeIndex === index}
              class:active={activeIndex === index}
              on:click={() => onSelect(result)}
              on:keydown={(e) => { if (e.key === 'Enter') onSelect(result); }}
              on:mouseenter={() => (activeIndex = index)}
            >
              <div class="result-content">
                <span class="result-title">{result.title}</span>
                {#if result.summary}
                  <span class="result-summary">{result.summary.length > 60 ? result.summary.slice(0, 60) + '...' : result.summary}</span>
                {/if}
              </div>
              <span class="result-type">{result.type === 'node' ? 'Knoten' : 'Garnrolle'}</span>
            </li>
          {/each}
        </ul>
      {:else}
        <div class="no-results" role="status">Keine Treffer für "{$searchQuery}"</div>
      {/if}
    {/if}
  </div>
{/if}

<style>
  .search-overlay {
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
    min-width: 44px;
    min-height: 44px;
    display: grid;
    place-items: center;
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

  .result-item {
    width: 100%;
    text-align: left;
    padding: 0.75rem 0.5rem;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text);
  }

  .result-item:hover, .result-item.active {
    background: var(--hover, rgba(0,0,0,0.05));
  }

  .result-item.active {
    outline: 2px solid var(--primary, #005fcc);
    outline-offset: -2px;
  }

  .result-content {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    overflow: hidden;
    padding-right: 1rem;
  }

  .result-title {
    font-weight: 500;
  }

  .result-summary {
    font-size: 0.8rem;
    color: var(--muted, #666);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
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
