<script lang="ts">
  import { onMount } from "svelte";
  import { authStore } from "$lib/auth/store";
  import GovernanceFaden from "./GovernanceFaden.svelte";
  import {
    GovernanceApiError,
    formatRemaining,
    getProposal,
    listProposalMessages,
    postProposalMessage,
    statusLabel,
    submitVeto,
    submitVote,
    type ProposalDetail,
    type ProposalMessage,
    type VoteChoice,
  } from "$lib/api/governance";

  export let proposalId: string;

  let proposal: ProposalDetail | null = null;
  let messages: ProposalMessage[] = [];
  let loading = true;
  let error = "";
  let vetoReason = "";
  let messageBody = "";
  let submitting = false;

  $: canWeave = $authStore.role === "weber" || $authStore.role === "admin";
  $: isOpen = proposal?.status === "consent" || proposal?.status === "voting";

  function describeError(cause: unknown): string {
    if (cause instanceof GovernanceApiError) {
      if (cause.status === 403) return "Diese Webungsaktion ist Gästen nicht erlaubt.";
      if (cause.status === 409) return "Die Aktion passt nicht mehr zur aktuellen Antragsphase.";
      if (cause.status === 503) return "Das Antragssystem ist vorübergehend nicht verfügbar.";
    }
    return "Der Antrag konnte nicht geladen oder geändert werden.";
  }

  async function refresh() {
    loading = true;
    error = "";
    try {
      [proposal, messages] = await Promise.all([
        getProposal(proposalId),
        listProposalMessages(proposalId),
      ]);
    } catch (cause) {
      error = describeError(cause);
    } finally {
      loading = false;
    }
  }

  async function veto() {
    if (!proposal || !vetoReason.trim() || submitting) return;
    submitting = true;
    error = "";
    try {
      await submitVeto(proposal.id, vetoReason);
      vetoReason = "";
      await refresh();
    } catch (cause) {
      error = describeError(cause);
    } finally {
      submitting = false;
    }
  }

  async function vote(choice: VoteChoice) {
    if (!proposal || submitting) return;
    submitting = true;
    error = "";
    try {
      await submitVote(proposal.id, choice);
      await refresh();
    } catch (cause) {
      error = describeError(cause);
    } finally {
      submitting = false;
    }
  }

  async function postMessage() {
    if (!proposal || !messageBody.trim() || submitting) return;
    submitting = true;
    error = "";
    try {
      const created = await postProposalMessage(proposal.id, messageBody);
      messages = [...messages, created];
      messageBody = "";
    } catch (cause) {
      error = describeError(cause);
    } finally {
      submitting = false;
    }
  }

  onMount(async () => {
    await authStore.checkAuth();
    await refresh();
  });
</script>

<svelte:head><title>Antrag · Weltgewebe</title></svelte:head>

<main class="page-shell">
  <a class="back-link" href="/antraege">← Alle Anträge</a>

  {#if loading}
    <p>Antrag wird geladen…</p>
  {:else if error && !proposal}
    <div class="error" role="alert">{error}</div>
  {:else if proposal}
    <header class="proposal-header">
      <div class="topline">
        <span class:open={isOpen}>{statusLabel(proposal.status)}</span>
        {#if proposal.remaining_seconds !== undefined}<strong>Noch {formatRemaining(proposal.remaining_seconds)}</strong>{/if}
      </div>
      <p class="eyebrow">Weberantrag</p>
      <h1>{proposal.applicant_title}</h1>
      {#if proposal.summary}<p class="summary">{proposal.summary}</p>{/if}
      <dl>
        <div><dt>Gestellt</dt><dd>{new Date(proposal.created_at).toLocaleString("de-DE")}</dd></div>
        <div><dt>Vetos</dt><dd>{proposal.veto_count}</dd></div>
        <div><dt>Abstimmung</dt><dd>{proposal.yes_votes} Ja · {proposal.no_votes} Nein · {proposal.abstain_votes} Enthaltung</dd></div>
      </dl>
    </header>

    {#if error}<div class="error" role="alert">{error}</div>{/if}

    <GovernanceFaden {proposal} {messages} />

    {#if proposal.vetoes.length > 0}
      <section class="card" aria-labelledby="vetos-heading">
        <h2 id="vetos-heading">Vetos</h2>
        <div class="entries">
          {#each proposal.vetoes as item}
            <article>
              <div class="entry-meta"><strong>{item.weber_title}</strong><time datetime={item.created_at}>{new Date(item.created_at).toLocaleString("de-DE")}</time></div>
              <p>{item.reason}</p>
            </article>
          {/each}
        </div>
      </section>
    {/if}

    {#if canWeave && proposal.status === "consent"}
      <section class="card action-card" aria-labelledby="veto-heading">
        <h2 id="veto-heading">Begründetes Veto einlegen</h2>
        <p>Ein Veto verhindert keine Entscheidung. Es eröffnet nach Ablauf der ersten sieben Tage eine weitere siebentägige Gesprächs- und Abstimmungsphase.</p>
        <textarea bind:value={vetoReason} maxlength="2000" rows="4" placeholder="Konkreter Einwand und mögliche Lösung"></textarea>
        <button class="primary" on:click={veto} disabled={!vetoReason.trim() || submitting}>Veto einlegen</button>
      </section>
    {/if}

    {#if canWeave && proposal.status === "voting"}
      <section class="card action-card" aria-labelledby="vote-heading">
        <h2 id="vote-heading">Abstimmen</h2>
        <p>Es gibt keine Mindestbeteiligung. Der Antrag wird angenommen, wenn am Ende mehr Ja- als Nein-Stimmen vorliegen.</p>
        <div class="vote-buttons">
          {#each ["ja", "nein", "enthaltung"] as choice}
            <button class:active={proposal.own_vote === choice} on:click={() => vote(choice as VoteChoice)} disabled={submitting}>
              {choice === "ja" ? "Ja" : choice === "nein" ? "Nein" : "Enthaltung"}
            </button>
          {/each}
        </div>
      </section>
    {/if}

    <section class="card" aria-labelledby="conversation-heading">
      <h2 id="conversation-heading">Gesprächsraum</h2>
      {#if messages.length === 0}<p class="muted">Noch keine Gesprächsbeiträge.</p>{/if}
      <div class="entries">
        {#each messages as message}
          <article>
            <div class="entry-meta"><strong>{message.author_title}</strong><time datetime={message.created_at}>{new Date(message.created_at).toLocaleString("de-DE")}</time></div>
            <p>{message.body}</p>
          </article>
        {/each}
      </div>
      {#if canWeave && isOpen}
        <div class="message-form">
          <label for="message-body">Beitrag verfassen</label>
          <textarea id="message-body" bind:value={messageBody} maxlength="4000" rows="4"></textarea>
          <button class="primary" on:click={postMessage} disabled={!messageBody.trim() || submitting}>Beitrag senden</button>
        </div>
      {:else if $authStore.role === "gast"}
        <p class="guest-note">Als Gast kannst du den Gesprächsraum lesen. Schreiben, Veto und Abstimmung sind Webungsaktionen und beginnen erst mit dem Weberstatus.</p>
      {/if}
    </section>
  {/if}
</main>

<style>
  :global(body) { margin: 0; background: #f3f1e9; color: #18251f; font-family: system-ui, sans-serif; }
  .page-shell { width: min(820px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0 72px; }
  .back-link { color: inherit; text-decoration: none; font-weight: 700; }
  .proposal-header { padding: 44px 0 28px; }
  .topline, .entry-meta, dl, .vote-buttons { display: flex; gap: 12px; align-items: center; }
  .topline { justify-content: space-between; color: #526259; }
  .topline span { padding: 5px 10px; border-radius: 999px; background: #e4e3dc; }
  .topline span.open { background: #dcecdf; color: #1f5b42; }
  .eyebrow { margin: 28px 0 5px; text-transform: uppercase; letter-spacing: .09em; font-size: .76rem; font-weight: 750; color: #4d6759; }
  h1 { margin: 0; font-size: clamp(2.2rem, 8vw, 4.2rem); line-height: 1; }
  h2 { margin: 0 0 12px; }
  .summary { max-width: 65ch; font-size: 1.1rem; line-height: 1.6; }
  dl { flex-wrap: wrap; margin: 24px 0 0; }
  dl div { min-width: 150px; }
  dt { color: #607168; font-size: .8rem; }
  dd { margin: 3px 0 0; font-weight: 700; }
  .card, .error { border: 1px solid rgba(24,37,31,.16); border-radius: 18px; background: rgba(255,255,255,.72); padding: 22px; margin-top: 16px; }
  .action-card { background: #eef3ec; }
  .entries { display: grid; gap: 14px; }
  article { border-top: 1px solid rgba(24,37,31,.12); padding-top: 14px; }
  article:first-child { border-top: 0; padding-top: 0; }
  .entry-meta { justify-content: space-between; color: #607168; font-size: .84rem; }
  article p { margin-bottom: 0; white-space: pre-wrap; line-height: 1.5; }
  textarea { box-sizing: border-box; width: 100%; resize: vertical; border: 1px solid rgba(24,37,31,.28); border-radius: 12px; padding: 12px; font: inherit; background: #fff; }
  button { border: 1px solid rgba(24,37,31,.25); border-radius: 999px; padding: 10px 16px; font: inherit; font-weight: 720; cursor: pointer; background: #fff; }
  button.active { outline: 3px solid rgba(31,91,66,.28); background: #dcecdf; }
  button:disabled { opacity: .55; cursor: wait; }
  .primary { border: 0; background: #1f5b42; color: #fff; }
  .action-card, .message-form { display: grid; gap: 12px; }
  .message-form { margin-top: 20px; }
  .vote-buttons { flex-wrap: wrap; }
  .error { color: #7f2424; background: #fff0f0; }
  .muted, .guest-note { color: #607168; }
  .guest-note { padding: 12px; border-radius: 10px; background: #eeece5; }
  @media (max-width: 560px) { .topline, .entry-meta { align-items: flex-start; flex-direction: column; } }
</style>
