<script lang="ts">
  import { onDestroy } from 'svelte';
  import { selection } from '$lib/stores/uiView';
  import { buildPanelEndpoint, createPanelDetailsLoader } from '$lib/panels/panelDetails';
  import { formatDate } from '$lib/utils/formatDate';

  interface EdgeParticipantDetails {
    id: string;
    title: string;
    type?: string;
  }

  interface EdgeDetails {
    id: string;
    edge_kind: string;
    note?: string;
    created_at?: string;
    source_details?: EdgeParticipantDetails | null;
    target_details?: EdgeParticipantDetails | null;
  }

  const detailsLoader = createPanelDetailsLoader<EdgeDetails>(selection, {
    buildEndpoint: (id) => buildPanelEndpoint('edge', id),
    resourceLabel: 'edge details',
  });
  const edgeDetailsStore = detailsLoader.details;
  const isLoadingDetailsStore = detailsLoader.isLoading;
  onDestroy(detailsLoader.destroy);

  $: edgeDetails = $edgeDetailsStore;
  $: isLoadingDetails = $isLoadingDetailsStore;
</script>

<div class="edge-mode">
  <h3>{edgeDetails?.edge_kind || $selection?.data?.edge_kind || 'Faden'}</h3>

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
          <p class="ghost">
            {$selection?.data?.source_id || 'Unbekannt'}
            {#if $selection?.data?.source_type}
              <span class="participant-role">({$selection?.data?.source_type})</span>
            {/if}
          </p>
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
          <p class="ghost">
            {$selection?.data?.target_id || 'Unbekannt'}
            {#if $selection?.data?.target_type}
              <span class="participant-role">({$selection?.data?.target_type})</span>
            {/if}
          </p>
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