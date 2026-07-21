<script lang="ts">
  import { tick } from "svelte";
  import FanAction from "./FanAction.svelte";
  import { isSearchOpen, closeSearch } from "$lib/stores/searchStore";
  import { isFilterOpen, closeFilter } from "$lib/stores/filterStore";
  import {
    mapChrome,
    toggleGovernanceFan,
    closeGovernanceFan,
  } from "$lib/stores/mapChrome";
  import { suppressNextRestore } from "$lib/utils/focusManager";

  let fanEl: HTMLDivElement;
  let triggerEl: HTMLButtonElement;

  $: open = $mapChrome.governanceFanOpen;

  function closeLensesWithoutRestore(): void {
    if ($isSearchOpen) {
      suppressNextRestore("search");
      closeSearch();
    }
    if ($isFilterOpen) {
      suppressNextRestore("filter");
      closeFilter();
    }
  }

  function handleTrigger(): void {
    if (!open) closeLensesWithoutRestore();
    toggleGovernanceFan();
  }

  function closeFan(restoreFocus = false): void {
    if (!open) return;
    closeGovernanceFan();
    if (restoreFocus) tick().then(() => triggerEl?.focus());
  }

  function handleWindowPointerDown(event: PointerEvent): void {
    if (!open || !fanEl) return;
    if (!fanEl.contains(event.target as Node)) closeFan();
  }

  function handleWindowKeydown(event: KeyboardEvent): void {
    if (!open || event.defaultPrevented || event.repeat) return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeFan(true);
    }
  }

  function handleFocusOut(event: FocusEvent): void {
    if (!open) return;
    const next = event.relatedTarget as Node | null;
    if (next && fanEl.contains(next)) return;
    tick().then(() => {
      if (open && fanEl && !fanEl.contains(document.activeElement)) closeFan();
    });
  }
</script>

<svelte:window
  on:pointerdown={handleWindowPointerDown}
  on:keydown={handleWindowKeydown}
/>

<div
  class="governance-fan"
  bind:this={fanEl}
  data-testid="governance-fan"
  data-expanded={open ? "true" : "false"}
  on:focusout={handleFocusOut}
>
  <button
    type="button"
    class="governance-trigger"
    bind:this={triggerEl}
    data-testid="governance-fan-trigger"
    aria-label={open
      ? "Gemeinsame Entscheidungen schließen"
      : "Gemeinsame Entscheidungen öffnen"}
    aria-expanded={open}
    aria-controls="governance-fan-actions"
    on:click={handleTrigger}
  >
    <span>Mitentscheiden</span>
  </button>

  <div
    id="governance-fan-actions"
    class="governance-menu"
    class:open
    role="group"
    aria-label="Gemeinsame Entscheidungen"
    aria-hidden={!open}
  >
    <div class="governance-slot governance-slot--outer-left">
      <FanAction
        label="Alle Anträge"
        symbol="◇"
        testId="governance-fan-all"
        href="/antraege"
        tabIndex={open ? 0 : -1}
        on:click={() => closeGovernanceFan()}
      />
    </div>
    <div class="governance-slot governance-slot--inner-left">
      <FanAction
        label="Offene Anträge"
        symbol="◌"
        testId="governance-fan-open"
        href="/antraege?status=consent"
        tabIndex={open ? 0 : -1}
        on:click={() => closeGovernanceFan()}
      />
    </div>
    <div class="governance-slot governance-slot--center">
      <FanAction
        label="Vetos"
        symbol="!"
        testId="governance-fan-vetoes"
        href="/antraege?ereignis=veto"
        tabIndex={open ? 0 : -1}
        on:click={() => closeGovernanceFan()}
      />
    </div>
    <div class="governance-slot governance-slot--inner-right">
      <FanAction
        label="Gespräche"
        symbol="…"
        testId="governance-fan-conversations"
        href="/antraege?ereignis=gespraech"
        tabIndex={open ? 0 : -1}
        on:click={() => closeGovernanceFan()}
      />
    </div>
    <div class="governance-slot governance-slot--outer-right">
      <FanAction
        label="Abstimmungen"
        symbol="✓"
        testId="governance-fan-voting"
        href="/antraege?status=voting"
        tabIndex={open ? 0 : -1}
        on:click={() => closeGovernanceFan()}
      />
    </div>
  </div>
</div>

<style>
  .governance-fan {
    position: relative;
    z-index: var(--z-map-fan);
    pointer-events: auto;
  }

  .governance-trigger {
    min-width: 112px;
    min-height: 44px;
    padding: 0 0.8rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 999px;
    background: rgba(20, 22, 28, 0.88);
    color: var(--text);
    box-shadow: var(--shadow);
    backdrop-filter: blur(var(--map-lens-blur));
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.45rem;
    font: inherit;
    font-weight: 700;
    cursor: pointer;
  }

  .governance-menu {
    box-sizing: border-box;
    position: absolute;
    top: calc(100% + 10px);
    left: 50%;
    width: max-content;
    max-width: min(var(--governance-fan-menu-width), calc(100vw - 24px));
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: center;
    gap: 0.5rem;
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transform: translateX(-50%) translateY(-8px) scale(0.97);
    transform-origin: top center;
    transition:
      transform var(--motion-fan),
      opacity var(--motion-fan-fast),
      visibility 0s linear var(--motion-fan-duration);
  }

  .governance-menu.open {
    opacity: 1;
    visibility: visible;
    transform: translateX(-50%) translateY(0) scale(1);
    transition-delay: 0s;
  }

  .governance-menu :global(.fan-action) {
    pointer-events: auto;
  }

  .governance-slot--outer-left,
  .governance-slot--outer-right {
    transform: translateY(12px);
  }

  .governance-slot--inner-left,
  .governance-slot--inner-right {
    transform: translateY(5px);
  }

  .governance-trigger:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 3px;
  }

  @media (max-width: 900px) {
    .governance-menu :global(.fan-action) {
      min-width: 0;
      width: 92px;
      padding-inline: 0.5rem;
      font-size: 0.76rem;
      white-space: normal;
      text-align: left;
    }
  }

  @media (max-width: 520px) {
    .governance-menu {
      max-width: min(304px, calc(100vw - 16px));
      gap: 0.35rem;
    }
  }

  @media (prefers-reduced-transparency: reduce) {
    .governance-trigger {
      background: var(--panel-solid);
      backdrop-filter: none;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .governance-menu {
      transition: none;
    }
  }
</style>
