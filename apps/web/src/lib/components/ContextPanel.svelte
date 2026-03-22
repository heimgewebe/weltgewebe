<script lang="ts">
  import { selection, systemState, contextPanelOpen, leaveToNavigation } from '$lib/stores/uiView';
  import { isSearchOpen } from '$lib/stores/searchStore';
  import { isFilterOpen } from '$lib/stores/filterStore';

  import NodePanel from './panels/NodePanel.svelte';
  import AccountPanel from './panels/AccountPanel.svelte';
  import EdgePanel from './panels/EdgePanel.svelte';
  import KompositionPanel from './panels/KompositionPanel.svelte';

  function closePanel() {
    leaveToNavigation();
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && $contextPanelOpen && !$isSearchOpen && !$isFilterOpen) {
      closePanel();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if $contextPanelOpen}
  <aside class="context-panel" data-testid="context-panel">
    <header class="panel-header">
      {#if $systemState === 'komposition'}
        <h2>Neuer Knoten</h2>
      {:else if $selection}
        {#if $selection.type === 'node'}
          <h2>Knoten</h2>
        {:else if $selection.type === 'account' || $selection.type === 'garnrolle'}
          <h2>Garnrolle</h2>
        {:else if $selection.type === 'edge'}
          <h2>Faden</h2>
        {/if}
      {:else}
        <h2>Details</h2>
      {/if}
      <button class="close-btn" on:click={closePanel} aria-label="Schließen">✕</button>
    </header>

    <div class="panel-content">
      {#if $systemState === 'komposition'}
        <KompositionPanel />
      {:else if $selection}
        {#if $selection.type === 'node'}
          <NodePanel />
        {:else if $selection.type === 'account' || $selection.type === 'garnrolle'}
          <AccountPanel />
        {:else if $selection.type === 'edge'}
          <EdgePanel />
        {/if}
      {:else}
        <div class="empty-state">
          <p>Bitte ein Objekt auf der Karte auswählen.</p>
        </div>
      {/if}
    </div>
  </aside>
{/if}

<style>
  .context-panel {
    position: fixed;
    z-index: 50;
    background: var(--panel, #fff);
    color: var(--text, #333);
    box-shadow: var(--shadow, 0 -4px 16px rgba(0,0,0,0.1));
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    border-bottom: 1px solid var(--panel-border, rgba(0,0,0,0.1));
  }

  .panel-header h2 {
    margin: 0;
    font-size: 1.2rem;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 1.2rem;
    cursor: pointer;
    color: var(--text);
  }

  .panel-content {
    padding: 1rem;
    flex: 1;
  }

  /* Mobile: Bottom Sheet */
  @media (max-width: 768px) {
    .context-panel {
      bottom: 0;
      left: 0;
      right: 0;
      max-height: 80vh;
      border-radius: 16px 16px 0 0;
    }
  }

  /* Desktop: Right Sidebar */
  @media (min-width: 769px) {
    .context-panel {
      top: 0;
      right: 0;
      bottom: 0;
      width: var(--context-panel-width, 400px);
      box-shadow: var(--shadow, -4px 0 16px rgba(0,0,0,0.1));
    }
  }
</style>
