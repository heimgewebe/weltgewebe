<script lang="ts">
  import { selection } from '$lib/stores/uiView';
  import { onDestroy } from 'svelte';

  // To support static builds and dynamic API switching similar to NodePanel
  const API_BASE = import.meta.env.VITE_API_BASE || '';

  let edgeDetails: any = null;
  let isLoadingDetails = false;
  let abortController: AbortController | null = null;
  let lastSelectionId: string | null = null;

  // Reactively fetch edge details when selection changes
  $: {
    const currentSelectionId = $selection?.id || null;

    if (currentSelectionId && currentSelectionId !== lastSelectionId) {
      lastSelectionId = currentSelectionId;
      edgeDetails = null;
      isLoadingDetails = false;

      // Cancel any ongoing fetch if selection changes rapidly
      if (abortController) {
        abortController.abort();
      }

      isLoadingDetails = true;
      abortController = new AbortController();
      const currentReqId = currentSelectionId;

      const endpoint = API_BASE ? `${API_BASE}/api/edges/${currentSelectionId}` : `/api/edge/${currentSelectionId}`;

      fetch(endpoint, {
        signal: abortController.signal
      })
        .then((res) => {
          if (res.ok) return res.json();
          throw new Error('Failed to load edge details');
        })
        .then((data) => {
          if (currentSelectionId === currentReqId) {
            edgeDetails = data;
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

  function formatDate(isoString: string | undefined) {
    if (!isoString) return 'Unbekannt';
    try {
      return new Intl.DateTimeFormat('de-DE', { timeZone: 'UTC', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(isoString));
    } catch (e) {
      return 'Unbekannt';
    }
  }

  onDestroy(() => {
    if (abortController) {
      abortController.abort();
    }
  });
</script>

<div class="edge-mode">
  <h3>Faden: {$selection?.id}</h3>

  <div class="details">
    {#if isLoadingDetails}
      <p class="ghost">Lade Details...</p>
    {:else}
      <p>
        <strong>Typ:</strong>
        {edgeDetails?.edge_kind || $selection?.data?.edge_kind || 'Unbekannt'}
      </p>

      {#if edgeDetails?.note || $selection?.data?.note}
        <p>
          <strong>Beschreibung:</strong>
          {edgeDetails?.note || $selection?.data?.note}
        </p>
      {/if}

      <p>
        <strong>Erstellt am:</strong>
        {formatDate(edgeDetails?.created_at || $selection?.data?.created_at)}
      </p>

      <div class="participants">
        <p><strong>Ursprung:</strong></p>
        {#if edgeDetails?.source_details}
          <ul>
            <li>
              <span class="participant-name">{edgeDetails.source_details.title}</span>
              {#if edgeDetails.source_details.type}
                <span class="participant-role">({edgeDetails.source_details.type})</span>
              {/if}
            </li>
          </ul>
        {:else}
          <p class="ghost">{$selection?.data?.source || 'Unbekannt'}</p>
        {/if}

        <p class="target-title"><strong>Ziel:</strong></p>
        {#if edgeDetails?.target_details}
          <ul>
            <li>
              <span class="participant-name">{edgeDetails.target_details.title}</span>
              {#if edgeDetails.target_details.type}
                <span class="participant-role">({edgeDetails.target_details.type})</span>
              {/if}
            </li>
          </ul>
        {:else}
          <p class="ghost">{$selection?.data?.target || 'Unbekannt'}</p>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .details {
    padding-top: 0.5rem;
  }

  .details p {
    margin-bottom: 0.5rem;
    font-size: 0.95rem;
  }

  .participants {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--panel-border, rgba(0,0,0,0.1));
  }

  .participants ul {
    list-style: none;
    padding: 0;
    margin: 0.25rem 0 1rem 0;
  }

  .participants li {
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

  .target-title {
    margin-top: 1rem;
  }

  .ghost {
    color: var(--muted, #9aa4b2);
    font-size: 0.9rem;
  }
</style>