<script lang="ts">
  import { selection } from '$lib/stores/uiView';
  import { authStore } from '$lib/auth/store';
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

  // STUB: This data structure mimics the future backend data.
  // In the final implementation, this should come from $selection.data.modules
  // TODO: Replace stub modules with selection-driven data.
  // Initial state is all locked (safe default)
  let modules = [
    { id: 'infos', label: 'Steckbrief', locked: true },
    { id: 'besprechungen', label: 'Forum', locked: true },
    { id: 'verantwortungen', label: 'Verantwortungen', locked: true }
  ];

  // Helper to determine ownership and type
  $: isAccount = $selection?.type === 'account';
  // Check if current user is the owner of the selected account
  $: isOwner = $authStore.loggedIn && $selection && $selection.id === $authStore.current_account_id;

  // Reactively reset modules when selection changes
  let lastSelectionId: string | null = null;
  $: if ($selection?.id !== lastSelectionId) {
    lastSelectionId = $selection?.id || null;
    // Reset to default locked state on new selection.
    // Note: Nodes are currently default-locked for safety, awaiting a defined Node-Ownership model.
    // If nodes should be public-writable or public-unlocked in the future, change this default.
    modules = modules.map(m => ({ ...m, locked: true }));
  }

  // Enforce invariant: If it's an account and not owner, it MUST be locked.
  // This auto-corrects any state drift.
  $: if (isAccount && !isOwner) {
     const anyUnlocked = modules.some(m => !m.locked);
     if (anyUnlocked) {
        modules = modules.map(m => ({ ...m, locked: true }));
     }
  }

  function handleModuleClick(module: typeof modules[0]) {
    // Navigate or open module detail
    console.log('Open module:', module.id);
  }

  function toggleLock(id: string) {
    // Immutable update to ensure robust reactivity and state history if needed
    modules = modules.map(m =>
      m.id === id ? { ...m, locked: !m.locked } : m
    );
  }
</script>

<style>
  .schaufenster-card {
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
    .schaufenster-card {
      bottom: 80px;
      right: 12px;
    }
  }

  /* Mobile: Bottom (above dock) */
  @media (max-width: 599px) {
    .schaufenster-card {
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

  .module-card {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 48px;
    background: transparent;
    border: 1px solid var(--panel-border);
    border-radius: 8px;
    transition: all 0.2s ease;
  }

  .module-card:hover {
    background: rgba(0,0,0,0.03);
    border-color: var(--muted);
  }

  .module-card.locked {
    border-style: dashed;
    opacity: 0.8;
    background: rgba(0,0,0,0.02);
  }

  /* Main action button covers the card area except the lock button */
  .module-action {
    flex: 1;
    height: 100%;
    border: none;
    background: transparent;
    cursor: pointer;
    color: var(--text);
    font-size: 13px;
    font-weight: 500;
    text-align: center;
    padding: 10px;
    width: 100%;
  }

  .module-card.locked .module-action {
    color: var(--muted);
    cursor: default;
  }

  /* Discrete Lock Toggle Button */
  .lock-toggle {
    position: absolute;
    top: 2px;
    right: 2px;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    cursor: pointer;
    border-radius: 4px;
    /* Updated for better visibility/UX (Splinter #1) */
    opacity: 0.3;
    transition: opacity 0.2s, background 0.2s;
    font-size: 12px;
    padding: 0;
  }

  .lock-toggle:hover,
  .lock-toggle:focus-visible {
    opacity: 1;
    background: rgba(0,0,0,0.05);
  }

  /* When locked, fully visible */
  .module-card.locked .lock-toggle {
    opacity: 0.8;
  }
  .module-card.locked .lock-toggle:hover {
    opacity: 1;
  }

  @media (prefers-reduced-motion: reduce) {
    .schaufenster-card {
      transition: none !important;
    }
  }
</style>

{#if $selection}
  <div
    class="schaufenster-card"
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

    <!-- The "Schaufenster" Buttons -->
    <div class="modules-grid" role="group" aria-label="Module">
      {#each modules as module (module.id)}
        <div class="module-card" class:locked={module.locked}>
          <button
            class="module-action"
            on:click={() => !module.locked && handleModuleClick(module)}
            aria-disabled={module.locked}
          >
            {module.label}
          </button>

          <!-- Lock toggle is only visible for owners on accounts (or non-accounts if applicable) -->
          <!-- "Unlock-UI ist nur sichtbar, wenn isOwner === true" -->
          {#if !isAccount || isOwner}
            <button
              class="lock-toggle"
              on:click|stopPropagation={() => toggleLock(module.id)}
              aria-label={module.locked ? `${module.label} entsperren` : `${module.label} verzwirnen`}
              aria-pressed={module.locked}
              title={module.locked ? 'Entsperren' : 'Verzwirnen'}
            >
              {module.locked ? '🔒' : '🔓'}
            </button>
          {/if}
        </div>
      {/each}
    </div>
  </div>
{/if}
