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

  // Default buttons for now. In a real app, this would come from the node/account data.
  // The 'locked' state is also local for now.
  let modules = [
    { id: 'infos', label: 'Infos', locked: false },
    { id: 'besprechungen', label: 'Besprechungen', locked: false },
    { id: 'verantwortungen', label: 'Verantwortungen', locked: true } // Example of a locked button
  ];

  function handleModuleClick(module: typeof modules[0]) {
    // Navigate or open module detail
    console.log('Open module:', module.id);
  }

  function handleModuleContext(e: Event, module: typeof modules[0]) {
    e.preventDefault(); // Prevent default context menu
    // Toggle locked state "Verzwirnen"
    module.locked = !module.locked;
    modules = modules; // Trigger reactivity
  }
</script>

<style>
  .showcase-card {
    position: absolute;
    z-index: 35;
    background: var(--panel);
    border: 1px solid var(--panel-border);
    box-shadow: var(--shadow);
    border-radius: var(--radius);
    padding: 16px;
    width: 300px;
    color: var(--text);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  /* Desktop: Bottom Right */
  @media (min-width: 600px) {
    .showcase-card {
      bottom: 80px;
      right: 12px;
    }
  }

  /* Mobile: Bottom (above dock) */
  @media (max-width: 599px) {
    .showcase-card {
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

  .summary {
    font-size: 14px;
    color: var(--muted);
    line-height: 1.5;
    /* Limit to 3 lines */
    display: -webkit-box;
    line-clamp: 3;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .modules-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    margin-top: 4px;
  }

  .module-btn {
    position: relative;
    background: transparent;
    border: 1px solid var(--panel-border);
    border-radius: 8px;
    padding: 10px;
    cursor: pointer;
    color: var(--text);
    font-size: 13px;
    font-weight: 500;
    text-align: center;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 48px;
  }

  .module-btn:hover {
    background: rgba(0,0,0,0.03);
    border-color: var(--muted);
  }

  .module-btn.locked {
    border-style: dashed;
    opacity: 0.7;
    color: var(--muted);
  }

  .lock-icon {
    position: absolute;
    top: 4px;
    right: 4px;
    font-size: 10px;
  }

  .hint {
    font-size: 11px;
    color: var(--muted);
    text-align: center;
    opacity: 0.7;
    margin-top: 4px;
  }

  @media (prefers-reduced-motion: reduce) {
    .showcase-card {
      transition: none !important;
    }
  }
</style>

{#if $selection}
  <div
    class="showcase-card"
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

    <div class="summary">
      {#if $selection.data}
        {$selection.data.summary || 'Keine Beschreibung verfügbar.'}
      {:else}
        Wird geladen...
      {/if}
    </div>

    <!-- The "Showcase" Buttons -->
    <div class="modules-grid">
      {#each modules as module (module.id)}
        <button
          class="module-btn"
          class:locked={module.locked}
          on:click={() => handleModuleClick(module)}
          on:contextmenu={(e) => handleModuleContext(e, module)}
          title={module.locked ? 'Verzwirnt (Rechtsklick/Longpress zum Entsperren)' : 'Rechtsklick/Longpress zum Verzwirnen'}
        >
          {module.label}
          {#if module.locked}
             <span class="lock-icon">🔒</span>
          {/if}
        </button>
      {/each}
    </div>

    <div class="hint">
      Long-Klick (Rechtsklick) zum Verzwirnen
    </div>
  </div>
{/if}
