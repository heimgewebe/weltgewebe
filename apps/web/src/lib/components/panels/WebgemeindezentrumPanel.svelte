<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import CenterGovernance from "$lib/components/governance/CenterGovernance.svelte";
  import NodeConversation from "$lib/components/panels/NodeConversation.svelte";
  import { selection } from "$lib/stores/uiView";
  import {
    buildPanelEndpoint,
    createPanelDetailsLoader,
  } from "$lib/panels/panelDetails";
  import { formatDate } from "$lib/utils/formatDate";
  import type { MapEntityWebgemeindezentrum } from "$lib/map/types";
  import {
    emptyWebgemeindezentrumGovernance,
    webgemeindezentrumTruthHeading,
    type WebgemeindezentrumDetails,
  } from "$lib/webgemeindezentrum/details";

  let heading: HTMLHeadingElement;
  const detailsLoader = createPanelDetailsLoader<WebgemeindezentrumDetails>(
    selection,
    {
      buildEndpoint: (id) => buildPanelEndpoint("webgemeindezentrum", id),
      resourceLabel: "Webgemeindezentrum",
    },
  );
  const detailsStore = detailsLoader.details;
  const loadingStore = detailsLoader.isLoading;
  onDestroy(detailsLoader.destroy);
  onMount(() => heading?.focus());

  $: fallback = $selection?.data as MapEntityWebgemeindezentrum | undefined;
  $: details = $detailsStore;
  $: title = details?.title || fallback?.title || "Webgemeindezentrum";
  $: locationState = details?.location_state || fallback?.location_state;
  $: locationStateLabel =
    details?.location_state_label || fallback?.location_state_label;
  $: locationLabel = details?.location_label || fallback?.location_label;
  $: meetingNote = details?.meeting_note || fallback?.meeting_note;
  $: accessNote = details?.access_note || fallback?.access_note;
  $: ortsweberei = details?.ortsweberei || fallback?.ortsweberei;
  $: location =
    details?.location ||
    (fallback ? { lat: fallback.lat, lon: fallback.lon } : undefined);
  $: history = details?.location_history || [];
  $: centerId = details?.id || fallback?.id;
  $: conversationId = details?.conversation_id || fallback?.conversation_id;
  $: governance = details?.governance ?? emptyWebgemeindezentrumGovernance();
  $: truthHeading = webgemeindezentrumTruthHeading(locationState);
</script>

<section class="center-mode" aria-labelledby="webgemeindezentrum-heading">
  <h3
    id="webgemeindezentrum-heading"
    bind:this={heading}
    tabindex="-1"
    data-testid="webgemeindezentrum-heading"
  >
    {title}
  </h3>

  {#if locationStateLabel}
    <p
      class:desired={locationState === "desired"}
      class="location-state"
      data-testid="webgemeindezentrum-location-state"
    >
      {locationStateLabel}
    </p>
  {/if}

  <div
    class="compact-summary"
    role="region"
    aria-label="Webgemeindezentrum im Überblick"
    data-testid="webgemeindezentrum-compact-summary"
  >
    {#if locationLabel}
      <p><strong>Treffort:</strong> {locationLabel}</p>
    {/if}
    {#if ortsweberei}
      <p><strong>Ortsweberei:</strong> {ortsweberei.name}</p>
    {/if}
  </div>

  {#if centerId}
    <a
      class="full-view-link"
      href={`/webgemeindezentrum?id=${encodeURIComponent(centerId)}`}
      data-testid="webgemeindezentrum-full-view-link"
    >
      <span>Vollansicht öffnen</span>
      <span aria-hidden="true">→</span>
    </a>
  {/if}

  {#if $loadingStore && !details}
    <p class="ghost" role="status">Lade Standortverlauf…</p>
  {/if}

  <div class="full-content">
    {#if centerId}
      <CenterGovernance
        {centerId}
        proposalCount={governance.proposal_count}
        openProposalCount={governance.open_proposal_count}
        votingProposalCount={governance.voting_proposal_count}
      />
    {/if}

    {#if conversationId}
      <NodeConversation
        {conversationId}
        heading="Gespräch im Webgemeindezentrum"
        emptyMessage="Noch keine Beiträge. Hier beginnt das gemeinsame Gespräch der Ortsweberei."
        testId="webgemeindezentrum-conversation"
      />
    {/if}

    {#if meetingNote}
      <section aria-labelledby="meeting-purpose-heading">
        <h4 id="meeting-purpose-heading">Gemeinsam vor Ort</h4>
        <p>{meetingNote}</p>
      </section>
    {/if}

    {#if accessNote}
      <aside class="truth-note" aria-label="Standortstatus">
        <strong>{truthHeading}</strong>
        <p>{accessNote}</p>
      </aside>
    {/if}

    {#if ortsweberei}
      <dl>
        <div>
          <dt>Ortsweberei</dt>
          <dd>{ortsweberei.name}</dd>
        </div>
        <div>
          <dt>Gewebezelle</dt>
          <dd><code>{ortsweberei.gewebezelle_id}</code></dd>
        </div>
        {#if location}
          <div>
            <dt>Kartenpunkt</dt>
            <dd>{location.lat.toFixed(4)}, {location.lon.toFixed(4)}</dd>
          </div>
        {/if}
      </dl>
    {/if}

    <section aria-labelledby="location-history-heading">
      <h4 id="location-history-heading">Standortverlauf</h4>
      {#if history.length > 0}
        <ol class="timeline">
          {#each history as event}
            <li>
              <strong>{event.location_state_label}</strong>
              <span>{formatDate(event.decided_at)}</span>
              <p>{event.reason}</p>
            </li>
          {/each}
        </ol>
      {:else if !$loadingStore}
        <p class="ghost">
          Der erste gewünschte Standort ist im kanonischen Datensatz verankert.
        </p>
      {/if}
    </section>
  </div>
</section>

<style>
  .full-view-link {
    display: inline-flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    min-height: 44px;
    box-sizing: border-box;
    padding: 0.55rem 0.75rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 10px;
    background: var(--accent-soft);
    color: var(--text);
    font-weight: 700;
    text-decoration: none;
  }

  .full-view-link:hover {
    border-color: var(--accent);
  }

  .full-view-link:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 2px;
  }
</style>
