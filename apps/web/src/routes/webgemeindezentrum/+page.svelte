<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { page } from "$app/stores";
  import CenterGovernance from "$lib/components/governance/CenterGovernance.svelte";
  import NodeConversation from "$lib/components/panels/NodeConversation.svelte";
  import { authStore } from "$lib/auth/store";
  import { buildPanelEndpoint } from "$lib/panels/panelDetails";
  import { formatDate } from "$lib/utils/formatDate";
  import {
    emptyWebgemeindezentrumGovernance,
    webgemeindezentrumTruthHeading,
    type WebgemeindezentrumDetails,
  } from "$lib/webgemeindezentrum/details";
  import "$lib/styles/page-system.css";

  let details: WebgemeindezentrumDetails | null = null;
  let loading = true;
  let loadError = "";
  let mounted = false;
  let loadedCenterId = "";
  let requestController: AbortController | null = null;

  $: centerId = $page.url.searchParams.get("id")?.trim() ?? "";
  $: governance = details?.governance ?? emptyWebgemeindezentrumGovernance();
  $: history = details?.location_history ?? [];
  $: truthHeading = webgemeindezentrumTruthHeading(details?.location_state);
  $: mapHref = details
    ? `/map?focus=webgemeindezentrum:${encodeURIComponent(details.id)}`
    : "/map";

  $: if (mounted && centerId !== loadedCenterId) {
    loadedCenterId = centerId;
    void loadCenter(centerId);
  }

  async function loadCenter(id: string): Promise<void> {
    requestController?.abort();
    requestController = null;
    details = null;
    loadError = "";

    if (!id) {
      loading = false;
      loadError =
        "Für die Vollansicht fehlt die Kennung des Webgemeindezentrums.";
      return;
    }

    const controller = new AbortController();
    requestController = controller;
    loading = true;

    try {
      const response = await fetch(
        buildPanelEndpoint("webgemeindezentrum", id),
        { signal: controller.signal },
      );
      if (!response.ok) {
        throw new Error(
          `Webgemeindezentrum konnte nicht geladen werden (${response.status})`,
        );
      }

      const loaded = (await response.json()) as WebgemeindezentrumDetails;
      if (loaded.type !== "webgemeindezentrum" || loaded.id !== id) {
        throw new Error(
          "Webgemeindezentrum-Antwort passt nicht zur angefragten Kennung",
        );
      }
      if (!controller.signal.aborted) details = loaded;
    } catch (cause) {
      if ((cause as { name?: string } | null)?.name === "AbortError") return;
      console.error(cause);
      loadError = "Das Webgemeindezentrum kann gerade nicht geladen werden.";
    } finally {
      if (requestController === controller) {
        requestController = null;
        loading = false;
      }
    }
  }

  onMount(() => {
    mounted = true;
    void authStore.checkAuth();
    loadedCenterId = centerId;
    void loadCenter(centerId);
  });

  onDestroy(() => {
    mounted = false;
    requestController?.abort();
    requestController = null;
  });
</script>

<svelte:head>
  <title
    >{details
      ? `${details.title} · Weltgewebe`
      : "Webgemeindezentrum · Weltgewebe"}</title
  >
  <meta
    name="description"
    content="Vollansicht eines Webgemeindezentrums mit örtlicher Selbstverwaltung, Gespräch, Treffortstatus und Standortverlauf."
  />
</svelte:head>

<main
  class="wg-page wg-page--paper center-page"
  data-testid="webgemeindezentrum-full-view"
>
  <div class="center-shell">
    <header class="center-header">
      <a
        class="wg-back-link"
        href={mapHref}
        data-testid="webgemeindezentrum-map-link">← Zur Karte</a
      >

      {#if loading}
        <p class="wg-state wg-state--muted" role="status">
          Webgemeindezentrum wird geladen…
        </p>
      {:else if loadError}
        <div class="wg-state wg-state--error" role="alert">
          <p>{loadError}</p>
          <p><a href="/map">Zurück zum Gewebe</a></p>
        </div>
      {:else if details}
        <div class="hero-grid">
          <div class="hero-copy">
            <p class="wg-eyebrow">{details.ortsweberei.name}</p>
            <h1 class="wg-title">{details.title}</h1>
            <p class="wg-lede">
              Hier bündelt die Ortsweberei ihre örtlichen Entscheidungen, ihr
              öffentliches Gespräch und den nachvollziehbaren Treffort.
            </p>
          </div>

          <aside
            class="place-status"
            data-location-state={details.location_state}
            data-testid="webgemeindezentrum-full-location-state"
            aria-label="Treffortstatus"
          >
            <p class="status-kicker">Treffortstatus</p>
            <strong>{details.location_state_label}</strong>
            <p>{details.location_label}</p>
            <span class="truth-heading">{truthHeading}</span>
          </aside>
        </div>

        <dl class="identity-strip" aria-label="Webgemeindezentrum im Überblick">
          <div>
            <dt>Ortsweberei</dt>
            <dd>{details.ortsweberei.name}</dd>
          </div>
          <div>
            <dt>Gewebezelle</dt>
            <dd>{details.ortsweberei.gewebezelle_id}</dd>
          </div>
          <div>
            <dt>Kartenpunkt</dt>
            <dd>
              {details.location.lat.toFixed(4)}, {details.location.lon.toFixed(
                4,
              )}
            </dd>
          </div>
        </dl>
      {/if}
    </header>

    {#if details}
      <section
        class="activity-strip"
        aria-label="Aktivität im Webgemeindezentrum"
        data-testid="webgemeindezentrum-activity-summary"
      >
        <div>
          <strong>{governance.proposal_count}</strong>
          <span>Anträge</span>
        </div>
        <div>
          <strong>{governance.open_proposal_count}</strong>
          <span>offen</span>
        </div>
        <div>
          <strong>{governance.voting_proposal_count}</strong>
          <span>in Abstimmung</span>
        </div>
        <div>
          <strong>{governance.conversation_message_count}</strong>
          <span>Gesprächsbeiträge</span>
        </div>
      </section>

      <section class="work-grid" aria-label="Gemeinsame Arbeit">
        <div class="workspace-card governance-workspace">
          <CenterGovernance
            centerId={details.id}
            proposalCount={governance.proposal_count}
            openProposalCount={governance.open_proposal_count}
            votingProposalCount={governance.voting_proposal_count}
          />
        </div>

        <div class="workspace-card conversation-workspace">
          <p class="wg-eyebrow">Lokales Gespräch</p>
          {#if details.conversation_id}
            <NodeConversation
              conversationId={details.conversation_id}
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
          <p class="wg-eyebrow">Gemeinsam vor Ort</p>
          <h2>Treffort</h2>
          <p>{details.location_label}</p>
          {#if details.meeting_note}<p>{details.meeting_note}</p>{/if}
          {#if details.access_note}
            <aside class="truth-note">
              <strong>{truthHeading}</strong>
              <p>{details.access_note}</p>
            </aside>
          {/if}
        </article>

        <article class="place-card">
          <p class="wg-eyebrow">Nachvollziehbar</p>
          <h2>Standortverlauf</h2>
          {#if history.length > 0}
            <ol class="center-timeline">
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
          {:else}
            <p class="quiet-state">
              Der erste veröffentlichte Standort ist im kanonischen Datensatz
              verankert.
            </p>
          {/if}
        </article>
      </section>
    {/if}
  </div>
</main>

<style>
  .center-page {
    padding-top: clamp(1rem, 3vw, 2rem);
  }

  .center-shell {
    width: min(76rem, calc(100% - 2rem));
    margin-inline: auto;
  }

  .center-header {
    display: grid;
    gap: clamp(1.5rem, 4vw, 2.5rem);
    padding-bottom: clamp(1.5rem, 5vw, 3rem);
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

  .place-status {
    display: grid;
    gap: 0.45rem;
    padding: 1.2rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: var(--radius);
    background: color-mix(in srgb, var(--panel-solid) 92%, var(--accent-soft));
    box-shadow: var(--shadow);
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

  .status-kicker,
  .truth-heading,
  .quiet-state,
  .center-timeline time {
    color: var(--muted);
  }

  .status-kicker {
    font-size: 0.78rem;
    font-weight: 750;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .truth-heading {
    display: inline-flex;
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
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1px;
    overflow: hidden;
    margin: 0;
    border: 1px solid var(--panel-border);
    border-radius: var(--radius);
    background: var(--panel-border);
  }

  .identity-strip div,
  .activity-strip div {
    min-width: 0;
    padding: 0.9rem 1rem;
    background: var(--panel-solid);
  }

  .identity-strip dt,
  .activity-strip span {
    color: var(--muted);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .identity-strip dd {
    overflow-wrap: anywhere;
    margin: 0.25rem 0 0;
    font-weight: 700;
  }

  .activity-strip {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    margin-bottom: clamp(1rem, 3vw, 1.5rem);
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
    border: 1px solid var(--panel-border);
    border-radius: var(--radius);
    background: color-mix(in srgb, var(--panel-solid) 96%, transparent);
    box-shadow: var(--shadow);
  }

  .conversation-workspace {
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

  .place-card {
    display: grid;
    align-content: start;
    gap: 0.8rem;
  }

  .place-card h2,
  .place-card p,
  .truth-note p,
  .center-timeline p {
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

  .center-timeline {
    display: grid;
    gap: 1rem;
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .center-timeline li {
    display: grid;
    gap: 0.4rem;
    padding-left: 1rem;
    border-left: 2px solid var(--panel-border-strong);
  }

  .center-timeline li > div {
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
    .center-shell {
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
