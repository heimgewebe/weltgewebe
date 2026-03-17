<script lang="ts">
  import { contextPanelOpen, enterKomposition } from '$lib/stores/uiView';
  import { toggleSearch, isSearchOpen, closeSearch } from '$lib/stores/searchStore';
  import { toggleFilter, isFilterOpen, closeFilter } from '$lib/stores/filterStore';

  function onNewNode() {
    enterKomposition({ mode: 'new-knoten', source: 'action-bar' });
  }

  import { tick } from 'svelte';

  let searchBtnEl: HTMLButtonElement;
  let filterBtnEl: HTMLButtonElement;

  function onToggleSearch() {
    if ($isFilterOpen) {
      closeFilter();
    }
    toggleSearch();
  }

  function onToggleFilter() {
    if ($isSearchOpen) {
      closeSearch();
    }
    toggleFilter();
  }

  // Restore focus when closing overlays if we were inside them.
  // We use previous state tracking to avoid fragile DOM dependency
  // since the overlay might already be unmounted when this runs.
  let wasFilterOpen = false;
  let wasSearchOpen = false;

  $: {
    if ($isFilterOpen) {
      wasFilterOpen = true;
    } else if (wasFilterOpen) {
      wasFilterOpen = false;
      if (filterBtnEl && typeof document !== 'undefined') {
        const active = document.activeElement;
        // If focus is on body (overlay unmounted) or still in overlay (if animating out), restore it.
        if (active === document.body || (active && active.closest && active.closest('.filter-overlay'))) {
          tick().then(() => filterBtnEl.focus());
        }
      }
    }
  }

  $: {
    if ($isSearchOpen) {
      wasSearchOpen = true;
    } else if (wasSearchOpen) {
      wasSearchOpen = false;
      if (searchBtnEl && typeof document !== 'undefined') {
        const active = document.activeElement;
        // If focus is on body (overlay unmounted) or still in overlay (if animating out), restore it.
        if (active === document.body || (active && active.closest && active.closest('.search-overlay'))) {
          tick().then(() => searchBtnEl.focus());
        }
      }
    }
  }
</script>

<nav class="action-bar" class:panel-open={$contextPanelOpen} aria-label="Aktionsleiste">
  <button bind:this={searchBtnEl} class="action-btn" on:click={onToggleSearch} class:active={$isSearchOpen} aria-label="Suche">Suche</button>
  <button class="action-btn" on:click={onNewNode} aria-label="Neuer Knoten">Neuer Knoten</button>
  <button bind:this={filterBtnEl} class="action-btn" class:active={$isFilterOpen} on:click={onToggleFilter} aria-label="Filter">Filter</button>
</nav>

<style>
  .action-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 60px;
    background: var(--panel, #fff);
    border-top: 1px solid var(--panel-border, rgba(0,0,0,0.1));
    display: flex;
    justify-content: space-around;
    align-items: center;
    z-index: 40;
    padding: 0 1rem;
    box-shadow: var(--shadow, 0 -2px 10px rgba(0,0,0,0.05));
  }

  .action-btn {
    background: none;
    border: none;
    font-size: 0.9rem;
    color: var(--text, #333);
    cursor: pointer;
    padding: 0.5rem 1rem;
    border-radius: 8px;
  }

  .action-btn:hover {
    background: rgba(0,0,0,0.05);
  }

  .action-btn.active {
    background: var(--accent, #ff8c42);
    color: var(--bg, #fff);
  }

  /* Desktop: adjust layout slightly if needed */
  @media (min-width: 769px) {
    .action-bar.panel-open {
      right: var(--context-panel-width, 400px); /* leaves room for ContextPanel */
    }
  }
</style>
