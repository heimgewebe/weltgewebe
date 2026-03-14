<script lang="ts">
  import { selection } from '$lib/stores/uiView';

  let activeTab = 'profil';

  function setTab(tab: string) {
    activeTab = tab;
  }

  // Explicitly reset tab when account ID changes
  let currentSelectionId: string | undefined;
  let lastSelectionId: string | undefined;

  $: {
    currentSelectionId = $selection?.id;
    if (currentSelectionId !== lastSelectionId) {
      lastSelectionId = currentSelectionId;
      activeTab = 'profil';
    }
  }
</script>

<div class="account-mode">
  <h3>{$selection?.data?.title || $selection?.id}</h3>
  <p class="summary">{$selection?.data?.summary || 'Handelnder Akteur im Gewebe.'}</p>

  <div class="tabs">
    <button class:active={activeTab === 'profil'} on:click={() => setTab('profil')}>Profil</button>
    <button class:active={activeTab === 'aktivitaet'} on:click={() => setTab('aktivitaet')}>Aktivität</button>
    <button class:active={activeTab === 'knoten'} on:click={() => setTab('knoten')}>Knoten</button>
  </div>

  <div class="tab-content">
    {#if activeTab === 'profil'}
      <p><strong>Kompetenzen:</strong> ...</p>
      <p><strong>Vergemeinschaftete Güter:</strong> Werkzeuge, Wissen, Zeit...</p>
    {:else if activeTab === 'aktivitaet'}
      <p>Geknüpfte Knoten und Beiträge.</p>
    {:else if activeTab === 'knoten'}
      <p>Knoten, an denen diese Garnrolle beteiligt ist.</p>
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
