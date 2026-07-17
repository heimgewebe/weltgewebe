<script lang="ts">
  import { tick } from "svelte";
  import { isSearchOpen, closeSearch } from "$lib/stores/searchStore";
  import { isFilterOpen, closeFilter } from "$lib/stores/filterStore";
  import { suppressNextRestore } from "$lib/utils/focusManager";
  import { closeMapFan, expandedMapFan, toggleMapFan } from "$lib/stores/mapChrome";
  import { GOVERNANCE_EVENTS } from "./mapUiActions";

  let fanEl: HTMLDivElement;
  let triggerEl: HTMLButtonElement;
  $: open = $expandedMapFan === "governance";

  function announceGeometryChange() {
    tick().then(() => window.dispatchEvent(new CustomEvent("map-ui-geometry-change")));
  }

  function closeFan(restoreFocus = false) {
    if (!open) return;
    closeMapFan("governance");
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
    toggleMapFan("governance");
    announceGeometryChange();
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

<svelte:window on:pointerdown={handleWindowPointerDown} on:keydown={handleWindowKeydown} />

<div class="governance-fan" bind:this={fanEl} data-testid="governance-fan" data-expanded={open ? "true" : "false"} on:focusout={handleFocusOut}>
  <button
    type="button"
    class="governance-trigger"
    bind:this={triggerEl}
    data-testid="governance-fan-trigger"
    aria-label={open ? "Gemeinschaftsfächer schließen" : "Gemeinschaftsfächer öffnen"}
    aria-expanded={open}
    aria-controls="governance-fan-events"
    on:click={toggleFan}
  >
    <span aria-hidden="true">{open ? "×" : "◎"}</span>
    <span>Gemeinschaft</span>
  </button>

  <nav
    id="governance-fan-events"
    class="governance-events"
    class:open
    data-testid="governance-fan-actions"
    aria-label="Gemeinsame Entscheidungen"
    aria-hidden={!open}
  >
    {#each GOVERNANCE_EVENTS as event}
      <a href={event.href} data-testid={"governance-fan-" + event.id} tabindex={open ? 0 : -1} on:click={() => closeFan()}>
        <span aria-hidden="true">{event.symbol}</span>
        <span>{event.label}</span>
      </a>
    {/each}
  </nav>
</div>

<style>
  .governance-fan {
    position: relative;
    z-index: var(--z-map-governance-fan);
  }

  .governance-trigger {
    min-height: 44px;
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

  .governance-events {
    position: absolute;
    top: calc(100% + var(--map-fan-gap));
    left: 50%;
    width: min(600px, calc(100vw - 24px));
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: var(--map-fan-action-gap);
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transform: translate(-50%, -10px) scale(0.96);
    transform-origin: top center;
    transition:
      transform var(--motion-fan),
      opacity var(--motion-fan-opacity),
      visibility 0s linear var(--motion-fan-duration);
  }

  .governance-events::before {
    content: "";
    position: absolute;
    top: calc(-1 * var(--map-fan-gap));
    left: 50%;
    width: 1px;
    height: var(--map-fan-gap);
    background: var(--panel-border-strong);
  }

  .governance-events.open {
    opacity: 1;
    visibility: visible;
    pointer-events: auto;
    transform: translate(-50%, 0) scale(1);
    transition-delay: 0s;
  }

  .governance-events a {
    min-width: 132px;
    min-height: 44px;
    box-sizing: border-box;
    padding: 0 0.85rem;
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
    text-decoration: none;
    font-weight: 700;
  }

  .governance-trigger:hover,
  .governance-trigger:focus-visible,
  .governance-events a:hover,
  .governance-events a:focus-visible {
    border-color: var(--accent);
    background: var(--map-control-bg-hover);
  }

  .governance-trigger:focus-visible,
  .governance-events a:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 3px;
  }

  @media (max-width: 520px) {
    .governance-trigger { padding-inline: 0.7rem; font-size: 0.82rem; }
    .governance-events a {
      min-width: min(176px, calc(50vw - 16px));
      font-size: 0.82rem;
    }
  }

  @media (prefers-reduced-transparency: reduce) {
    .governance-trigger,
    .governance-events a {
      background: var(--panel-solid);
      backdrop-filter: none;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .governance-events { transition: none; }
  }
</style>
