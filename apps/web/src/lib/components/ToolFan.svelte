<script lang="ts">
  import { tick } from "svelte";
  import {
    contextPanelOpen,
    systemState,
    enterKomposition,
  } from "$lib/stores/uiView";
  import { isSearchOpen, closeSearch } from "$lib/stores/searchStore";
  import {
    isFilterOpen,
    activeFilters,
    closeFilter,
  } from "$lib/stores/filterStore";
  import {
    toggleSearchExclusive,
    toggleFilterExclusive,
  } from "$lib/stores/overlayManager";
  import {
    setRestoreTarget,
    suppressNextRestore,
  } from "$lib/utils/focusManager";
  import { authStore } from "$lib/auth/store";

  let open = false;
  let fanEl: HTMLDivElement;
  let triggerEl: HTMLButtonElement;

  $: canCreateNode = $authStore.role === "weber" || $authStore.role === "admin";
  $: activeFilterCount = $activeFilters.size;

  function closeFan(restoreFocus = false) {
    if (!open) return;
    open = false;
    if (restoreFocus) tick().then(() => triggerEl?.focus());
  }

  function toggleFan() {
    open = !open;
  }

  function onFind() {
    if (triggerEl) setRestoreTarget("search", triggerEl);
    toggleSearchExclusive();
    closeFan();
  }

  function onSight() {
    if (triggerEl) setRestoreTarget("filter", triggerEl);
    toggleFilterExclusive();
    closeFan();
  }

  function onWeave() {
    if (!canCreateNode) return;
    if ($isSearchOpen) suppressNextRestore("search");
    if ($isFilterOpen) suppressNextRestore("filter");
    closeSearch();
    closeFilter();
    enterKomposition({ mode: "new-knoten", source: "tool-fan" });
    closeFan();
  }

  function handleWindowPointerDown(event: PointerEvent) {
    if (!open || !fanEl) return;
    if (!fanEl.contains(event.target as Node)) closeFan();
  }

  function handleWindowKeydown(event: KeyboardEvent) {
    if (!open || event.defaultPrevented || event.repeat) return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeFan(true);
    }
  }
</script>

<svelte:window
  on:pointerdown={handleWindowPointerDown}
  on:keydown={handleWindowKeydown}
/>

<div
  class="tool-fan"
  class:panel-open={$contextPanelOpen}
  class:expanded={open}
  bind:this={fanEl}
  data-testid="tool-fan"
  data-expanded={open ? "true" : "false"}
>
  <button
    type="button"
    class="fan-trigger"
    bind:this={triggerEl}
    data-testid="tool-fan-trigger"
    aria-label={open ? "Werkzeuge schließen" : "Werkzeuge öffnen"}
    aria-expanded={open}
    aria-controls="tool-fan-actions"
    on:click={toggleFan}
  >
    <span class="trigger-symbol" aria-hidden="true">{open ? "×" : "✣"}</span>
    <span class="trigger-label">Werkzeuge</span>
  </button>

  <div
    id="tool-fan-actions"
    class="fan-menu"
    class:open
    role="group"
    aria-label="Werkzeugfächer"
    aria-hidden={!open}
  >
    <button
      type="button"
      class="fan-action fan-action--find"
      class:active={$isSearchOpen}
      data-testid="tool-fan-find"
      aria-label="Finden"
      aria-pressed={$isSearchOpen}
      tabindex={open ? 0 : -1}
      on:click={onFind}
    >
      <span class="fan-symbol" aria-hidden="true">⌕</span>
      <span>Finden</span>
    </button>

    <button
      type="button"
      class="fan-action fan-action--sight"
      class:active={$isFilterOpen}
      data-testid="tool-fan-sight"
      aria-label="Sicht"
      aria-pressed={$isFilterOpen}
      tabindex={open ? 0 : -1}
      on:click={onSight}
    >
      <span class="fan-symbol" aria-hidden="true">◉</span>
      <span>Sicht</span>
      {#if activeFilterCount > 0}
        <span class="count-badge" aria-label={`${activeFilterCount} aktiv`}
          >{activeFilterCount}</span
        >
      {/if}
    </button>

    <button
      type="button"
      class="fan-action fan-action--weave"
      class:active={$systemState === "komposition"}
      data-testid="tool-fan-weave"
      aria-label={canCreateNode
        ? "Weben"
        : "Weben – Weber-Garnrolle erforderlich"}
      aria-pressed={$systemState === "komposition"}
      disabled={!canCreateNode}
      title={canCreateNode
        ? "Knoten knüpfen"
        : "Zum Weben ist eine Weber-Garnrolle nötig"}
      tabindex={open && canCreateNode ? 0 : -1}
      on:click={onWeave}
    >
      <span class="fan-symbol" aria-hidden="true">⌁</span>
      <span>{canCreateNode ? "Weben" : "Weben · Weberstatus nötig"}</span>
    </button>

    <a
      class="governance-link"
      href="/antraege"
      data-testid="tool-fan-proposals"
      tabindex={open ? 0 : -1}>Anträge</a
    >
  </div>
</div>

<style>
  .tool-fan {
    position: fixed;
    right: calc(var(--tool-fan-edge) + env(safe-area-inset-right));
    bottom: calc(var(--tool-fan-edge) + env(safe-area-inset-bottom));
    width: var(--tool-fan-open-width);
    height: var(--tool-fan-open-height);
    z-index: var(--z-map-tool-fan);
    pointer-events: none;
    transition: right var(--motion-ui);
  }

  .fan-trigger,
  .fan-action,
  .governance-link {
    pointer-events: auto;
  }

  .fan-trigger {
    position: absolute;
    right: 0;
    bottom: 0;
    min-width: var(--tool-fan-collapsed-width);
    min-height: var(--tool-fan-size);
    padding: 0 0.9rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 999px;
    background: rgba(20, 22, 28, 0.94);
    color: var(--text);
    box-shadow: var(--shadow);
    backdrop-filter: blur(12px);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.45rem;
    font-weight: 700;
    cursor: pointer;
  }

  .trigger-symbol {
    font-size: 1.2rem;
    line-height: 1;
  }

  .fan-menu {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  .fan-action,
  .governance-link {
    position: absolute;
    right: 0;
    bottom: 0;
    min-height: 44px;
    border: 1px solid var(--panel-border-strong);
    border-radius: 999px;
    background: rgba(20, 22, 28, 0.96);
    color: var(--text);
    box-shadow: var(--shadow);
    backdrop-filter: blur(12px);
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transform: translate(0, 0) scale(0.76);
    transition:
      transform var(--motion-fan),
      opacity 0.14s ease,
      visibility 0s linear 0.18s;
  }

  .fan-action {
    min-width: 106px;
    padding: 0 0.85rem;
    display: inline-flex;
    align-items: center;
    justify-content: flex-start;
    gap: 0.5rem;
    font: inherit;
    font-weight: 700;
    cursor: pointer;
  }

  .fan-symbol {
    width: 1.1rem;
    text-align: center;
    color: var(--accent);
    font-size: 1.05rem;
  }

  .fan-menu.open .fan-action,
  .fan-menu.open .governance-link {
    opacity: 1;
    visibility: visible;
    pointer-events: auto;
    transition-delay: 0s;
  }

  .fan-menu.open .governance-link {
    transform: scale(1);
  }

  .fan-menu.open .fan-action--find {
    transform: translate(var(--tool-fan-find-x), var(--tool-fan-find-y)) scale(1);
  }

  .fan-menu.open .fan-action--sight {
    transform: translate(var(--tool-fan-sight-x), var(--tool-fan-sight-y)) scale(1);
  }

  .fan-menu.open .fan-action--weave {
    transform: translate(var(--tool-fan-weave-x), var(--tool-fan-weave-y)) scale(1);
  }

  .fan-action.active {
    border-color: var(--accent);
    background: var(--accent-soft);
  }

  .fan-action:disabled {
    width: 180px;
    min-width: 180px;
    box-sizing: border-box;
    cursor: not-allowed;
    opacity: 0.68;
    font-size: 0.8rem;
  }

  .count-badge {
    display: grid;
    place-items: center;
    min-width: 1.25rem;
    height: 1.25rem;
    margin-left: auto;
    padding: 0 0.25rem;
    border-radius: 999px;
    background: var(--accent);
    color: var(--bg);
    font-size: 0.72rem;
    font-variant-numeric: tabular-nums;
  }

  .governance-link {
    top: 0;
    left: 0;
    right: auto;
    bottom: auto;
    min-height: 44px;
    padding: 0 0.85rem;
    display: inline-flex;
    align-items: center;
    color: var(--muted);
    text-decoration: none;
    font-size: 0.82rem;
  }

  .fan-trigger:hover,
  .fan-action:hover:not(:disabled),
  .governance-link:hover {
    border-color: var(--accent);
    background: rgba(32, 42, 54, 0.98);
  }

  .fan-trigger:focus-visible,
  .fan-action:focus-visible,
  .governance-link:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 3px;
  }

  @media (max-width: 768px) {
    .tool-fan.panel-open {
      display: none;
    }
  }

  @media (min-width: 769px) {
    .tool-fan.panel-open {
      right: calc(
        var(--context-panel-width) + var(--tool-fan-edge) +
          env(safe-area-inset-right)
      );
    }
  }

  @media (max-width: 420px) {
    .trigger-label {
      font-size: 0.82rem;
    }
  }

  @media (prefers-reduced-transparency: reduce) {
    .fan-trigger,
    .fan-action,
    .governance-link {
      background: var(--panel-solid);
      backdrop-filter: none;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .tool-fan,
    .fan-action,
    .governance-link {
      transition: none;
    }
  }
</style>
