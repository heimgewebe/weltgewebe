<script lang="ts">
  import { tick } from "svelte";
  import { goto } from "$app/navigation";
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
  import {
    closeMapFan,
    expandedMapFan,
    toggleMapFan,
  } from "$lib/stores/mapChrome";
  import FanAction from "./FanAction.svelte";
  import { TOOL_ACTION_IDS } from "./mapUiActions";

  let fanEl: HTMLDivElement;
  let triggerEl: HTMLButtonElement;

  $: open = $expandedMapFan === "tools";
  $: canCreateNode = $authStore.role === "weber" || $authStore.role === "admin";
  $: activeFilterCount = $activeFilters.size;

  function announceGeometryChange() {
    tick().then(() =>
      window.dispatchEvent(new CustomEvent("map-ui-geometry-change")),
    );
  }

  function closeFan(restoreFocus = false) {
    if (!open) return;
    closeMapFan("tools");
    announceGeometryChange();
    if (restoreFocus) tick().then(() => triggerEl?.focus());
  }

  function toggleFan() {
    if (!open) {
      if ($isSearchOpen) suppressNextRestore("search");
      if ($isFilterOpen) suppressNextRestore("filter");
      closeSearch();
      closeFilter();
    }
    toggleMapFan("tools");
    announceGeometryChange();
  }

  function onFind() {
    if (triggerEl) setRestoreTarget("search", triggerEl);
    toggleSearchExclusive();
    closeFan();
  }

  function onContent() {
    if (triggerEl) setRestoreTarget("filter", triggerEl);
    toggleFilterExclusive();
    closeFan();
  }

  function onWeave() {
    if (!canCreateNode) return;
    closeSearch();
    closeFilter();
    enterKomposition({ mode: "new-knoten", source: "tool-fan" });
    closeFan();
  }

  async function onApply() {
    closeFan();
    await goto("/antraege?intent=stellen#antrag-stellen");
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

  function handleFocusOut(event: FocusEvent) {
    if (!open) return;
    const next = event.relatedTarget as Node | null;
    if (next && fanEl.contains(next)) return;
    tick().then(() => {
      if (!fanEl.contains(document.activeElement)) closeFan();
    });
  }
</script>

<svelte:window
  on:pointerdown={handleWindowPointerDown}
  on:keydown={handleWindowKeydown}
/>

<div
  class="tool-fan"
  class:panel-open={$contextPanelOpen}
  bind:this={fanEl}
  data-testid="tool-fan"
  data-expanded={open ? "true" : "false"}
  on:focusout={handleFocusOut}
>
  <button
    type="button"
    class="fan-trigger"
    bind:this={triggerEl}
    data-testid="tool-fan-trigger"
    aria-label={open ? "Werkzeugfächer schließen" : "Werkzeugfächer öffnen"}
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
    data-testid="tool-fan-actions"
    role="group"
    aria-label="Webungswerkzeuge"
    aria-hidden={!open}
  >
    <div class="fan-branch fan-branch--find">
      <FanAction
        id={TOOL_ACTION_IDS.find}
        label="Finden"
        symbol="⌕"
        {open}
        active={$isSearchOpen}
        pressed={$isSearchOpen}
        on:activate={onFind}
      />
    </div>
    <div class="fan-branch fan-branch--content">
      <FanAction
        id={TOOL_ACTION_IDS.content}
        label="Karteninhalt"
        symbol="◉"
        {open}
        active={$isFilterOpen}
        pressed={$isFilterOpen}
        count={activeFilterCount}
        on:activate={onContent}
      />
    </div>
    <div class="fan-branch fan-branch--weave">
      <FanAction
        id={TOOL_ACTION_IDS.weave}
        label={canCreateNode
          ? "Knoten knüpfen"
          : "Knoten knüpfen · Weberstatus nötig"}
        symbol="⌁"
        {open}
        active={$systemState === "komposition"}
        pressed={$systemState === "komposition"}
        disabled={!canCreateNode}
        ariaLabel={canCreateNode
          ? undefined
          : "Knoten knüpfen – Weber-Garnrolle erforderlich"}
        title={canCreateNode
          ? "Knoten knüpfen"
          : "Zum Knüpfen ist eine Weber-Garnrolle nötig"}
        on:activate={onWeave}
      />
    </div>
    <div class="fan-branch fan-branch--apply">
      <FanAction
        id={TOOL_ACTION_IDS.apply}
        label="Antrag stellen"
        symbol="＋"
        {open}
        title="Verfügbare Antragsaktion öffnen"
        on:activate={onApply}
      />
    </div>
  </div>
</div>

<style>
  .tool-fan {
    position: fixed;
    left: 50%;
    bottom: calc(var(--tool-fan-edge) + env(safe-area-inset-bottom));
    z-index: var(--z-map-tool-fan);
    transform: translateX(-50%);
    transition: left var(--motion-ui);
  }

  .fan-trigger {
    min-width: var(--tool-fan-collapsed-width);
    min-height: var(--tool-fan-size);
    padding: 0 0.9rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 999px;
    background: var(--map-control-bg);
    color: var(--text);
    box-shadow: var(--shadow);
    backdrop-filter: blur(var(--map-control-blur));
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.45rem;
    font: inherit;
    font-weight: 700;
    cursor: pointer;
  }

  .fan-menu {
    position: absolute;
    left: 50%;
    bottom: calc(100% + var(--map-fan-gap));
    width: min(var(--tool-fan-menu-max-width), calc(100vw - 24px));
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    align-items: end;
    gap: var(--map-fan-action-gap);
    padding-top: 0.45rem;
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transform: translate(-50%, 10px) scale(0.96);
    transform-origin: bottom center;
    transition:
      transform var(--motion-fan),
      opacity var(--motion-fan-opacity),
      visibility 0s linear var(--motion-fan-duration);
  }

  .fan-menu::after {
    content: "";
    position: absolute;
    left: 50%;
    bottom: calc(-1 * var(--map-fan-gap));
    width: 1px;
    height: var(--map-fan-gap);
    background: var(--panel-border-strong);
  }

  .fan-menu.open {
    opacity: 1;
    visibility: visible;
    pointer-events: auto;
    transform: translate(-50%, 0) scale(1);
    transition-delay: 0s;
  }

  .fan-branch {
    display: flex;
    transition: transform var(--motion-fan);
  }

  .fan-branch:nth-child(1),
  .fan-branch:nth-child(4) {
    transform: translateY(10px);
  }

  .fan-branch:nth-child(2),
  .fan-branch:nth-child(3) {
    transform: translateY(-6px);
  }

  .trigger-symbol {
    font-size: 1.2rem;
    line-height: 1;
  }

  .fan-trigger:hover,
  .fan-trigger:focus-visible {
    border-color: var(--accent);
    background: var(--map-control-bg-hover);
  }

  .fan-trigger:focus-visible {
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
      left: calc((100vw - var(--context-panel-width)) / 2);
    }
  }

  @media (max-width: 620px) {
    .fan-menu {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      align-items: stretch;
      padding-top: 0;
    }

    .fan-branch,
    .fan-branch:nth-child(1),
    .fan-branch:nth-child(2),
    .fan-branch:nth-child(3),
    .fan-branch:nth-child(4) {
      transform: none;
    }

    .fan-branch :global(.fan-action) {
      width: 100%;
    }
  }

  @media (max-width: 420px) {
    .trigger-label {
      font-size: 0.82rem;
    }
  }

  @media (prefers-reduced-transparency: reduce) {
    .fan-trigger {
      background: var(--panel-solid);
      backdrop-filter: none;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .tool-fan,
    .fan-menu,
    .fan-branch {
      transition: none;
    }
  }
</style>
