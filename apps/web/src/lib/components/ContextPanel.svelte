<script lang="ts">
  import { selection, systemState, contextPanelOpen, leaveToNavigation } from '$lib/stores/uiView';
  import { tick } from 'svelte';

  import NodePanel from './panels/NodePanel.svelte';
  import AccountPanel from './panels/AccountPanel.svelte';
  import EdgePanel from './panels/EdgePanel.svelte';
  import KompositionPanel from './panels/KompositionPanel.svelte';

  function closePanel() {
    leaveToNavigation();
  }

  function handleKeydown(event: KeyboardEvent) {
    if ($contextPanelOpen && event.key === 'Escape') {
      closePanel();
    }
  }

  let headerElement: HTMLElement | null = null;
  let lastSelectionId: string | null = null;

  $: {
    if ($contextPanelOpen) {
      const currentId = $systemState === 'komposition' ? 'komposition-draft' : ($selection?.id ?? null);
      if (currentId !== lastSelectionId) {
        lastSelectionId = currentId;
        tick().then(() => {
          if (headerElement) {
            headerElement.focus();
          }
        });
      }
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if $contextPanelOpen}
  <aside class="context-panel" data-testid="context-panel" aria-label="Kontextinformationen">
    <header class="panel-header">
      {#if $systemState === 'komposition'}
        <h2 tabindex="-1" bind:this={headerElement}>Neuer Knoten</h2>
      {:else if $selection}
        {#if $selection.type === 'node'}
          <h2 tabindex="-1" bind:this={headerElement}>Knoten</h2>
        {:else if $selection.type === 'account' || $selection.type === 'garnrolle'}
          <h2 tabindex="-1" bind:this={headerElement}>Garnrolle</h2>
        {:else if $selection.type === 'edge'}
          <h2 tabindex="-1" bind:this={headerElement}>Faden</h2>
        {/if}
      {:else}
        <h2 tabindex="-1" bind:this={headerElement}>Details</h2>
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
