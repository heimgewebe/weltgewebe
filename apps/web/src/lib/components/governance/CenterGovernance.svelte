<script lang="ts">
  import { onMount } from "svelte";
  import { authStore } from "$lib/auth/store";
  import {
    createSachProposal,
    createWeberProposal,
    formatRemaining,
    GovernanceApiError,
    listProposals,
    proposalTitle,
    statusLabel,
    type Proposal,
  } from "$lib/api/governance";

  interface Props {
    centerId: string;
    proposalCount?: number | null;
    openProposalCount?: number | null;
    votingProposalCount?: number | null;
  }

  let {
    centerId,
    proposalCount = null,
    openProposalCount = null,
    votingProposalCount = null,
  }: Props = $props();

  let proposals: Proposal[] = $state([]);
  let loading = $state(true);
  let error = $state("");
  let summary = $state("");
  let sachTitle = $state("");
  let sachSummary = $state("");
  let submitting = $state(false);
  let submitError = $state("");
  let mounted = $state(false);
  let loadedCenterId = $state("");
  let loadGeneration = 0;

  let centerProposals = $derived(
    proposals.filter((proposal) => proposal.webgemeindezentrum_id === centerId),
  );
  let activeProposals = $derived(
    centerProposals.filter(
      (proposal) =>
        proposal.status === "consent" || proposal.status === "voting",
    ),
  );
  let ownOpenProposal = $derived(
    activeProposals.some(
      (proposal) =>
        proposal.kind === "weberantrag" &&
        proposal.applicant_account_id === $authStore.account_id,
    ),
  );
  let displayedProposalCount = $derived(
    loading || error ? proposalCount : centerProposals.length,
  );
  let displayedOpenProposalCount = $derived(
    loading || error ? openProposalCount : activeProposals.length,
  );
  let displayedVotingProposalCount = $derived(
    loading || error
      ? votingProposalCount
      : centerProposals.filter((proposal) => proposal.status === "voting")
          .length,
  );
  let canApplyForWeber = $derived(
    $authStore.authenticated && $authStore.role === "gast" && !ownOpenProposal,
  );
  let canCreateSach = $derived(
    $authStore.authenticated &&
      ($authStore.role === "weber" || $authStore.role === "admin"),
  );

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
    if (submitting || !canApplyForWeber) return;
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

  async function submitSachProposal() {
    if (submitting || !canCreateSach || !sachTitle.trim()) return;
    submitting = true;
    submitError = "";
    try {
      const proposal = await createSachProposal(
        sachTitle,
        sachSummary,
        centerId,
      );
      proposals = [
        proposal,
        ...proposals.filter((item) => item.id !== proposal.id),
      ];
      sachTitle = "";
      sachSummary = "";
    } catch (submitFailure) {
      console.error(submitFailure);
      submitError = "Der Sachantrag konnte nicht gespeichert werden.";
    } finally {
      submitting = false;
    }
  }

  $effect(() => {
    if (mounted && centerId !== loadedCenterId) {
      loadedCenterId = centerId;
      summary = "";
      sachTitle = "";
      sachSummary = "";
      submitError = "";
      void load();
    }
  });

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
  {:else if centerProposals.length > 0}
    <ol class="proposals">
      {#each centerProposals.slice(0, 5) as proposal (proposal.id)}
        <li>
          <a href={`/antraege?id=${encodeURIComponent(proposal.id)}`}>
            <strong>{proposalTitle(proposal)}</strong>
            <span
              >{proposal.kind === "sachantrag" ? "Sachantrag" : "Weberantrag"}
              · {statusLabel(proposal.status)} · {formatRemaining(
                proposal.remaining_seconds,
              )}</span
            >
            {#if proposal.summary}<p>{proposal.summary}</p>{/if}
          </a>
        </li>
      {/each}
    </ol>
  {:else}
    <p class="muted">Für dieses Zentrum liegt noch kein Antrag vor.</p>
  {/if}

  {#if canApplyForWeber}
    <form
      class="application"
      onsubmit={(event) => {
        event.preventDefault();
        void submitApplication();
      }}
    >
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

  {#if canCreateSach}
    <form
      class="application"
      onsubmit={(event) => {
        event.preventDefault();
        void submitSachProposal();
      }}
    >
      <label for="center-sach-title">Sachantrag stellen</label>
      <input
        id="center-sach-title"
        bind:value={sachTitle}
        maxlength="200"
        required
        placeholder="Worüber soll die Ortsweberei entscheiden?"
      />
      <label for="center-sach-summary">Begründung</label>
      <textarea
        id="center-sach-summary"
        bind:value={sachSummary}
        maxlength="2000"
        rows="3"
        placeholder="Ausgangslage und gewünschter Beschluss"></textarea>
      {#if submitError}<p class="error" role="alert">{submitError}</p>{/if}
      <button type="submit" disabled={submitting || !sachTitle.trim()}>
        {submitting ? "Antrag wird geknüpft…" : "Sachantrag stellen"}
      </button>
    </form>
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
  input,
  textarea {
    box-sizing: border-box;
    width: 100%;
  }
  .error {
    color: var(--danger, #a21d1d);
  }
</style>
