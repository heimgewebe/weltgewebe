<script lang="ts">
  interface Props {
    label: string;
    symbol: string;
    testId: string;
    href?: string | null;
    active?: boolean | undefined;
    disabled?: boolean;
    tabIndex?: number;
    ariaLabel?: string | undefined;
    title?: string | undefined;
    onclick?: (event: MouseEvent) => void;
    children?: import("svelte").Snippet;
  }

  let {
    label,
    symbol,
    testId,
    href = null,
    active = undefined,
    disabled = false,
    tabIndex = 0,
    ariaLabel = undefined,
    title = undefined,
    onclick,
    children,
  }: Props = $props();
</script>

{#if href && !disabled}
  <a
    class="fan-action"
    class:active={active === true}
    data-testid={testId}
    {href}
    aria-label={ariaLabel}
    aria-current={active === true ? "page" : undefined}
    tabindex={tabIndex}
    {title}
    {onclick}
  >
    <span class="fan-symbol" aria-hidden="true">{symbol}</span>
    <span class="fan-label">{label}</span>
    {@render children?.()}
  </a>
{:else}
  <button
    type="button"
    class="fan-action"
    class:active={active === true}
    data-testid={testId}
    aria-label={ariaLabel}
    aria-pressed={active === undefined ? undefined : active}
    {disabled}
    tabindex={tabIndex}
    {title}
    {onclick}
  >
    <span class="fan-symbol" aria-hidden="true">{symbol}</span>
    <span class="fan-label">{label}</span>
    {@render children?.()}
  </button>
{/if}

<style>
  .fan-action {
    box-sizing: border-box;
    min-width: 112px;
    min-height: 48px;
    padding: 0 0.85rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 999px;
    background: var(--panel);
    color: var(--text);
    box-shadow: var(--shadow);
    backdrop-filter: blur(var(--map-lens-blur));
    display: inline-flex;
    align-items: center;
    justify-content: flex-start;
    gap: 0.5rem;
    font: inherit;
    font-weight: 700;
    text-decoration: none;
    cursor: pointer;
    white-space: nowrap;
  }

  .fan-action.active {
    border-color: var(--accent);
    background: var(--accent-soft);
  }

  .fan-action:disabled {
    cursor: not-allowed;
    opacity: 0.58;
  }

  .fan-symbol {
    width: 1.1rem;
    flex: 0 0 1.1rem;
    color: var(--accent);
    text-align: center;
    font-size: 1.05rem;
  }

  .fan-label {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .fan-action:hover:not(:disabled) {
    border-color: var(--accent);
    background: var(--panel-solid);
  }

  .fan-action:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 3px;
  }

  @media (prefers-reduced-transparency: reduce) {
    .fan-action {
      background: var(--panel-solid);
      backdrop-filter: none;
    }
  }
</style>
