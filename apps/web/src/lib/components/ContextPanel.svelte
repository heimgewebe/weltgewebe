<script lang="ts">
  import { selection, systemState, contextPanelOpen, kompositionDraft } from '$lib/stores/uiView';

  let activeTab = 'uebersicht';

  function setTab(tab: string) {
    activeTab = tab;
  }

  $: if ($selection) {
    if ($selection.type === 'node') {
      if (!['uebersicht', 'gespraech', 'antraege', 'verlauf'].includes(activeTab)) {
        activeTab = 'uebersicht';
      }
    } else if ($selection.type === 'garnrolle' || $selection.type === 'account') {
      if (!['profil', 'aktivitaet', 'knoten'].includes(activeTab)) {
        activeTab = 'profil';
      }
    }
  }

  function closePanel() {
    systemState.set('navigation');
    selection.set(null);
    kompositionDraft.set(null);
  }
</script>

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
        <div class="komposition-mode">
          {#if $kompositionDraft?.source === 'map-longpress' && $kompositionDraft.lngLat}
            <p>Neuer Knoten am Ort: {$kompositionDraft.lngLat[1].toFixed(5)}, {$kompositionDraft.lngLat[0].toFixed(5)}</p>
          {:else}
            <p>Bitte wähle einen Ort auf der Karte (Longpress) für den neuen Knoten.</p>
          {/if}
          <!-- Additional editor fields would go here -->
        </div>
      {:else if $selection}
        {#if $selection.type === 'node'}
          <div class="node-mode">
            <h3>{$selection.data?.title || $selection.id}</h3>
            <p class="summary">{$selection.data?.summary || 'Keine Beschreibung verfügbar.'}</p>

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
        {:else if $selection.type === 'account' || $selection.type === 'garnrolle'}
          <div class="account-mode">
            <h3>{$selection.data?.title || $selection.id}</h3>
            <p class="summary">{$selection.data?.summary || 'Handelnder Akteur im Gewebe.'}</p>

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
        {:else if $selection.type === 'edge'}
          <div class="edge-mode">
            <h3>Faden: {$selection.id}</h3>

            <div class="details">
              <p><strong>Ursprung:</strong> {$selection.data?.source || 'Unbekannt'}</p>
              <p><strong>Ziel:</strong> {$selection.data?.target || 'Unbekannt'}</p>
              <p><strong>Zeitlichkeit:</strong> ...</p>
            </div>
          </div>
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
      width: 400px;
      box-shadow: var(--shadow, -4px 0 16px rgba(0,0,0,0.1));
    }
  }
</style>
