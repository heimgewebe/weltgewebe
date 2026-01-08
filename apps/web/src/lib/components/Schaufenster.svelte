<script context="module" lang="ts">
  import type { Module } from '../../routes/map/types';
  // Simple in-memory cache for session persistence
  // Cache policy: Session-only, unbounded (bounded by typical session usage), persists across component re-mounts
  const modulesCache = new Map<string, Module[]>();
</script>

<script lang="ts">
  import { selection } from '$lib/stores/uiView';
  import { authStore } from '$lib/auth/store';
  import { slide } from 'svelte/transition';
  import { tick } from 'svelte';
  import { env } from '$env/dynamic/public';
  import { browser } from '$app/environment';

  function close() {
    $selection = null;
    isEditingInfo = false;
  }

  // Manage focus when card opens
  let cardRef: HTMLElement;
  $: if ($selection && cardRef) {
    (async () => {
      await tick();
      cardRef?.focus();
    })();
  }

  // Wire real module data from selection
  // Modules come from backend data and include locked state
  // Create working copy that can be mutated for UI state (lock/unlock)
  let modules: Module[] = [];
  
  // Reset modules when selection changes
  let lastSelectionId: string | null = null;
  let isEditingInfo = false;
  let infoDraft = '';

  $: if ($selection?.id !== lastSelectionId) {
    lastSelectionId = $selection?.id || null;

    if ($selection?.id) {
        // Use cache only in browser to avoid SSR shared state leaks
        if (browser && modulesCache.has($selection.id)) {
            // Restore from cache
            const cached = modulesCache.get($selection.id) || [];
            modules = cached.map(m => ({...m}));
        } else {
             // Initialize from selection data
             const sourceModules = $selection?.data?.modules ?? [];
             modules = sourceModules.map((m: Module) => ({ ...m }));

             if (browser) {
                 modulesCache.set($selection.id, modules);
             }
        }
    } else {
        modules = [];
    }

    // Reset editing state
    isEditingInfo = false;
    infoDraft = '';
  }

  // Helper to determine ownership and type
  $: isAccount = $selection?.type === 'account';
  // Check if current user is the owner of the selected account
  $: isOwner = $authStore.loggedIn && $selection && $selection.id === $authStore.current_account_id;

  // Enforce invariant: If it's an account and not owner, modules MUST be locked.
  // This auto-corrects any state drift from backend.
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

    // Persist to cache (browser only)
    const selectionId = $selection?.id;
    if (selectionId && browser) {
        modulesCache.set(selectionId, modules);
    }
  }

  function startEditInfo() {
    infoDraft = $selection?.data?.info || '';
    isEditingInfo = true;
  }

  async function saveInfo() {
    if (!$selection?.id) return;

    try {
      const apiBase = env.PUBLIC_GEWEBE_API_BASE || '/api';
      const selectionId = $selection.id;
      const nextInfo = infoDraft;
      const endpoint = `${apiBase}/nodes/${selectionId}`;

      const res = await fetch(endpoint, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ info: nextInfo })
      });

      if (res.ok) {
        // Update local store to reflect changes immediately
        selection.update((current) => {
          if (!current || current.id !== selectionId || !current.data) {
            return current;
          }

          return {
            ...current,
            data: {
              ...current.data,
              info: nextInfo
            }
          };
        });
        isEditingInfo = false;
      } else {
        console.error('Failed to save info', res.status);
        alert('Fehler beim Speichern.');
      }
    } catch (e) {
      console.error(e);
      alert('Fehler beim Speichern.');
    }
  }

  function cancelEditInfo() {
    isEditingInfo = false;
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

  .no-modules {
    grid-column: 1 / -1;
    text-align: center;
    padding: 16px;
    color: var(--muted);
    font-size: 14px;
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

  /* Info Styles */
  .info-section {
    border-top: 1px solid var(--panel-border);
    padding-top: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .info-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .info-title {
    font-size: 14px;
    font-weight: 600;
  }

  .info-content {
    font-size: 14px;
    color: var(--text);
    line-height: 1.5;
    white-space: pre-wrap;
    max-height: 200px;
    overflow-y: auto;
  }

  .info-empty {
    font-style: italic;
    color: var(--muted);
    font-size: 13px;
  }

  .edit-btn {
    background: transparent;
    border: none;
    color: var(--accent, #0066cc);
    font-size: 12px;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 4px;
  }
  .edit-btn:hover {
    background: rgba(0,0,0,0.05);
  }

  .info-editor {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  textarea.info-input {
    width: 100%;
    min-height: 100px;
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--panel-border);
    border-radius: 6px;
    padding: 8px;
    color: var(--text);
    font-family: inherit;
    font-size: 14px;
    resize: vertical;
  }

  .editor-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }

  .action-btn {
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
    border: 1px solid transparent;
  }

  .save-btn {
    background: var(--accent, #0066cc);
    color: white;
  }
  .cancel-btn {
    background: transparent;
    border-color: var(--panel-border);
    color: var(--text);
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

    <!-- Info Section -->
    {#if $selection.type === 'node'}
      <div class="info-section">
        <div class="info-header">
          <span class="info-title">Info</span>
          {#if !isEditingInfo}
            <button class="edit-btn" on:click={startEditInfo}>Bearbeiten</button>
          {/if}
        </div>

        {#if isEditingInfo}
          <div class="info-editor">
            <textarea
              class="info-input"
              bind:value={infoDraft}
              placeholder="Info hier eingeben..."
            ></textarea>
            <div class="editor-actions">
              <button class="action-btn cancel-btn" on:click={cancelEditInfo}>Abbrechen</button>
              <button class="action-btn save-btn" on:click={saveInfo}>Speichern</button>
            </div>
          </div>
        {:else}
          <div class="info-content">
            {#if $selection.data && $selection.data.info}
              {$selection.data.info}
            {:else}
              <span class="info-empty">Keine Info vorhanden</span>
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    <!-- The "Schaufenster" Buttons -->
    <div class="modules-grid" role="group" aria-label="Module">
      {#if modules.length === 0}
        <div class="no-modules">Keine Module</div>
      {:else}
        {#each modules as module (module.id)}
          <div class="module-card" class:locked={module.locked} data-module-id={module.id}>
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
      {/if}
    </div>
  </div>
{/if}
