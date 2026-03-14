<script lang="ts">
  import { selection } from '$lib/stores/uiView';

  let activeTab = 'uebersicht';

  function setTab(tab: string) {
    activeTab = tab;
  }

  // Explicitly reset tab when node ID changes
  let currentSelectionId: string | undefined;
  let lastSelectionId: string | undefined;

  $: {
    currentSelectionId = $selection?.id;
    if (currentSelectionId !== lastSelectionId) {
      lastSelectionId = currentSelectionId;
      activeTab = 'uebersicht';
    }
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
      <div class="overview">
        <p><strong>Erstellt am:</strong> {$selection?.data?.created_at ? new Date($selection.data.created_at).toLocaleDateString() : 'Unbekannt'}</p>

        {#if $selection?.data?.location}
          <p><strong>Koordinaten:</strong> {$selection.data.location.lat.toFixed(5)}, {$selection.data.location.lon.toFixed(5)}</p>
        {/if}

        <div class="modules-list">
          <h4>Module</h4>
          {#if $selection?.data?.modules && $selection.data.modules.length > 0}
            <ul>
              {#each $selection.data.modules as mod}
                <li>{mod.label} <span class="badge">{mod.type}</span></li>
              {/each}
            </ul>
          {:else}
            <p class="ghost">Keine Module aktiviert.</p>
          {/if}
        </div>
      </div>

    {:else if activeTab === 'gespraech'}
      <div class="chat-placeholder">
        <div class="messages">
          <div class="message">
            <span class="author">System:</span>
            <span>Willkommen im Gesprächsraum für diesen Knoten.</span>
          </div>
        </div>
        <div class="chat-input">
          <input type="text" placeholder="Nachricht schreiben..." disabled />
          <button disabled>Senden</button>
        </div>
      </div>

    {:else if activeTab === 'antraege'}
      <div class="proposals-placeholder">
        <div class="empty-state">
          <p class="ghost">Keine aktiven Anträge.</p>
          <button class="btn-secondary" disabled>Neuen Antrag stellen</button>
        </div>
      </div>

    {:else if activeTab === 'verlauf'}
      <div class="timeline-placeholder">
        <ul class="timeline">
          <li>
            <span class="date">{$selection?.data?.created_at ? new Date($selection.data.created_at).toLocaleDateString() : 'Kürzlich'}</span>
            <span class="event">Knoten wurde im Gewebe verankert.</span>
          </li>
        </ul>
      </div>
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

  .ghost {
    color: var(--muted, #9aa4b2);
    font-size: 0.9rem;
  }

  /* Overview Styles */
  .overview p {
    margin-bottom: 0.5rem;
    font-size: 0.95rem;
  }

  .modules-list {
    margin-top: 1.5rem;
  }

  .modules-list h4 {
    margin-bottom: 0.5rem;
    font-size: 1rem;
    color: var(--text, #e9eef5);
  }

  .modules-list ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .modules-list li {
    background: var(--panel-border, rgba(255, 255, 255, 0.06));
    padding: 0.5rem 0.75rem;
    border-radius: var(--radius, 6px);
    margin-bottom: 0.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.9rem;
  }

  .badge {
    background: var(--accent-soft, rgba(106, 166, 255, 0.18));
    color: var(--accent, #6aa6ff);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    text-transform: uppercase;
  }

  /* Chat Styles */
  .chat-placeholder {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    height: 300px;
  }

  .messages {
    flex: 1;
    background: var(--panel-border, rgba(255, 255, 255, 0.03));
    border-radius: var(--radius, 6px);
    padding: 1rem;
    overflow-y: auto;
  }

  .message {
    margin-bottom: 0.5rem;
    font-size: 0.95rem;
  }

  .message .author {
    font-weight: bold;
    color: var(--accent, #6aa6ff);
    margin-right: 0.5rem;
  }

  .chat-input {
    display: flex;
    gap: 0.5rem;
  }

  .chat-input input {
    flex: 1;
    padding: 0.5rem;
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.1));
    border-radius: var(--radius, 4px);
    background: transparent;
    color: var(--text, #e9eef5);
  }

  .chat-input button {
    padding: 0.5rem 1rem;
    background: var(--panel-border, rgba(255, 255, 255, 0.1));
    border: none;
    border-radius: var(--radius, 4px);
    color: var(--muted, #9aa4b2);
    cursor: not-allowed;
  }

  /* Proposals Styles */
  .proposals-placeholder .empty-state {
    text-align: center;
    padding: 2rem 0;
  }

  .btn-secondary {
    margin-top: 1rem;
    padding: 0.5rem 1rem;
    background: transparent;
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.1));
    color: var(--muted, #9aa4b2);
    border-radius: var(--radius, 4px);
    cursor: not-allowed;
  }

  /* Timeline Styles */
  .timeline {
    list-style: none;
    padding: 0;
    margin: 0;
    border-left: 2px solid var(--panel-border, rgba(255, 255, 255, 0.1));
    margin-left: 0.5rem;
  }

  .timeline li {
    padding-left: 1rem;
    position: relative;
    margin-bottom: 1.5rem;
  }

  .timeline li::before {
    content: '';
    position: absolute;
    left: -6px;
    top: 0.25rem;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--accent, #6aa6ff);
  }

  .timeline .date {
    display: block;
    font-size: 0.8rem;
    color: var(--muted, #9aa4b2);
    margin-bottom: 0.25rem;
  }

  .timeline .event {
    font-size: 0.95rem;
  }
</style>
