<script lang="ts">
  import { onMount } from "svelte";
  import { authStore } from "$lib/auth/store";
  import {
    createWeberProposal,
    formatRemaining,
    GovernanceApiError,
    listProposals,
    statusLabel,
    type Proposal,
  } from "$lib/api/governance";

  export let centerId: string;
  export let proposalCount: number | null = null;
  export let openProposalCount: number | null = null;
  export let votingProposalCount: number | null = null;

  let proposals: Proposal[] = [];
  let loading = true;
  let error = "";
  let summary = "";
  let submitting = false;
  let submitError = "";
  let mounted = false;
  let loadedCenterId = "";
  let loadGeneration = 0;

  $: centerProposals = proposals.filter(
    (proposal) => proposal.webgemeindezentrum_id === centerId,
  );
  $: activeProposals = centerProposals.filter(
    (proposal) => proposal.status === "consent" || proposal.status === "voting",
  );
  $: ownOpenProposal = activeProposals.some(
    (proposal) => proposal.applicant_account_id === $authStore.account_id,
  );
  $: displayedProposalCount =
    loading || error ? proposalCount : centerProposals.length;
  $: displayedOpenProposalCount =
    loading || error ? openProposalCount : activeProposals.length;
  $: displayedVotingProposalCount =
    loading || error
      ? votingProposalCount
      : centerProposals.filter((proposal) => proposal.status === "voting")
          .length;
  $: canApply =
    $authStore.authenticated && $authStore.role === "gast" && !ownOpenProposal;

  async function load() {
    const generation = ++loadGeneration;
    loading = true;
    try {
      const listed = await listProposals();
      if (generation !== loadGeneration) return;
      proposals = listed;
      error = "";
    } catch (loadError) {
      if (generation !== loadGeneration) return;
      console.error(loadError);
      error = "Anträge können gerade nicht geladen werden.";
    } finally {
      if (generation === loadGeneration) loading = false;
    }
  }

  async function submitApplication() {
    if (submitting || !canApply) return;
    submitting = true;
    submitError = "";
    try {
      const proposal = await createWeberProposal(summary, centerId);
      proposals = [
        proposal,
        ...proposals.filter((item) => item.id !== proposal.id),
      ];
      summary = "";
    } catch (submitFailure) {
      submitError =
        submitFailure instanceof GovernanceApiError &&
        submitFailure.status === 409
          ? "Für diese Garnrolle besteht bereits ein offener Weberantrag."
          : "Der Weberantrag konnte nicht gespeichert werden.";
    } finally {
      submitting = false;
    }
  }

  $: if (mounted && centerId !== loadedCenterId) {
    loadedCenterId = centerId;
    summary = "";
    submitError = "";
    void load();
  }

  onMount(() => {
    mounted = true;
    loadedCenterId = centerId;
    void load();
    return () => {
      mounted = false;
      loadGeneration += 1;
    };
  });
</script>

<section
  class="governance"
  aria-labelledby="center-governance-heading"
  data-testid="center-governance"
>
  <header>
    <div>
      <p class="eyebrow">Örtliche Selbstverwaltung</p>
      <h4 id="center-governance-heading">Governance der Ortsweberei</h4>
    </div>
    <a href="/antraege">Vollansicht</a>
  </header>

  <dl class="counts" aria-label="Governance-Überblick">
    <div>
      <dt>Alle Anträge</dt>
      <dd>{displayedProposalCount ?? "—"}</dd>
    </div>
    <div>
      <dt>Offen</dt>
      <dd>{displayedOpenProposalCount ?? "—"}</dd>
    </div>
    <div>
      <dt>Abstimmung</dt>
      <dd>{displayedVotingProposalCount ?? "—"}</dd>
    </div>
  </dl>

  {#if loading}
    <p class="muted" role="status">Lade Anträge…</p>
  {:else if error}
    <p class="error" role="alert">{error}</p>
  {:else if activeProposals.length > 0}
    <ol class="proposals">
      {#each activeProposals.slice(0, 5) as proposal (proposal.id)}
        <li>
          <a href={`/antraege?id=${encodeURIComponent(proposal.id)}`}>
            <strong>{proposal.applicant_title}</strong>
            <span
              >{statusLabel(proposal.status)} · {formatRemaining(
                proposal.remaining_seconds,
              )}</span
            >
            {#if proposal.summary}<p>{proposal.summary}</p>{/if}
          </a>
        </li>
      {/each}
    </ol>
  {:else}
    <p class="muted">Derzeit ist kein Antrag in einer offenen Phase.</p>
  {/if}

  {#if canApply}
    <form class="application" on:submit|preventDefault={submitApplication}>
      <label for="center-weber-application">Weberstatus beantragen</label>
      <textarea
        id="center-weber-application"
        bind:value={summary}
        maxlength="1000"
        rows="3"
        placeholder="Warum möchtest du als Weber mitwirken?"></textarea>
      {#if submitError}<p class="error" role="alert">{submitError}</p>{/if}
      <button type="submit" disabled={submitting}>
        {submitting ? "Antrag wird geknüpft…" : "Weberantrag stellen"}
      </button>
    </form>
  {:else if ownOpenProposal}
    <p class="muted">Dein Weberantrag ist bereits offen und oben verlinkt.</p>
  {:else if !$authStore.authenticated}
    <p class="muted">Melde dich an, um Anträge zu stellen oder mitzuwirken.</p>
  {/if}
</section>

<style>
  .governance {
    display: grid;
    gap: 0.75rem;
    padding: 1rem;
    border: 1px solid var(--panel-border);
    border-radius: 1rem;
  }
  header,
  .counts {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
  }
  h4,
  p,
  dl,
  ol {
    margin: 0;
  }
  .eyebrow,
  .muted,
  .proposals span {
    color: var(--muted);
    font-size: 0.85rem;
  }
  dd {
    margin: 0;
  }
  .proposals {
    padding-left: 1.25rem;
  }
  .proposals a,
  .application {
    display: grid;
    gap: 0.25rem;
  }
  textarea {
    box-sizing: border-box;
    width: 100%;
  }
  .error {
    color: var(--danger, #a21d1d);
  }
</style>
