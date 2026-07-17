<script lang="ts">
  import { tick, createEventDispatcher } from "svelte";
  import {
    isSearchOpen,
    searchQuery,
    closeSearch,
  } from "$lib/stores/searchStore";
  import { contextPanelOpen } from "$lib/stores/uiView";
  import type { MapEntityViewModel } from "$lib/map/types";
  import { restoreTarget } from "$lib/utils/focusManager";

  export let filteredResults: MapEntityViewModel[] = [];
  const dispatch = createEventDispatcher<{ select: MapEntityViewModel }>();
  let inputEl: HTMLInputElement;
  let listEl: HTMLUListElement;
  let activeIndex = -1;
  let wasOpen = false;
  let showAll = false;
  let previousQuery = "";
  let previousResults = filteredResults;

  $: visibleResults = showAll ? filteredResults : filteredResults.slice(0, 6);
  $: {
    if ($searchQuery !== previousQuery) {
      previousQuery = $searchQuery;
      showAll = false;
      activeIndex = -1;
    }
  }
  $: {
    if (filteredResults !== previousResults) {
      previousResults = filteredResults;
      activeIndex = -1;
      if (filteredResults.length <= 6) showAll = false;
    }
  }
  $: {
    if ($isSearchOpen) {
      wasOpen = true;
      (async () => {
        await tick();
        if ($isSearchOpen && inputEl) inputEl.focus();
      })();
    } else {
      activeIndex = -1;
      showAll = false;
      if (wasOpen) {
        wasOpen = false;
        restoreTarget("search");
      }
    }
  }

  function resultOptionId(item: MapEntityViewModel): string {
    return `search-option-${item.type}-${item.id}`;
  }

  function onSelect(item: MapEntityViewModel) {
    dispatch("select", item);
    closeSearch();
  }
  function handleGlobalKeydown(e: KeyboardEvent) {
    if (!$isSearchOpen || e.defaultPrevented) return;
    if (e.key === "Escape") closeSearch();
  }
  function handleInputKeydown(e: KeyboardEvent) {
    if (!$isSearchOpen || visibleResults.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % visibleResults.length;
      scrollToActive();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIndex =
        activeIndex <= 0 ? visibleResults.length - 1 : activeIndex - 1;
      scrollToActive();
    } else if (e.key === "Enter") {
      e.preventDefault();
      const selected = visibleResults[activeIndex >= 0 ? activeIndex : 0];
      if (selected) onSelect(selected);
    } else if (e.key === "Home") {
      e.preventDefault();
      activeIndex = 0;
      scrollToActive();
    } else if (e.key === "End") {
      e.preventDefault();
      activeIndex = visibleResults.length - 1;
      scrollToActive();
    }
  }
  async function scrollToActive() {
    await tick();
    const activeEl = listEl?.children[activeIndex] as HTMLElement | undefined;
    activeEl?.scrollIntoView({ block: "nearest" });
  }
</script>

<svelte:window on:keydown={handleGlobalKeydown} />

{#if $isSearchOpen}
  <div
    class="search-overlay"
    class:panel-open={$contextPanelOpen}
    data-testid="search-overlay"
    role="dialog"
    aria-label="Finden"
    aria-modal="false"
  >
    <div class="search-box">
      <span class="search-icon" aria-hidden="true">⌕</span>
      <input
        bind:this={inputEl}
        bind:value={$searchQuery}
        type="search"
        placeholder="Gewebe durchsuchen…"
        aria-label="Suchbegriff"
        aria-autocomplete="list"
        aria-controls={$searchQuery.trim().length > 0 &&
        visibleResults.length > 0
          ? "search-results-listbox"
          : undefined}
        aria-activedescendant={activeIndex >= 0 &&
        activeIndex < visibleResults.length
          ? resultOptionId(visibleResults[activeIndex])
          : undefined}
        on:keydown={handleInputKeydown}
      />
      <button
        class="close-btn"
        on:click={closeSearch}
        aria-label="Finden schließen">✕</button
      >
    </div>

    {#if $searchQuery.trim().length > 0}
      {#if visibleResults.length > 0}
        <div class="result-meta" aria-live="polite">
          {filteredResults.length === 1
            ? "1 Treffer auf der Karte"
            : `${filteredResults.length} Treffer auf der Karte`}
        </div>
        <ul
          class="results"
          id="search-results-listbox"
          role="listbox"
          aria-label="Suchvorschläge"
          bind:this={listEl}
        >
          {#each visibleResults as result, index}
            <li
              id={resultOptionId(result)}
              class="result-item"
              role="option"
              aria-selected={activeIndex === index}
              class:active={activeIndex === index}
              on:click={() => onSelect(result)}
              on:keydown={(e) => {
                if (e.key === "Enter") onSelect(result);
              }}
              on:mouseenter={() => (activeIndex = index)}
            >
              <div class="result-content">
                <span class="result-title">{result.title}</span>
                {#if result.summary}<span class="result-summary"
                    >{result.summary.length > 80
                      ? result.summary.slice(0, 80) + "…"
                      : result.summary}</span
                  >{/if}
              </div>
              <span class="result-type"
                >{result.type === "node" ? "Knoten" : "Garnrolle"}</span
              >
            </li>
          {/each}
        </ul>
        {#if filteredResults.length > 6}
          <button
            type="button"
            class="show-more"
            aria-expanded={showAll}
            on:click={() => {
              showAll = !showAll;
              activeIndex = -1;
            }}
            >{showAll
              ? "Weniger Vorschläge"
              : `Alle ${filteredResults.length} Vorschläge zeigen`}</button
          >
        {/if}
      {:else}
        <div class="no-results" role="status">
          Keine Treffer für „{$searchQuery}“
        </div>
      {/if}
    {/if}
  </div>
{/if}

<style>
  .search-overlay {
    position: fixed;
    top: calc(env(safe-area-inset-top) + var(--toolbar-offset) + 10px);
    left: 50%;
    width: min(520px, calc(100vw - 32px));
    max-height: min(360px, calc(100dvh - 110px));
    transform: translateX(-50%);
    z-index: var(--z-map-lens);
    padding: 0.65rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 16px;
    background: rgba(20, 22, 28, 0.95);
    box-shadow: var(--shadow);
    backdrop-filter: blur(var(--map-lens-blur));
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
  }
  .search-box {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .search-icon {
    width: 1.4rem;
    color: var(--accent);
    text-align: center;
    font-size: 1.15rem;
  }
  .search-box input {
    flex: 1;
    min-width: 0;
    min-height: 44px;
    padding: 0.65rem 0.25rem;
    border: 0;
    outline: 0;
    font-size: 1rem;
    background: transparent;
    color: var(--text);
    box-sizing: border-box;
  }
  .search-box input:focus-visible {
    box-shadow: inset 0 -2px var(--accent);
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
  .result-meta {
    padding: 0.35rem 0.45rem 0.15rem;
    color: var(--muted);
    font-size: 0.78rem;
  }
  .results {
    list-style: none;
    padding: 0;
    margin: 0.35rem 0 0;
    overflow-y: auto;
    border-top: 1px solid var(--panel-border);
  }
  .result-item {
    width: 100%;
    box-sizing: border-box;
    text-align: left;
    padding: 0.65rem 0.5rem;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    color: var(--text);
    border-bottom: 1px solid var(--panel-border);
  }
  .result-item:hover,
  .result-item.active {
    background: var(--accent-soft);
  }
  .result-item.active {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  .result-content {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    overflow: hidden;
    min-width: 0;
  }
  .result-title {
    font-weight: 650;
  }
  .result-summary {
    font-size: 0.82rem;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .result-type {
    flex: 0 0 auto;
    font-size: 0.75rem;
    color: var(--muted);
  }
  .show-more {
    min-height: 44px;
    margin-top: 0.35rem;
    border: 0;
    border-radius: 10px;
    background: transparent;
    color: var(--accent);
    cursor: pointer;
    font-weight: 650;
  }
  .show-more:hover,
  .show-more:focus-visible {
    background: var(--accent-soft);
  }
  .no-results {
    padding: 0.8rem 0.5rem 0.35rem;
    color: var(--muted);
  }

  @media (min-width: 769px) {
    .search-overlay.panel-open {
      left: calc((100vw - var(--context-panel-width)) / 2);
      width: min(520px, calc(100vw - var(--context-panel-width) - 32px));
    }
  }

  @media (prefers-reduced-transparency: reduce) {
    .search-overlay {
      background: var(--panel-solid);
      backdrop-filter: none;
    }
  }

  @media (max-width: 520px) {
    .search-overlay {
      top: calc(env(safe-area-inset-top) + var(--toolbar-offset) + 4px);
      width: calc(100vw - 20px);
      max-height: min(42dvh, 340px);
      padding: 0.5rem;
      border-radius: 14px;
    }
  }
</style>
