<script lang="ts">
  import { flip } from "svelte/animate";
  import { onMount } from "svelte";
  import {
    accountAttentionRuntime,
    retainAccountAttentionRuntime,
  } from "$lib/accountAttentionRuntime";
  import { setAttentionOverflowOpen } from "$lib/stores/mapChrome";
  import { unreadMessageBadgeLabel } from "./topBarAttentionState";

  let controlCapacity = $state(3);
  let reducedMotion = $state(false);
  let overflowOpen = $state(false);

  let visibleCount = $derived.by(() => {
    const total = $accountAttentionRuntime.items.length;
    return total <= controlCapacity ? total : Math.max(1, controlCapacity - 1);
  });
  let visibleItems = $derived(
    $accountAttentionRuntime.items.slice(0, visibleCount),
  );
  let hiddenItems = $derived(
    $accountAttentionRuntime.items.slice(visibleCount),
  );

  function attentionSymbol(kind: string): string {
    switch (kind) {
      case "direct_message":
        return "✉";
      case "weber_application":
        return "◌";
      default:
        return "◇";
    }
  }

  function syncViewportState(): void {
    const topbar = document.querySelector<HTMLElement>(".topbar");
    const topbarWidth =
      topbar?.getBoundingClientRect().width ?? window.innerWidth;
    const rootFontSize =
      Number.parseFloat(getComputedStyle(document.documentElement).fontSize) ||
      16;
    const gap = rootFontSize * 0.35;
    const leftTrackWidth = Math.max(44, (topbarWidth - 24) / 2);
    controlCapacity = Math.max(
      2,
      Math.min(7, Math.floor((leftTrackWidth + gap) / (44 + gap))),
    );
  }

  $effect(() => {
    setAttentionOverflowOpen(hiddenItems.length > 0 && overflowOpen);
  });

  onMount(() => {
    const releaseRuntime = retainAccountAttentionRuntime();
    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const syncMotion = () => {
      reducedMotion = motionQuery.matches;
    };
    const topbar = document.querySelector<HTMLElement>(".topbar");
    const resizeObserver = new ResizeObserver(syncViewportState);
    if (topbar) resizeObserver.observe(topbar);
    syncViewportState();
    syncMotion();
    motionQuery.addEventListener("change", syncMotion);

    return () => {
      setAttentionOverflowOpen(false);
      releaseRuntime();
      resizeObserver.disconnect();
      motionQuery.removeEventListener("change", syncMotion);
    };
  });
</script>

{#if $accountAttentionRuntime.items.length > 0}
  <nav
    class="attention-bubbles"
    data-testid="attention-bubbles"
    aria-label="Aktuelle Aufmerksamkeit"
  >
    <div class="attention-row">
      {#each visibleItems as item (item.id)}
        <a
          class="attention-bubble"
          class:personal={item.kind !== "governance"}
          data-attention-id={item.id}
          data-attention-kind={item.kind}
          href={item.href}
          aria-label={`${item.label}: ${item.detail}`}
          title={`${item.label} · ${item.detail}`}
          animate:flip={{ duration: reducedMotion ? 0 : 170 }}
        >
          <span class="attention-symbol" aria-hidden="true">
            {attentionSymbol(item.kind)}
          </span>
          {#if item.count && item.count > 1}
            <span class="attention-count" aria-hidden="true">
              {unreadMessageBadgeLabel(item.count)}
            </span>
          {/if}
        </a>
      {/each}

      {#if hiddenItems.length > 0}
        <details class="attention-overflow" bind:open={overflowOpen}>
          <summary
            class="attention-overflow-trigger"
            aria-label={`${hiddenItems.length} weitere Aufmerksamkeitseinheiten`}
          >
            +{hiddenItems.length}
          </summary>
          <div
            class="attention-overflow-menu"
            data-testid="attention-overflow-menu"
          >
            {#each hiddenItems as item (item.id)}
              <a
                class="attention-overflow-item"
                href={item.href}
                data-attention-id={item.id}
              >
                <span class="overflow-symbol" aria-hidden="true">
                  {attentionSymbol(item.kind)}
                </span>
                <span class="overflow-copy">
                  <strong>{item.label}</strong>
                  <span>{item.detail}</span>
                </span>
                {#if item.count && item.count > 1}
                  <span class="overflow-count">
                    {unreadMessageBadgeLabel(item.count)}
                  </span>
                {/if}
              </a>
            {/each}
          </div>
        </details>
      {/if}
    </div>
  </nav>
{/if}

<style>
  .attention-bubbles {
    grid-column: 1;
    justify-self: start;
    min-width: 0;
    pointer-events: auto;
  }

  .attention-row {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    min-width: 0;
  }

  .attention-bubble,
  .attention-overflow-trigger {
    box-sizing: border-box;
    position: relative;
    display: grid;
    place-items: center;
    width: 44px;
    min-width: 44px;
    height: 44px;
    padding: 0;
    border: 1px solid var(--panel-border-strong);
    border-radius: 50%;
    background: var(--panel);
    color: var(--text);
    box-shadow: var(--shadow);
    backdrop-filter: blur(var(--map-lens-blur));
    text-decoration: none;
    cursor: pointer;
  }

  .attention-bubble.personal {
    border-color: color-mix(
      in srgb,
      var(--accent) 65%,
      var(--panel-border-strong)
    );
  }

  .attention-symbol {
    font-size: 1.08rem;
    line-height: 1;
  }

  .attention-count {
    position: absolute;
    top: -0.3rem;
    right: -0.35rem;
    box-sizing: border-box;
    display: grid;
    place-items: center;
    min-width: 1.2rem;
    height: 1.2rem;
    padding: 0 0.18rem;
    border: 2px solid var(--panel);
    border-radius: 999px;
    background: var(--accent);
    color: var(--accent-contrast, #fff);
    font-size: 0.62rem;
    font-weight: 800;
    line-height: 1;
  }

  .attention-overflow {
    position: relative;
  }

  .attention-overflow > summary {
    list-style: none;
  }

  .attention-overflow > summary::-webkit-details-marker {
    display: none;
  }

  .attention-overflow-trigger {
    font: inherit;
    font-size: 0.72rem;
    font-weight: 800;
  }

  .attention-overflow-menu {
    box-sizing: border-box;
    position: absolute;
    top: calc(100% + 8px);
    left: 0;
    width: min(290px, calc(100vw - 24px));
    max-height: min(55vh, 360px);
    overflow: auto;
    display: grid;
    gap: 0.25rem;
    padding: 0.4rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 16px;
    background: var(--panel);
    box-shadow: var(--shadow);
    backdrop-filter: blur(var(--map-lens-blur));
  }

  .attention-overflow-item {
    box-sizing: border-box;
    display: grid;
    grid-template-columns: 32px minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.5rem;
    min-height: 44px;
    padding: 0.35rem 0.45rem;
    border-radius: 12px;
    color: var(--text);
    text-decoration: none;
  }

  .attention-overflow-item:hover {
    background: var(--accent-soft);
  }

  .overflow-symbol {
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    border: 1px solid var(--panel-border-strong);
    border-radius: 50%;
  }

  .overflow-copy {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
  }

  .overflow-copy strong,
  .overflow-copy span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .overflow-copy strong {
    font-size: 0.78rem;
  }

  .overflow-copy span {
    color: var(--text-muted, var(--text));
    font-size: 0.7rem;
  }

  .overflow-count {
    min-width: 1.5rem;
    padding: 0.2rem 0.35rem;
    border-radius: 999px;
    background: var(--accent-soft);
    color: var(--accent);
    font-size: 0.68rem;
    font-weight: 800;
    text-align: center;
  }

  .attention-bubble:focus-visible,
  .attention-overflow-trigger:focus-visible,
  .attention-overflow-item:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 3px;
  }

  @media (prefers-reduced-transparency: reduce) {
    .attention-bubble,
    .attention-overflow-trigger,
    .attention-overflow-menu {
      background: var(--panel-solid);
      backdrop-filter: none;
    }
  }

  @media (prefers-reduced-motion: no-preference) {
    .attention-bubble {
      animation: attention-arrive 150ms ease-out;
    }
  }

  @keyframes attention-arrive {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
</style>
