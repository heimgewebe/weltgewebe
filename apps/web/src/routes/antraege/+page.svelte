<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { authStore } from "$lib/auth/store";
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

  $: selectedProposalId = $page.url.searchParams.get("id");
  $: statusFilter = $page.url.searchParams.get("status");
  $: eventFilter = $page.url.searchParams.get("ereignis");
  $: visibleProposals =
    statusFilter === "consent" || statusFilter === "voting"
      ? proposals.filter((proposal) => proposal.status === statusFilter)
      : eventFilter === "veto"
        ? proposals.filter((proposal) => proposal.veto_count > 0)
        : eventFilter === "gespraech"
          ? proposals.filter((proposal) => proposal.status === "voting")
          : proposals;
  $: proposalListTitle =
    statusFilter === "consent"
      ? "Offene Anträge"
      : statusFilter === "voting"
        ? "Abstimmungen"
        : eventFilter === "veto"
          ? "Anträge mit Veto"
          : eventFilter === "gespraech"
            ? "Gesprächsphasen"
            : "Alle Anträge";
  $: isGuest = $authStore.authenticated && $authStore.role === "gast";
  $: hasOpenOwnProposal =
    isGuest &&
    proposals.some(
      (proposal) =>
        proposal.applicant_account_id === $authStore.account_id &&
        (proposal.status === "consent" || proposal.status === "voting"),
    );

  function describeError(cause: unknown): string {
    if (cause instanceof GovernanceApiError) {
      if (cause.status === 409) return "Diese Aktion ist im aktuellen Zustand nicht möglich.";
      if (cause.status === 503) return "Das Antragssystem ist vorübergehend nicht verfügbar.";
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

  onMount(async () => {
    await authStore.checkAuth();
    await refresh();
  });
</script>

<svelte:head>
  <title>Anträge · Weltgewebe</title>
  <meta name="description" content="Offene Anträge, Konsentphasen, Vetos, Gespräche und Abstimmungen im Weltgewebe." />
</svelte:head>

{#if selectedProposalId}
  <ProposalDetail proposalId={selectedProposalId} />
{:else}
<main class="page-shell">
  <header class="page-header">
    <a class="back-link" href="/map">← Zum Gewebe</a>
    <p class="eyebrow">Gemeinsame Entscheidungen</p>
    <h1>Anträge</h1>
    <p>
      Jeder Antrag liegt sieben Tage offen. Ohne Veto wird er angenommen. Nach einem Veto folgen weitere sieben Tage Gespräch und Abstimmung; angenommen ist er genau dann, wenn mehr Ja- als Nein-Stimmen vorliegen.
    </p>
  </header>

  {#if isGuest}
    <section id="antrag-stellen" class="guest-card" aria-labelledby="weberstatus-heading">
      <div>
        <p class="eyebrow">Dein Status: Gast</p>
        <h2 id="weberstatus-heading">Weberstatus beantragen</h2>
        <p>Als Gast kannst du das gesamte Weltgewebe erkunden, hinterlässt aber keine Spuren. Mit einem angenommenen Antrag erhältst du deine Garnrolle und kannst weben.</p>
      </div>
      {#if hasOpenOwnProposal}
        <p class="notice">Dein Weberantrag ist bereits offen.</p>
      {:else}
        <label for="application-summary">Kurze Vorstellung oder Begründung</label>
        <textarea id="application-summary" bind:value={summary} maxlength="2000" rows="5" placeholder="Was möchtest du im Weltgewebe beitragen?"></textarea>
        <button class="primary" on:click={applyForWeber} disabled={submitting}>
          {submitting ? "Antrag wird gestellt…" : "Weberstatus beantragen"}
        </button>
      {/if}
      <button class="danger-link" on:click={leaveWeltgewebe} disabled={leaving}>
        {leaving ? "Gastkonto wird aufgelöst…" : "Weltgewebe vollständig verlassen"}
      </button>
    </section>
  {/if}

  {#if error}<div class="error" role="alert">{error}</div>{/if}

  <section aria-labelledby="proposal-list-heading">
    <div class="section-heading">
      <div>
        <h2 id="proposal-list-heading">{proposalListTitle}</h2>
        <nav class="proposal-filters" aria-label="Governance-Ereignisse filtern">
          <a class:active={!statusFilter && !eventFilter} href="/antraege">Alle</a>
          <a class:active={statusFilter === "consent"} href="/antraege?status=consent">Offen</a>
          <a class:active={eventFilter === "veto"} href="/antraege?ereignis=veto">Vetos</a>
          <a class:active={eventFilter === "gespraech"} href="/antraege?ereignis=gespraech">Gespräche</a>
          <a class:active={statusFilter === "voting"} href="/antraege?status=voting">Abstimmungen</a>
        </nav>
      </div>
      <button class="secondary" on:click={refresh} disabled={loading}>Aktualisieren</button>
    </div>

    {#if loading}
      <p class="muted">Anträge werden geladen…</p>
    {:else if proposals.length === 0}
      <p class="empty">Noch liegen keine Anträge vor.</p>
    {:else if visibleProposals.length === 0}
      <p class="empty">Für diese Ansicht liegen keine Anträge vor.</p>
    {:else}
      <div class="proposal-list">
        {#each visibleProposals as proposal}
          <a class="proposal-card" href={`/antraege?id=${encodeURIComponent(proposal.id)}`}>
            <div class="proposal-topline">
              <span class:open={proposal.status === "consent" || proposal.status === "voting"}>{statusLabel(proposal.status)}</span>
              <time datetime={proposal.created_at}>{new Date(proposal.created_at).toLocaleDateString("de-DE")}</time>
            </div>
            <h3>Weberstatus für {proposal.applicant_title}</h3>
            {#if proposal.summary}<p>{proposal.summary}</p>{/if}
            <div class="facts">
              <span>{proposal.veto_count} Veto{proposal.veto_count === 1 ? "" : "s"}</span>
              <span>{proposal.yes_votes} Ja · {proposal.no_votes} Nein</span>
              {#if proposal.remaining_seconds !== undefined}<span>Noch {formatRemaining(proposal.remaining_seconds)}</span>{/if}
            </div>
          </a>
        {/each}
      </div>
    {/if}
  </section>
</main>
{/if}

<style>
  :global(body) { margin: 0; background: #f3f1e9; color: #18251f; font-family: system-ui, sans-serif; }
  .page-shell { width: min(880px, calc(100% - 32px)); margin: 0 auto; padding: 28px 0 72px; }
  .page-header { padding: 24px 0 32px; }
  .back-link { color: inherit; text-decoration: none; font-weight: 650; }
  .eyebrow { margin: 28px 0 6px; text-transform: uppercase; letter-spacing: .09em; font-size: .76rem; font-weight: 750; color: #4d6759; }
  h1 { margin: 0; font-size: clamp(2.4rem, 8vw, 4.5rem); line-height: .95; }
  h2, h3 { margin: 0; }
  .page-header > p:last-child { max-width: 68ch; font-size: 1.08rem; line-height: 1.6; }
  .guest-card, .proposal-card, .error, .empty { border: 1px solid rgba(24,37,31,.16); border-radius: 18px; background: rgba(255,255,255,.72); }
  .guest-card { display: grid; gap: 14px; padding: 24px; margin-bottom: 36px; }
  .guest-card .eyebrow { margin-top: 0; }
  label { font-weight: 700; }
  textarea { box-sizing: border-box; width: 100%; resize: vertical; border: 1px solid rgba(24,37,31,.28); border-radius: 12px; padding: 12px; font: inherit; background: #fff; }
  button { width: fit-content; border-radius: 999px; padding: 10px 16px; font: inherit; font-weight: 720; cursor: pointer; }
  button:disabled { opacity: .55; cursor: wait; }
  .primary { border: 0; background: #1f5b42; color: white; }
  .secondary { border: 1px solid rgba(24,37,31,.28); background: transparent; color: inherit; }
  .danger-link { border: 0; padding-left: 0; background: transparent; color: #8d2f2f; }
  .notice { padding: 12px 14px; border-radius: 10px; background: #e7efe9; }
  .error { padding: 14px 16px; margin-bottom: 24px; color: #7f2424; background: #fff0f0; }
  .section-heading, .proposal-topline, .facts { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .section-heading { margin-bottom: 16px; }
  .proposal-filters { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  .proposal-filters a { min-height: 44px; padding: 0 14px; border: 1px solid rgba(24,37,31,.2); border-radius: 999px; display: inline-flex; align-items: center; color: inherit; text-decoration: none; font-weight: 680; }
  .proposal-filters a.active { border-color: #1f5b42; background: #dcecdf; color: #1f5b42; }
  .proposal-list { display: grid; gap: 12px; }
  .proposal-card { display: grid; gap: 12px; padding: 20px; color: inherit; text-decoration: none; transition: transform 120ms ease, border-color 120ms ease; }
  .proposal-card:hover, .proposal-card:focus-visible { transform: translateY(-2px); border-color: rgba(24,37,31,.45); }
  .proposal-topline { font-size: .82rem; color: #607168; }
  .proposal-topline span { padding: 4px 9px; border-radius: 999px; background: #e9e8e1; }
  .proposal-topline span.open { background: #dcecdf; color: #1f5b42; }
  .proposal-card p { margin: 0; line-height: 1.5; }
  .facts { justify-content: flex-start; flex-wrap: wrap; font-size: .86rem; color: #526259; }
  .empty { padding: 24px; }
  .muted { color: #607168; }
  @media (max-width: 560px) { .section-heading, .proposal-topline { align-items: flex-start; } .section-heading { flex-direction: column; } }
</style>
