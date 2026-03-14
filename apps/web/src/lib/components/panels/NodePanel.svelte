<script lang="ts">
  import { selection } from '$lib/stores/uiView';

  let activeTab = 'uebersicht';

  function setTab(tab: string) {
    activeTab = tab;
  }

  // Explicitly reset tab when node ID changes
  $: currentSelectionId = $selection?.id;
  let lastSelectionId = currentSelectionId;

  $: if (currentSelectionId !== lastSelectionId) {
    lastSelectionId = currentSelectionId;
    activeTab = 'uebersicht';
  }
</script>

<div class="node-mode">
  <h3>{$selection?.data?.title || $selection?.id}</h3>
  <p class="summary">{$selection?.data?.summary || 'Keine Beschreibung verfügbar.'}</p>

  <div class="tabs">
    <button class:active={activeTab === 'uebersicht'} on:click={() => setTab('uebersicht')}>Übersicht</button>
    <button class:active={activeTab === 'gespraech'} on:click={() => setTab('gespraech')}>Gespräch</button>
    <button class:active={activeTab === 'antraege'} on:click={() => setTab('antraege')}>Anträge</button>
    <button class:active={activeTab === 'verlauf'} on:click={() => setTab('verlauf')}>Verlauf</button>
  </div>

  <div class="tab-content">
    {#if activeTab === 'uebersicht'}
      <p>Beteiligte Garnrollen und allgemeine Aktivität.</p>
    {:else if activeTab === 'gespraech'}
      <p>Gesprächsraum des Knotens.</p>
    {:else if activeTab === 'antraege'}
      <p>Vorschläge und Abstimmungen.</p>
    {:else if activeTab === 'verlauf'}
      <p>Zeitliche Entwicklung.</p>
    {/if}
  </div>
</div>

<style>
  .summary {
    color: var(--ghost, #666);
    margin-bottom: 1.5rem;
  }

  .tabs {
    display: flex;
    gap: 0.5rem;
    border-bottom: 1px solid var(--panel-border, rgba(0,0,0,0.1));
    margin-bottom: 1rem;
    overflow-x: auto;
  }

  .tabs button {
    background: none;
    border: none;
    padding: 0.5rem 1rem;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    color: var(--ghost, #666);
    white-space: nowrap;
  }

  .tabs button.active {
    border-bottom-color: var(--accent, #0070f3);
    color: var(--text, #333);
    font-weight: bold;
  }

  .tab-content {
    padding-top: 0.5rem;
  }
</style>
