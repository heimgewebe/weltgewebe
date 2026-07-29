<script lang="ts">
  export let id: string;
  export let label: string;
  export let level: 2 | 3 | 4 | 5 | 6 = 3;

  function openFromLongPress(event: MouseEvent) {
    event.preventDefault();
    (event.currentTarget as HTMLElement | null)?.parentElement?.setAttribute(
      "open",
      "",
    );
  }

  function closeDetails(details: HTMLDetailsElement | null) {
    if (!details) return;
    details.removeAttribute("open");
    details.querySelector<HTMLElement>("summary")?.focus();
  }

  function close(event: MouseEvent) {
    closeDetails(
      (event.currentTarget as HTMLElement | null)?.closest("details") ?? null,
    );
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key !== "Escape" || event.repeat || event.defaultPrevented)
      return;
    const details = event.currentTarget as HTMLDetailsElement;
    if (!details.open) return;
    event.preventDefault();
    event.stopPropagation();
    closeDetails(details);
  }
</script>

<details class="info-heading" on:keydown={handleKeydown}>
  <summary
    aria-controls={`${id}-explanation`}
    on:contextmenu={openFromLongPress}
  >
    <span {id} class="info-heading-title" role="heading" aria-level={level}
      >{label}</span
    >
  </summary>

  <div
    id={`${id}-explanation`}
    class="info-heading-panel"
    role="dialog"
    aria-labelledby={id}
  >
    <slot />
    <button type="button" on:click={close}>Schließen</button>
  </div>
</details>

<style>
  .info-heading {
    position: relative;
    anchor-scope: --info-heading-trigger;
  }

  summary {
    min-height: 44px;
    margin: -0.45rem 0;
    padding: 0.45rem 0.1rem;
    cursor: pointer;
    list-style: none;
    display: inline-flex;
    align-items: center;
    touch-action: manipulation;
    -webkit-touch-callout: none;
    anchor-name: --info-heading-trigger;
  }

  summary::-webkit-details-marker {
    display: none;
  }

  summary:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-radius: 4px;
  }

  .info-heading-title {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font: inherit;
    font-weight: inherit;
  }

  .info-heading-title::after {
    content: "ⓘ";
    color: var(--muted);
    font-size: 0.92em;
    line-height: 1;
  }

  summary:hover .info-heading-title::after,
  summary:focus-visible .info-heading-title::after {
    color: var(--accent);
  }

  .info-heading-panel {
    position: fixed;
    z-index: 30;
    top: 5rem;
    right: 1rem;
    width: min(24rem, calc(100vw - 2rem));
    padding: 0.75rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 10px;
    background: var(--panel-solid);
    color: var(--text);
    box-shadow: 0 10px 30px color-mix(in srgb, #000 22%, transparent);
  }

  .info-heading-panel :global(:first-child) {
    margin-top: 0;
  }

  .info-heading-panel :global(:last-child) {
    margin-bottom: 0;
  }

  button {
    min-height: 36px;
    margin: 0.7rem 0 0 auto;
    padding: 0.4rem 0.65rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 7px;
    background: var(--panel-solid);
    color: var(--text);
    font: inherit;
    cursor: pointer;
    display: block;
  }

  button:hover,
  button:focus-visible {
    border-color: var(--accent);
  }

  @supports (top: anchor(bottom)) {
    .info-heading-panel {
      position-anchor: --info-heading-trigger;
      top: anchor(bottom);
      right: auto;
      left: anchor(left);
      margin-top: 0.4rem;
      position-try-fallbacks:
        flip-inline,
        flip-block,
        flip-inline flip-block;
    }
  }

  @media (max-width: 40rem) {
    .info-heading-panel {
      top: auto;
      right: 0.75rem;
      bottom: calc(0.75rem + env(safe-area-inset-bottom));
      left: 0.75rem;
      width: auto;
      max-height: min(50vh, 24rem);
      margin-top: 0;
      overflow: auto;
      border-radius: 14px;
    }
  }
</style>
