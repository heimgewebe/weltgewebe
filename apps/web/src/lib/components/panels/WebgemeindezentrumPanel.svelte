<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { page } from "$app/stores";
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
  let detailsLoadFailed = false;
  const detailsLoader = createPanelDetailsLoader<WebgemeindezentrumDetails>(
    selection,
    {
      buildEndpoint: (id) => buildPanelEndpoint("webgemeindezentrum", id),
      resourceLabel: "Webgemeindezentrum",
      onSelectionChange: () => {
        detailsLoadFailed = false;
      },
      onError: (error) => {
        console.error(error);
        detailsLoadFailed = true;
      },
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
  $: fullViewMode = $page.url.searchParams.get("view") === "webgemeindezentrum";
  $: mapHref = centerId
    ? `/map?focus=webgemeindezentrum:${encodeURIComponent(centerId)}`
    : "/map";
  $: fullViewHref = centerId ? `${mapHref}&view=webgemeindezentrum` : "/map";
</script>

{#if fullViewMode}
  <section
    class="center-full-view"
    aria-labelledby="webgemeindezentrum-full-heading"
    data-testid="webgemeindezentrum-full-view"
  >
    <div class="full-shell">
      <header class="full-header">
        <a
          class="back-link"
          href={mapHref}
          data-testid="webgemeindezentrum-map-link">← Zur Kartenansicht</a
        >

        <div class="hero-grid">
          <div class="hero-copy">
            {#if ortsweberei}<p class="eyebrow">{ortsweberei.name}</p>{/if}
            <h1
              id="webgemeindezentrum-full-heading"
              bind:this={heading}
              tabindex="-1"
            >
              {title}
            </h1>
            <p class="lede">
              Hier bündelt die Ortsweberei ihre örtlichen Entscheidungen, ihr
              öffentliches Gespräch und den nachvollziehbaren Treffort.
            </p>
          </div>

          {#if locationStateLabel || locationLabel}
            <aside
              class="place-status"
              data-location-state={locationState}
              data-testid="webgemeindezentrum-full-location-state"
              aria-label="Treffortstatus"
            >
              <p class="status-kicker">Treffortstatus</p>
              {#if locationStateLabel}<strong>{locationStateLabel}</strong>{/if}
              {#if locationLabel}<p>{locationLabel}</p>{/if}
              <span class="truth-heading">{truthHeading}</span>
            </aside>
          {/if}
        </div>

        <dl class="identity-strip" aria-label="Webgemeindezentrum im Überblick">
          {#if ortsweberei}
            <div>
              <dt>Ortsweberei</dt>
              <dd>{ortsweberei.name}</dd>
            </div>
            <div>
              <dt>Gewebezelle</dt>
              <dd>{ortsweberei.gewebezelle_id}</dd>
            </div>
          {/if}
          {#if location}
            <div>
              <dt>Kartenpunkt</dt>
              <dd>{location.lat.toFixed(4)}, {location.lon.toFixed(4)}</dd>
            </div>
          {/if}
        </dl>
      </header>

      {#if $loadingStore && !details}
        <p class="quiet-state" role="status">Lade aktuelle Zentrumdaten…</p>
      {:else if detailsLoadFailed}
        <p
          class="detail-error"
          role="alert"
          data-testid="webgemeindezentrum-details-error"
        >
          Aktuelle Aktivitäts- und Verlaufsdaten konnten nicht geladen werden.
          Die Treffortangaben stammen weiterhin aus der Kartenprojektion.
        </p>
      {/if}

      {#if details}
        <section
          class="activity-strip"
          aria-label="Aktivität im Webgemeindezentrum"
          data-testid="webgemeindezentrum-activity-summary"
        >
          <div>
            <strong>{governance.proposal_count}</strong><span>Anträge</span>
          </div>
          <div>
            <strong>{governance.open_proposal_count}</strong><span>offen</span>
          </div>
          <div>
            <strong>{governance.voting_proposal_count}</strong><span
              >in Abstimmung</span
            >
          </div>
          <div>
            <strong>{governance.conversation_message_count}</strong><span
              >Gesprächsbeiträge</span
            >
          </div>
        </section>
      {/if}

      <section class="work-grid" aria-label="Gemeinsame Arbeit">
        <div class="workspace-card governance-workspace">
          {#if centerId}
            <CenterGovernance
              {centerId}
              proposalCount={governance.proposal_count}
              openProposalCount={governance.open_proposal_count}
              votingProposalCount={governance.voting_proposal_count}
            />
          {/if}
        </div>

        <div class="workspace-card conversation-workspace">
          <p class="eyebrow">Lokales Gespräch</p>
          {#if conversationId}
            <NodeConversation
              {conversationId}
              heading="Gespräch im Webgemeindezentrum"
              emptyMessage="Noch keine Beiträge. Hier beginnt das gemeinsame Gespräch der Ortsweberei."
              testId="webgemeindezentrum-full-conversation"
            />
          {:else}
            <p class="quiet-state">
              Für dieses Webgemeindezentrum ist noch kein Gesprächsraum
              veröffentlicht.
            </p>
          {/if}
        </div>
      </section>

      <section class="place-grid" aria-label="Treffort und Transparenz">
        <article class="place-card">
          <p class="eyebrow">Gemeinsam vor Ort</p>
          <h2>Treffort</h2>
          {#if locationLabel}<p>{locationLabel}</p>{/if}
          {#if meetingNote}<p>{meetingNote}</p>{/if}
          {#if accessNote}
            <aside class="truth-note">
              <strong>{truthHeading}</strong>
              <p>{accessNote}</p>
            </aside>
          {/if}
        </article>

        <article class="place-card">
          <p class="eyebrow">Nachvollziehbar</p>
          <h2>Standortverlauf</h2>
          {#if history.length > 0}
            <ol class="full-timeline">
              {#each history as event}
                <li>
                  <div>
                    <strong>{event.location_state_label}</strong>
                    <time datetime={event.decided_at}
                      >{formatDate(event.decided_at)}</time
                    >
                  </div>
                  <p>{event.reason}</p>
                </li>
              {/each}
            </ol>
          {:else if detailsLoadFailed}
            <p class="quiet-state">
              Der Standortverlauf konnte nicht geladen werden.
            </p>
          {:else if !$loadingStore}
            <p class="quiet-state">
              Der erste veröffentlichte Standort ist im kanonischen Datensatz
              verankert.
            </p>
          {/if}
        </article>
      </section>
    </div>
  </section>
{:else}
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
      <a href={fullViewHref} data-testid="webgemeindezentrum-full-view-link"
        >Vollansicht öffnen →</a
      >
    {/if}

    {#if $loadingStore && !details}
      <p class="ghost" role="status">Lade Standortverlauf…</p>
    {:else if detailsLoadFailed}
      <p
        class="ghost"
        role="alert"
        data-testid="webgemeindezentrum-details-error"
      >
        Aktuelle Detaildaten konnten nicht geladen werden.
      </p>
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
        {:else if detailsLoadFailed}
          <p class="ghost">Der Standortverlauf ist gerade nicht verfügbar.</p>
        {:else if !$loadingStore}
          <p class="ghost">
            Der erste gewünschte Standort ist im kanonischen Datensatz
            verankert.
          </p>
        {/if}
      </section>
    </div>
  </section>
{/if}

<style>
  .center-full-view {
    position: fixed;
    inset: 0;
    z-index: var(--z-map-modal);
    overflow: auto;
    box-sizing: border-box;
    padding: clamp(1rem, 3vw, 2rem) 0 clamp(2rem, 5vw, 4rem);
    background: var(--bg);
    color: var(--text);
  }

  .full-shell {
    width: min(76rem, calc(100% - 2rem));
    margin-inline: auto;
  }

  .full-header {
    display: grid;
    gap: clamp(1.5rem, 4vw, 2.5rem);
    padding-bottom: clamp(1.5rem, 5vw, 3rem);
  }

  .back-link {
    width: fit-content;
    color: var(--accent);
    font-weight: 700;
    text-decoration-thickness: 1px;
    text-underline-offset: 0.2em;
  }

  .hero-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.7fr) minmax(17rem, 0.7fr);
    gap: clamp(1.25rem, 4vw, 3rem);
    align-items: end;
  }

  .hero-copy {
    display: grid;
    gap: 1rem;
  }

  .hero-copy h1 {
    margin: 0;
    font-size: clamp(2rem, 6vw, 4.5rem);
    line-height: 0.98;
    letter-spacing: -0.045em;
  }

  .eyebrow,
  .status-kicker,
  .identity-strip dt,
  .activity-strip span {
    margin: 0;
    color: var(--muted);
    font-size: 0.78rem;
    font-weight: 750;
    letter-spacing: 0.07em;
    text-transform: uppercase;
  }

  .lede {
    max-width: 48rem;
    margin: 0;
    color: var(--muted);
    font-size: clamp(1.02rem, 2vw, 1.22rem);
    line-height: 1.55;
  }

  .place-status,
  .workspace-card,
  .place-card {
    border: 1px solid var(--panel-border);
    border-radius: var(--radius);
    background: var(--panel-solid);
    box-shadow: var(--shadow);
  }

  .place-status {
    display: grid;
    gap: 0.45rem;
    padding: 1.2rem;
    border-color: var(--panel-border-strong);
  }

  .place-status[data-location-state="desired"],
  .place-status[data-location-state="provisional"] {
    border-style: dashed;
  }

  .place-status p,
  .place-status strong {
    margin: 0;
  }

  .place-status strong {
    font-size: 1.25rem;
  }

  .truth-heading,
  .quiet-state,
  .full-timeline time {
    color: var(--muted);
  }

  .truth-heading {
    width: fit-content;
    margin-top: 0.3rem;
    padding: 0.28rem 0.55rem;
    border-radius: 999px;
    background: var(--accent-soft);
    font-size: 0.82rem;
    font-weight: 750;
  }

  .identity-strip,
  .activity-strip {
    display: grid;
    gap: 1px;
    overflow: hidden;
    margin: 0;
    border: 1px solid var(--panel-border);
    border-radius: var(--radius);
    background: var(--panel-border);
  }

  .identity-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .activity-strip {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    margin-bottom: clamp(1rem, 3vw, 1.5rem);
  }

  .identity-strip div,
  .activity-strip div {
    min-width: 0;
    padding: 0.9rem 1rem;
    background: var(--panel-solid);
  }

  .identity-strip dd {
    overflow-wrap: anywhere;
    margin: 0.25rem 0 0;
    font-weight: 700;
  }

  .activity-strip div {
    display: grid;
    gap: 0.1rem;
  }

  .activity-strip strong {
    font-size: clamp(1.35rem, 3vw, 1.8rem);
  }

  .work-grid,
  .place-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: clamp(1rem, 3vw, 1.5rem);
  }

  .workspace-card,
  .place-card {
    min-width: 0;
    padding: clamp(1rem, 3vw, 1.5rem);
  }

  .conversation-workspace,
  .place-card {
    display: grid;
    align-content: start;
    gap: 0.8rem;
  }

  .governance-workspace :global([data-testid="center-governance"]) {
    padding: 0;
    border: 0;
  }

  .place-grid {
    margin-top: clamp(1rem, 3vw, 1.5rem);
  }

  .place-card h2,
  .place-card p,
  .truth-note p,
  .full-timeline p {
    margin: 0;
  }

  .truth-note {
    display: grid;
    gap: 0.35rem;
    margin-top: 0.35rem;
    padding: 0.9rem 1rem;
    border-left: 3px solid var(--accent);
    border-radius: 0 10px 10px 0;
    background: var(--accent-soft);
  }

  .full-timeline {
    display: grid;
    gap: 1rem;
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .full-timeline li {
    display: grid;
    gap: 0.4rem;
    padding-left: 1rem;
    border-left: 2px solid var(--panel-border-strong);
  }

  .full-timeline li > div {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 0.5rem;
  }

  @media (max-width: 820px) {
    .hero-grid,
    .work-grid,
    .place-grid {
      grid-template-columns: 1fr;
    }
    .identity-strip,
    .activity-strip {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 480px) {
    .full-shell {
      width: min(calc(100% - 1rem), 76rem);
    }
    .identity-strip,
    .activity-strip {
      grid-template-columns: 1fr;
    }
    .workspace-card,
    .place-card {
      padding: 1rem;
    }
  }
</style>
