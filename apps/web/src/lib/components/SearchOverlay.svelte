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

  $: {
    if ($isSearchOpen) {
      wasOpen = true;
      (async () => {
        await tick();
        if ($isSearchOpen && inputEl) inputEl.focus();
      })();
    } else {
      activeIndex = -1;
      if (wasOpen) {
        wasOpen = false;
        restoreTarget("search");
      }
    }
  }
  $: if (filteredResults || $searchQuery) activeIndex = -1;

  function onSelect(item: MapEntityViewModel) {
    dispatch("select", item);
    closeSearch();
  }
  function handleGlobalKeydown(e: KeyboardEvent) {
    if (!$isSearchOpen || e.defaultPrevented) return;
    if (e.key === "Escape") closeSearch();
  }
  function handleInputKeydown(e: KeyboardEvent) {
    if (!$isSearchOpen || filteredResults.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % filteredResults.length;
      scrollToActive();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIndex =
        activeIndex <= 0 ? filteredResults.length - 1 : activeIndex - 1;
      scrollToActive();
    } else if (e.key === "Enter") {
      e.preventDefault();
      onSelect(filteredResults[activeIndex >= 0 ? activeIndex : 0]);
    } else if (e.key === "Home") {
      e.preventDefault();
      activeIndex = 0;
      scrollToActive();
    } else if (e.key === "End") {
      e.preventDefault();
      activeIndex = filteredResults.length - 1;
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
    aria-label="Suche"
    aria-modal="false"
  >
    <div class="search-box">
      <input
        bind:this={inputEl}
        bind:value={$searchQuery}
        type="text"
        placeholder="Gewebe durchsuchen…"
        aria-label="Suchbegriff"
        aria-autocomplete="list"
        aria-controls={$searchQuery.trim().length > 0 &&
        filteredResults.length > 0
          ? "search-results-listbox"
          : undefined}
        aria-activedescendant={activeIndex >= 0 && filteredResults.length > 0
          ? `search-result-${filteredResults[activeIndex]?.id}`
          : undefined}
        on:keydown={handleInputKeydown}
      />
      <button
        class="close-btn"
        on:click={closeSearch}
        aria-label="Suche schließen">✕</button
      >
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
  .search-box {
    display: flex;
    gap: 0.5rem;
  }
  .search-box input {
    flex: 1;
    min-width: 0;
    min-height: 44px;
    padding: 0.75rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 8px;
    font-size: 1rem;
    background: var(--bg);
    color: var(--text);
    box-sizing: border-box;
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
    margin: 1rem 0 0;
    overflow-y: auto;
  }
  .result-item {
    width: 100%;
    box-sizing: border-box;
    text-align: left;
    padding: 0.75rem;
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
    gap: 0.25rem;
    overflow: hidden;
    min-width: 0;
  }
  .result-title {
    font-weight: 600;
  }
  .result-summary {
    font-size: 0.85rem;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .result-type {
    flex: 0 0 auto;
    font-size: 0.8rem;
    color: var(--muted);
  }
  .no-results {
    padding: 1rem;
    text-align: center;
    color: var(--muted);
  }

  @media (min-width: 769px) {
    .search-overlay {
      left: 50%;
      right: auto;
      width: min(720px, calc(100vw - 2rem));
      transform: translateX(-50%);
      border: 1px solid var(--panel-border);
      border-bottom: 0;
      border-radius: 12px 12px 0 0;
    }
    .search-overlay.panel-open {
      left: calc((100vw - var(--context-panel-width)) / 2);
      width: min(720px, calc(100vw - var(--context-panel-width) - 2rem));
    }
  }
</style>
