<script lang="ts">
  import { selection } from '$lib/stores/uiView';

  import { env } from '$env/dynamic/public';

  const API_BASE = env.PUBLIC_GEWEBE_API_BASE ?? '';

  let activeTab = 'uebersicht';

  interface NodeDetails {
    id: string;
    title: string;
    summary?: string;
    created_at?: string;
    updated_at?: string;
    kind?: string;
    tags?: string[];
    location?: { lat: number; lon: number };
    participants?: { account_title?: string; account_id: string; edge_kind?: string }[];
    history?: { date: string; event: string }[];
  }

  function setTab(tab: string) {
    activeTab = tab;
  }

  // Explicitly reset tab when node ID changes
  let currentSelectionId: string | undefined;
  let lastSelectionId: string | undefined;

  let nodeDetails: NodeDetails | null = null;
  let isLoadingDetails = false;

  let abortController: AbortController | null = null;

  $: {
    currentSelectionId = $selection?.id;
    if (currentSelectionId !== lastSelectionId) {
      lastSelectionId = currentSelectionId;
      activeTab = 'uebersicht';
      nodeDetails = null;

      // Cancel any ongoing fetch if selection changes rapidly
      if (abortController) {
        abortController.abort();
      }

      if (currentSelectionId) {
        isLoadingDetails = true;
        abortController = new AbortController();
        const currentReqId = currentSelectionId;

        fetch(`${API_BASE}/api/nodes/${currentSelectionId}/`, {
          signal: abortController.signal
        })
          .then((res) => {
            if (res.ok) return res.json();
            throw new Error('Failed to load node details');
          })
          .then((data) => {
            // Only update state if this response matches the currently selected node
            if (currentSelectionId === currentReqId) {
              nodeDetails = data;
            }
          })
          .catch((err) => {
            if (err.name !== 'AbortError') {
              console.error(err);
            }
          })
          .finally(() => {
            if (currentSelectionId === currentReqId) {
              isLoadingDetails = false;
            }
          });
      }
    }
  }

  function formatDate(isoString: string | undefined) {
    if (!isoString) return 'Unbekannt';
    try {
      return new Intl.DateTimeFormat('de-DE', { timeZone: 'UTC', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(isoString));
    } catch (e) {
      return 'Unbekannt';
    }
  }

  let displayLat: number | undefined;
  let displayLon: number | undefined;

  // Typecast or fallback carefully since $selection type doesn't formally export .lat/.lng at the root
  // even though MapPoint might contain them at runtime
  $: {
    const selectionData = nodeDetails || ($selection?.data as any);
    displayLat = selectionData?.location?.lat ?? selectionData?.lat;
    displayLon = selectionData?.location?.lon ?? selectionData?.lon;
  }
</script>

<div class="node-mode">
  <h3>{nodeDetails?.title || $selection?.data?.title || $selection?.id}</h3>
  <p class="summary">{nodeDetails?.summary || $selection?.data?.summary || 'Keine Beschreibung verfügbar.'}</p>

  <div class="tabs">
    <button class:active={activeTab === 'uebersicht'} on:click={() => setTab('uebersicht')}>Übersicht</button>
    <button class:active={activeTab === 'gespraech'} on:click={() => setTab('gespraech')}>Gespräch</button>
    <button class:active={activeTab === 'antraege'} on:click={() => setTab('antraege')}>Anträge</button>
    <button class:active={activeTab === 'verlauf'} on:click={() => setTab('verlauf')}>Verlauf</button>
  </div>

  <div class="tab-content">
    {#if activeTab === 'uebersicht'}
      <div class="overview">
        {#if isLoadingDetails}
          <p class="ghost">Lade Details...</p>
        {:else}
          {#if (nodeDetails?.created_at || $selection?.data?.created_at)}
            <p><strong>Erstellt am:</strong> {formatDate(nodeDetails?.created_at || $selection?.data?.created_at)}</p>
          {/if}

          {#if (nodeDetails?.kind || $selection?.data?.kind)}
            <p><strong>Art:</strong> {nodeDetails?.kind || $selection?.data?.kind}</p>
          {/if}

          {#if (nodeDetails?.tags || $selection?.data?.tags)?.length > 0}
            <p><strong>Tags:</strong> {(nodeDetails?.tags || $selection?.data?.tags).join(', ')}</p>
          {/if}

          {#if typeof displayLat === 'number' && typeof displayLon === 'number'}
            <p><strong>Koordinaten:</strong> {displayLat.toFixed(5)}, {displayLon.toFixed(5)}</p>
          {/if}

          {#if nodeDetails?.participants && nodeDetails.participants.length > 0}
            <div class="participants">
              <p><strong>Beteiligte:</strong></p>
              <ul>
                {#each nodeDetails.participants as participant}
                  <li>
                    <span class="participant-name">{participant.account_title || participant.account_id}</span>
                    {#if participant.edge_kind}
                      <span class="participant-role">({participant.edge_kind})</span>
                    {/if}
                  </li>
                {/each}
              </ul>
            </div>
          {/if}
        {/if}
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
        {#if isLoadingDetails}
          <p class="ghost">Lade Verlauf...</p>
        {:else if nodeDetails?.history && nodeDetails.history.length > 0}
          <ul class="timeline">
            {#each nodeDetails.history as event}
              <li>
                <span class="date">{formatDate(event.date)}</span>
                <span class="event">{event.event}</span>
              </li>
            {/each}
          </ul>
        {:else}
          <ul class="timeline">
            {#if $selection?.data?.updated_at && $selection?.data?.updated_at !== $selection?.data?.created_at}
            <li>
              <span class="date">{formatDate($selection?.data?.updated_at)}</span>
              <span class="event">Knoten aktualisiert.</span>
            </li>
            {/if}
            <li>
              <span class="date">{$selection?.data?.created_at ? formatDate($selection?.data?.created_at) : 'Kürzlich'}</span>
              <span class="event">Knoten wurde im Gewebe verankert.</span>
            </li>
          </ul>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .participants {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--panel-border, rgba(0,0,0,0.1));
  }

  .participants ul {
    list-style: none;
    padding: 0;
    margin: 0.5rem 0 0 0;
  }

  .participants li {
    margin-bottom: 0.25rem;
    display: flex;
    gap: 0.5rem;
    align-items: baseline;
  }

  .participant-name {
    font-weight: 500;
    color: var(--text, #333);
  }

  .participant-role {
    font-size: 0.85em;
    color: var(--ghost, #666);
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

  .ghost {
    color: var(--muted, #9aa4b2);
    font-size: 0.9rem;
  }

  /* Overview Styles */
  .overview p {
    margin-bottom: 0.5rem;
    font-size: 0.95rem;
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
