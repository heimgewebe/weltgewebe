<script lang="ts">
  import { selection } from '$lib/stores/uiView';
  import { slide } from 'svelte/transition';
  import { tick } from 'svelte';

  function close() {
    $selection = null;
  }

  // Manage focus when card opens
  let cardRef: HTMLElement;
  $: if ($selection && cardRef) {
    (async () => {
      await tick();
      cardRef?.focus();
    })();
  }
</script>

<style>
  .selection-card {
    position: absolute;
    z-index: 35;
    background: var(--panel);
    border: 1px solid var(--panel-border);
    box-shadow: var(--shadow);
    border-radius: var(--radius);
    padding: 16px;
    width: 300px;
    color: var(--text);
  }

  /* Desktop: Bottom Right */
  @media (min-width: 600px) {
    .selection-card {
      bottom: 80px;
      right: 12px;
    }
  }

  /* Mobile: Bottom (above dock) */
  @media (max-width: 599px) {
    .selection-card {
      bottom: 80px;
      left: 12px;
      right: 12px;
      width: auto;
    }
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 8px;
    gap: 8px;
  }

  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    line-height: 1.3;
  }

  .badge {
    display: inline-block;
    font-size: 11px;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 4px;
    background: var(--panel-border); /* fallback */
    background: rgba(125,125,125, 0.15);
    color: var(--muted);
    font-weight: 600;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
  }

  .close-btn {
    background: transparent;
    border: none;
    padding: 4px;
    cursor: pointer;
    color: var(--muted);
    font-size: 16px;
    line-height: 1;
    border-radius: 4px;
    flex-shrink: 0;
  }
  .close-btn:hover {
    background: rgba(0,0,0,0.05);
    color: var(--text);
  }

  .content {
    margin-bottom: 16px;
    font-size: 14px;
    color: var(--muted);
    line-height: 1.5;
    /* Limit to 2 lines */
    display: -webkit-box;
    line-clamp: 2;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .actions {
    display: flex;
    gap: 8px;
  }

  .ghost-btn {
    flex: 1;
    background: transparent;
    border: 1px solid var(--panel-border);
    border-radius: 6px;
    padding: 6px 12px;
    cursor: pointer;
    color: var(--text);
    font-size: 13px;
    font-weight: 500;
    text-align: center;
    transition: background 0.15s, border-color 0.15s;
  }
  .ghost-btn:hover {
    background: rgba(0,0,0,0.03);
    border-color: var(--muted);
  }
  .ghost-btn.primary {
    color: var(--accent);
    border-color: var(--accent);
    background: rgba(var(--accent-rgb), 0.05); /* if accent-rgb existed, fallback: */
  }
  .ghost-btn.primary:hover {
    background: var(--accent);
    color: var(--bg);
  }

  @media (prefers-reduced-motion: reduce) {
    .selection-card {
      transition: none !important;
    }
  }
</style>

{#if $selection}
  <div
    class="selection-card"
    transition:slide={{ duration: 180, axis: 'y' }}
    role="dialog"
    aria-modal="false"
    tabindex="-1"
    bind:this={cardRef}
    aria-labelledby="selection-title"
  >
    <div class="header">
      <div>
        <span class="badge">{$selection.type}</span>
        <h3 id="selection-title">
          {#if $selection.data && $selection.data.title}
            {$selection.data.title}
          {:else}
            Element {$selection.id}
          {/if}
        </h3>
      </div>
      <button class="close-btn" on:click={close} aria-label="Close">✕</button>
    </div>

    <div class="content">
      {#if $selection.data}
        {$selection.data.summary || 'Keine Beschreibung verfügbar.'}
      {:else}
        Wird geladen...
      {/if}
    </div>

    <div class="actions">
      <button class="ghost-btn">Details</button>
      <button class="ghost-btn primary">Handeln</button>
    </div>
  </div>
{/if}
