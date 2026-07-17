<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { ToolActionId } from "./mapUiActions";

  export let id: ToolActionId;
  export let label: string;
  export let symbol: string;
  export let open = false;
  export let active = false;
  export let pressed: boolean | undefined = undefined;
  export let disabled = false;
  export let title: string | undefined = undefined;
  export let ariaLabel: string | undefined = undefined;
  export let count = 0;

  const dispatch = createEventDispatcher<{ activate: void }>();
</script>

<button
  type="button"
  class="fan-action"
  class:active
  data-testid={"tool-fan-" + id}
  aria-label={ariaLabel}
  aria-pressed={pressed}
  {disabled}
  {title}
  tabindex={open && !disabled ? 0 : -1}
  on:click={() => dispatch("activate")}
>
  <span class="fan-symbol" aria-hidden="true">{symbol}</span>
  <span class="fan-label">{label}</span>
  {#if count > 0}
    <span class="count-badge" aria-hidden="true">{count}</span>
    <span class="sr-only">
      {count} {count === 1 ? "Auswahl" : "Auswahlen"} aktiv
    </span>
  {/if}
</button>

<style>
  .fan-action {
    min-width: 118px;
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
    justify-content: flex-start;
    gap: 0.5rem;
    font: inherit;
    font-weight: 700;
    cursor: pointer;
  }

  .fan-action.active {
    border-color: var(--accent);
    background: var(--accent-soft);
  }

  .fan-action:hover:not(:disabled),
  .fan-action:focus-visible {
    border-color: var(--accent);
    background: var(--map-control-bg-hover);
  }

  .fan-action:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 3px;
  }

  .fan-action:disabled {
    cursor: not-allowed;
    opacity: 0.62;
  }

  .fan-symbol {
    width: 1.1rem;
    flex: 0 0 auto;
    text-align: center;
    color: var(--accent);
    font-size: 1.05rem;
  }

  .fan-label {
    min-width: 0;
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

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  @media (max-width: 520px) {
    .fan-action {
      min-width: min(164px, calc(50vw - 16px));
      max-width: min(164px, calc(50vw - 16px));
      padding-inline: 0.7rem;
      font-size: 0.82rem;
    }
  }

  @media (prefers-reduced-transparency: reduce) {
    .fan-action {
      background: var(--panel-solid);
      backdrop-filter: none;
    }
  }
</style>
