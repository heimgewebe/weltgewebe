<script lang="ts">
  import {
    contextPanelOpen,
    systemState,
    enterKomposition,
  } from "$lib/stores/uiView";
  import { isSearchOpen, closeSearch } from "$lib/stores/searchStore";
  import { isFilterOpen, closeFilter } from "$lib/stores/filterStore";
  import {
    toggleSearchExclusive,
    toggleFilterExclusive,
  } from "$lib/stores/overlayManager";
  import {
    setRestoreTarget,
    suppressNextRestore,
  } from "$lib/utils/focusManager";
  import { authStore } from "$lib/auth/store";

  $: canCreateNode = $authStore.role === "weber" || $authStore.role === "admin";

  function onNewNode() {
    if ($isSearchOpen) suppressNextRestore("search");
    if ($isFilterOpen) suppressNextRestore("filter");
    closeSearch();
    closeFilter();
    enterKomposition({ mode: "new-knoten", source: "action-bar" });
  }

  let searchBtnEl: HTMLButtonElement;
  let filterBtnEl: HTMLButtonElement;

  function onToggleSearch() {
    if (searchBtnEl) setRestoreTarget("search", searchBtnEl);
    toggleSearchExclusive();
  }

  function onToggleFilter() {
    if (filterBtnEl) setRestoreTarget("filter", filterBtnEl);
    toggleFilterExclusive();
  }
</script>

<nav
  class="action-bar"
  class:panel-open={$contextPanelOpen}
  aria-label="Aktionsleiste"
>
  {#if canCreateNode}
    <button
      class="action-btn"
      class:active={$systemState === "komposition"}
      on:click={onNewNode}
      aria-label="Knoten knüpfen">Knoten knüpfen</button
    >
  {/if}
  <button
    bind:this={searchBtnEl}
    class="action-btn"
    on:click={onToggleSearch}
    class:active={$isSearchOpen}
    aria-label="Suche">Suche</button
  >
  <button
    bind:this={filterBtnEl}
    class="action-btn"
    class:active={$isFilterOpen}
    on:click={onToggleFilter}
    aria-label="Filter">Filter</button
  >
</nav>

<style>
  .action-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: var(--actionbar-base-height);
    background: var(--panel);
    border-top: var(--actionbar-border-width) solid var(--panel-border);
    display: flex;
    justify-content: space-around;
    align-items: center;
    z-index: 40;
    padding: 0 1rem env(safe-area-inset-bottom);
    box-shadow: var(--shadow);
    box-sizing: content-box;
  }

  .action-btn {
    background: none;
    border: none;
    font-size: 0.9rem;
    color: var(--text);
    cursor: pointer;
    padding: 0.5rem 1rem;
    border-radius: 8px;
    min-height: 44px;
    min-width: 44px;
  }

  .action-btn:hover {
    background: var(--accent-soft);
  }
  .action-btn:active {
    transform: scale(0.96);
  }
  .action-btn.active {
    background: var(--accent);
    color: var(--bg);
  }

  @media (max-width: 768px) {
    .action-bar.panel-open {
      display: none;
    }
  }

  @media (min-width: 769px) {
    .action-bar.panel-open {
      right: var(--context-panel-width);
    }
  }
</style>
