<script lang="ts">
  import { onMount, tick } from "svelte";
  import { afterNavigate, goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { authStore } from "$lib/auth/store";
  import "$lib/styles/page-system.css";
  import ProposalDetail from "$lib/components/governance/ProposalDetail.svelte";
  import {
    GovernanceApiError,
    createWeberProposal,
    exitGuestAccount,
    formatRemaining,
    listProposals,
    statusLabel,
    type Proposal,
  } from "$lib/api/governance";

  let proposals: Proposal[] = [];
  let loading = true;
  let error = "";
  let summary = "";
  let submitting = false;
  let leaving = false;
  type ApplicationFocusRequest = "initial" | "navigation";

  let applicationSection: HTMLElement | null = null;
  let pendingApplicationFocus: ApplicationFocusRequest | null = null;

  $: selectedProposalId = $page.url.searchParams.get("id");
  $: statusFilter = $page.url.searchParams.get("status");
  $: eventFilter = $page.url.searchParams.get("ereignis");
  $: visibleProposals =
    statusFilter === "consent" || statusFilter === "voting"
      ? proposals.filter((proposal) => proposal.status === statusFilter)
      : eventFilter === "veto"
        ? proposals.filter((proposal) => proposal.veto_count > 0)
        : eventFilter === "gespraech"
          ? proposals.filter((proposal) => proposalMessageCount(proposal) > 0)
          : proposals;
  $: proposalListTitle =
    statusFilter === "consent"
      ? "Offene Anträge"
      : statusFilter === "voting"
        ? "Abstimmungen"
        : eventFilter === "veto"
          ? "Anträge mit Veto"
          : eventFilter === "gespraech"
            ? "Gespräche"
            : "Alle Anträge";
  $: isGuest = $authStore.authenticated && $authStore.role === "gast";
  $: hasOpenOwnProposal =
    isGuest &&
    proposals.some(
      (proposal) =>
        proposal.applicant_account_id === $authStore.account_id &&
        (proposal.status === "consent" || proposal.status === "voting"),
    );

  function proposalMessageCount(proposal: Proposal): number {
    return Math.max(0, proposal.message_count ?? 0);
  }

  function describeError(cause: unknown): string {
    if (cause instanceof GovernanceApiError) {
      if (cause.status === 409)
        return "Diese Aktion ist im aktuellen Zustand nicht möglich.";
      if (cause.status === 503)
        return "Das Antragssystem ist vorübergehend nicht verfügbar.";
    }
    return "Das Antragssystem konnte nicht geladen werden.";
  }

  async function refresh() {
    loading = true;
    error = "";
    try {
      proposals = await listProposals();
    } catch (cause) {
      error = describeError(cause);
    } finally {
      loading = false;
    }
  }

  async function applyForWeber() {
    if (!isGuest || hasOpenOwnProposal || submitting) return;
    submitting = true;
    error = "";
    try {
      const created = await createWeberProposal(summary);
      proposals = [created, ...proposals];
      summary = "";
    } catch (cause) {
      error = describeError(cause);
    } finally {
      submitting = false;
    }
  }

  async function leaveWeltgewebe() {
    if (!isGuest || leaving) return;
    const confirmed = window.confirm(
      "Gastkonto wirklich vollständig auflösen? Der Account, eigene Weberanträge, Passkeys und Sitzungen werden gelöscht.",
    );
    if (!confirmed) return;
    leaving = true;
    error = "";
    try {
      await exitGuestAccount();
      await authStore.checkAuth();
      await goto("/login");
    } catch (cause) {
      error = describeError(cause);
      leaving = false;
    }
  }

  async function focusPendingApplicationSection(): Promise<boolean> {
    const request = pendingApplicationFocus;
    if (!request) return false;
    await tick();
    if (!applicationSection) return false;

    if (request === "initial") {
      const active = document.activeElement;
      if (
        active &&
        active !== document.body &&
        active !== document.documentElement
      ) {
        pendingApplicationFocus = null;
        return false;
      }
    }

    applicationSection.focus();
    pendingApplicationFocus = null;
    return document.activeElement === applicationSection;
  }

  afterNavigate(({ to, type }) => {
    if (to?.url.hash !== "#antrag-stellen") {
      pendingApplicationFocus = null;
      return;
    }
    pendingApplicationFocus = type === "enter" ? "initial" : "navigation";
    void focusPendingApplicationSection();
  });

  onMount(async () => {
    await authStore.checkAuth();
    await focusPendingApplicationSection();
    await refresh();
  });
</script>

<svelte:head>
  <title>Anträge · Weltgewebe</title>
  <meta
    name="description"
    content="Offene Anträge, Konsentphasen, Vetos, Gespräche und Abstimmungen im Weltgewebe."
  />
</svelte:head>

{#if selectedProposalId}
  <ProposalDetail proposalId={selectedProposalId} />
{:else}
  <main class="wg-page wg-page--paper" data-testid="applications-page">
    <div class="wg-page__shell">
      <header class="wg-page__header">
        <a class="wg-back-link" href="/map">← Zum Gewebe</a>
        <p class="wg-eyebrow">Gemeinsame Entscheidungen</p>
        <h1 class="wg-title">Anträge</h1>
        <p class="wg-lede">
          Jeder Antrag liegt sieben Tage offen. Ohne Veto wird er angenommen.
          Nach einem Veto folgen weitere sieben Tage Gespräch und Abstimmung;
          angenommen ist er genau dann, wenn mehr Ja- als Nein-Stimmen
          vorliegen.
        </p>
      </header>

      {#if isGuest}
        <section
          id="antrag-stellen"
          class="wg-card wg-card--padded wg-stack guest-card"
          aria-labelledby="weberstatus-heading"
          tabindex="-1"
          bind:this={applicationSection}
        >
          <div class="wg-stack">
            <p class="wg-eyebrow">Dein Status: Gast</p>
            <h2 id="weberstatus-heading">Weberstatus beantragen</h2>
            <p>
              Als Gast besitzt du bereits deine Garnrolle und kannst sie
              beschreiben. Ein angenommener Antrag verleiht dir zusätzliche
              Weberrechte; er erzeugt keine zweite Garnrolle.
            </p>
          </div>
          {#if hasOpenOwnProposal}
            <p class="wg-state wg-state--success">
              Dein Weberantrag ist bereits offen.
            </p>
          {:else}
            <div class="wg-field">
              <label class="wg-label" for="application-summary"
                >Kurze Vorstellung oder Begründung</label
              >
              <textarea
                class="wg-control"
                id="application-summary"
                bind:value={summary}
                maxlength="2000"
                rows="5"
                placeholder="Was möchtest du im Weltgewebe beitragen?"
              ></textarea>
            </div>
            <button
              class="wg-button wg-button--primary"
              on:click={applyForWeber}
              disabled={submitting}
            >
              {submitting ? "Antrag wird gestellt…" : "Weberstatus beantragen"}
            </button>
          {/if}
          <button
            class="wg-button wg-button--danger"
            on:click={leaveWeltgewebe}
            disabled={leaving}
          >
            {leaving
              ? "Gastkonto wird aufgelöst…"
              : "Weltgewebe vollständig verlassen"}
          </button>
        </section>
      {/if}

      {#if error}
        <div class="wg-state wg-state--error page-error" role="alert">
          {error}
        </div>
      {/if}

      <section aria-labelledby="proposal-list-heading">
        <div class="wg-section-heading">
          <div>
            <h2 id="proposal-list-heading">{proposalListTitle}</h2>
            <nav
              class="proposal-filters"
              aria-label="Governance-Ereignisse filtern"
            >
              <a
                class:active={!statusFilter && !eventFilter}
                aria-current={!statusFilter && !eventFilter
                  ? "true"
                  : undefined}
                href="/antraege">Alle</a
              >
              <a
                class:active={statusFilter === "consent"}
                aria-current={statusFilter === "consent" ? "true" : undefined}
                href="/antraege?status=consent">Offen</a
              >
              <a
                class:active={eventFilter === "veto"}
                aria-current={eventFilter === "veto" ? "true" : undefined}
                href="/antraege?ereignis=veto">Vetos</a
              >
              <a
                class:active={eventFilter === "gespraech"}
                aria-current={eventFilter === "gespraech" ? "true" : undefined}
                href="/antraege?ereignis=gespraech">Gespräche</a
              >
              <a
                class:active={statusFilter === "voting"}
                aria-current={statusFilter === "voting" ? "true" : undefined}
                href="/antraege?status=voting">Abstimmungen</a
              >
            </nav>
          </div>
          <button
            class="wg-button wg-button--secondary"
            on:click={refresh}
            disabled={loading}>Aktualisieren</button
          >
        </div>

        {#if loading}
          <p class="wg-state wg-state--muted" role="status">
            Anträge werden geladen…
          </p>
        {:else if !error || proposals.length > 0}
          {#if proposals.length === 0}
            <p class="wg-state">Noch liegen keine Anträge vor.</p>
          {:else if visibleProposals.length === 0}
            <p class="wg-state">
              {eventFilter === "gespraech"
                ? "Noch gibt es keine Gespräche mit Beiträgen."
                : "Für diese Ansicht liegen keine Anträge vor."}
            </p>
          {:else}
            <div class="proposal-list">
              {#each visibleProposals as proposal}
                <a
                  class="wg-card proposal-card"
                  href={`/antraege?id=${encodeURIComponent(proposal.id)}`}
                >
                  <div class="wg-inline-spread proposal-topline">
                    <span
                      class:open={proposal.status === "consent" ||
                        proposal.status === "voting"}
                      >{statusLabel(proposal.status)}</span
                    >
                    <time datetime={proposal.created_at}
                      >{new Date(proposal.created_at).toLocaleDateString(
                        "de-DE",
                      )}</time
                    >
                  </div>
                  <h3>Weberstatus für {proposal.applicant_title}</h3>
                  {#if proposal.summary}<p>{proposal.summary}</p>{/if}
                  <div class="facts">
                    <span
                      >{proposal.veto_count} Veto{proposal.veto_count === 1
                        ? ""
                        : "s"}</span
                    >
                    <span
                      >{proposalMessageCount(proposal)} Beitrag{proposalMessageCount(
                        proposal,
                      ) === 1
                        ? ""
                        : "e"}</span
                    >
                    <span
                      >{proposal.yes_votes} Ja · {proposal.no_votes} Nein</span
                    >
                    {#if proposal.remaining_seconds !== undefined}<span
                        >Noch {formatRemaining(
                          proposal.remaining_seconds,
                        )}</span
                      >{/if}
                  </div>
                </a>
              {/each}
            </div>
          {/if}
        {/if}
      </section>
    </div>
  </main>
{/if}

<style>
  h2,
  h3,
  p {
    margin-block: 0;
  }

  .guest-card {
    margin-bottom: 36px;
  }

  .guest-card .wg-eyebrow {
    margin-top: 0;
  }

  .page-error {
    margin-bottom: 24px;
  }

  .proposal-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
  }

  .proposal-filters a {
    min-height: 44px;
    padding: 0 14px;
    border: 1px solid var(--wg-border);
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    color: inherit;
    text-decoration: none;
    font-weight: 680;
  }

  .proposal-filters a.active {
    border-color: var(--wg-action);
    background: var(--wg-action-soft);
    color: var(--wg-action);
  }

  .proposal-list {
    display: grid;
    gap: 12px;
  }

  .proposal-card {
    display: grid;
    gap: 12px;
    padding: 20px;
    color: inherit;
    text-decoration: none;
    transition:
      transform 120ms ease,
      border-color 120ms ease;
  }

  .proposal-card:hover,
  .proposal-card:focus-visible {
    transform: translateY(-2px);
    border-color: var(--wg-border-strong);
  }

  .proposal-topline {
    font-size: 0.82rem;
    color: var(--wg-muted);
  }

  .proposal-topline span {
    padding: 4px 9px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--wg-muted) 12%, transparent);
  }

  .proposal-topline span.open {
    background: var(--wg-action-soft);
    color: var(--wg-action);
  }

  .proposal-card p {
    line-height: 1.5;
  }

  .facts {
    display: flex;
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 0.86rem;
    color: var(--wg-muted);
  }

  @media (max-width: 560px) {
    .proposal-topline {
      align-items: flex-start;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .proposal-card {
      transition: none;
    }

    .proposal-card:hover,
    .proposal-card:focus-visible {
      transform: none;
    }
  }
</style>
