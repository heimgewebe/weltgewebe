<script lang="ts">
  import { selection } from '$lib/stores/uiView';

  const API_BASE = import.meta.env.PUBLIC_GEWEBE_API_BASE ?? '';

  let activeTab = 'profil';

  interface AccountDetails {
    id: string;
    title: string;
    summary?: string;
    tags?: string[];
    type?: string;
    created_at?: string;
    nodes?: { node_id: string; node_title: string; node_kind: string; edge_kind: string; note?: string }[];
    activity?: { date: string; event: string }[];
  }

  function setTab(tab: string) {
    activeTab = tab;
  }

  // Explicitly reset tab when account ID changes
  let currentSelectionId: string | undefined;
  let lastSelectionId: string | undefined;

  let accountDetails: AccountDetails | null = null;
  let isLoadingDetails = false;

  let abortController: AbortController | null = null;

  $: {
    currentSelectionId = $selection?.id;
    if (currentSelectionId !== lastSelectionId) {
      lastSelectionId = currentSelectionId;
      activeTab = 'profil';
      accountDetails = null;
      isLoadingDetails = false;

      // Cancel any ongoing fetch if selection changes rapidly
      if (abortController) {
        abortController.abort();
      }

      if (currentSelectionId) {
        isLoadingDetails = true;
        abortController = new AbortController();
        const currentReqId = currentSelectionId;

        // Use plural /api/accounts/[id] if hitting a remote API server
        // Use singular /api/account/[id] locally to avoid SvelteKit static build file/folder collisions
        const endpoint = API_BASE ? `${API_BASE}/api/accounts/${currentSelectionId}` : `/api/account/${currentSelectionId}`;

        fetch(endpoint, {
          signal: abortController.signal
        })
          .then((res) => {
            if (res.ok) return res.json();
            throw new Error('Failed to load account details');
          })
          .then((data) => {
            // Only update state if this response matches the currently selected account
            if (currentSelectionId === currentReqId) {
              accountDetails = data;
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

  const tabs = ['profil', 'aktivitaet', 'knoten'];

  function handleKeydown(e: KeyboardEvent) {
    const currentIndex = tabs.indexOf(activeTab);
    if (currentIndex === -1) return;

    let nextIndex = currentIndex;
    if (e.key === 'ArrowRight') {
      nextIndex = (currentIndex + 1) % tabs.length;
      e.preventDefault();
    } else if (e.key === 'ArrowLeft') {
      nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
      e.preventDefault();
    } else if (e.key === 'Home') {
      nextIndex = 0;
      e.preventDefault();
    } else if (e.key === 'End') {
      nextIndex = tabs.length - 1;
      e.preventDefault();
    }

    if (nextIndex !== currentIndex) {
      setTab(tabs[nextIndex]);
      const currentButton = e.currentTarget as HTMLElement | null;
      const tabList = currentButton?.closest('.tabs') as HTMLElement | null;
      if (tabList) {
        const buttons = tabList.querySelectorAll('button[role="tab"]');
        if (buttons[nextIndex]) {
          (buttons[nextIndex] as HTMLElement).focus();
        }
      }
    }
  }
</script>

<div class="account-mode">
  <h3>{accountDetails?.title || $selection?.data?.title || $selection?.id}</h3>
  <p class="summary">{accountDetails?.summary || $selection?.data?.summary || 'Handelnder Akteur im Gewebe.'}</p>

  <div class="tabs" role="tablist" aria-label="Garnrollen Tabs">
    <button
      class:active={activeTab === 'profil'}
      on:click={() => setTab('profil')}
      on:keydown={handleKeydown}
      role="tab"
      aria-selected={activeTab === 'profil'}
      aria-controls="panel-profil"
      id="tab-profil"
      tabindex={activeTab === 'profil' ? 0 : -1}
    >Profil</button>
    <button
      class:active={activeTab === 'aktivitaet'}
      on:click={() => setTab('aktivitaet')}
      on:keydown={handleKeydown}
      role="tab"
      aria-selected={activeTab === 'aktivitaet'}
      aria-controls="panel-aktivitaet"
      id="tab-aktivitaet"
      tabindex={activeTab === 'aktivitaet' ? 0 : -1}
    >Aktivität</button>
    <button
      class:active={activeTab === 'knoten'}
      on:click={() => setTab('knoten')}
      on:keydown={handleKeydown}
      role="tab"
      aria-selected={activeTab === 'knoten'}
      aria-controls="panel-knoten"
      id="tab-knoten"
      tabindex={activeTab === 'knoten' ? 0 : -1}
    >Knoten</button>
  </div>

  <div class="tab-content">
    {#if isLoadingDetails && !accountDetails}
      <p class="ghost">Lade Details...</p>
    {:else if activeTab === 'profil'}
      <div class="overview" id="panel-profil" role="tabpanel" aria-labelledby="tab-profil">
        {#if (accountDetails?.created_at || $selection?.data?.created_at)}
          <p><strong>Dabei seit:</strong> {formatDate(accountDetails?.created_at || $selection?.data?.created_at)}</p>
        {/if}

        {#if (accountDetails?.type || $selection?.data?.type)}
          <p><strong>Art:</strong> {accountDetails?.type || $selection?.data?.type}</p>
        {/if}

        {#if (accountDetails?.tags || $selection?.data?.tags)?.length > 0}
          <p><strong>Tags:</strong> {(accountDetails?.tags || $selection?.data?.tags).join(', ')}</p>
        {/if}

        <p><strong>Kompetenzen:</strong> Noch nicht hinterlegt.</p>
        <p><strong>Vergemeinschaftete Güter:</strong> Noch nicht hinterlegt.</p>
      </div>

    {:else if activeTab === 'aktivitaet'}
      <div class="timeline-placeholder" id="panel-aktivitaet" role="tabpanel" aria-labelledby="tab-aktivitaet">
        {#if isLoadingDetails}
          <p class="ghost">Lade Verlauf...</p>
        {:else if accountDetails?.activity && accountDetails.activity.length > 0}
          <ul class="timeline">
            {#each accountDetails.activity as event}
              <li>
                <span class="date">{formatDate(event.date)}</span>
                <span class="event">{event.event}</span>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="ghost">Keine Aktivität gefunden.</p>
        {/if}
      </div>

    {:else if activeTab === 'knoten'}
      <div class="nodes-placeholder" id="panel-knoten" role="tabpanel" aria-labelledby="tab-knoten">
        {#if isLoadingDetails}
          <p class="ghost">Lade Knoten...</p>
        {:else if accountDetails?.nodes && accountDetails.nodes.length > 0}
          <ul class="node-list">
            {#each accountDetails.nodes as node}
              <li>
                <span class="node-title">{node.node_title || node.node_id}</span>
                <span class="node-role">({node.edge_kind})</span>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="ghost">Keine verknüpften Knoten gefunden.</p>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .summary {
    color: var(--ghost, #666);
    margin-bottom: 1.5rem;
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

  /* Nodes Styles */
  .node-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .node-list li {
    margin-bottom: 0.5rem;
    display: flex;
    gap: 0.5rem;
    align-items: baseline;
    padding: 0.5rem;
    background: var(--panel-border, rgba(255, 255, 255, 0.03));
    border-radius: var(--radius, 4px);
  }

  .node-title {
    font-weight: 500;
    color: var(--text, #333);
  }

  .node-role {
    font-size: 0.85em;
    color: var(--ghost, #666);
  }
</style>
