<script lang="ts">
  import { onMount } from "svelte";
  import { authStore } from "$lib/auth/store";
  import {
    createSachProposal,
    formatRemaining,
    listProposals,
    proposalTitle,
    statusLabel,
    type Proposal,
  } from "$lib/api/governance";

  interface Props {
    nodeId: string;
    nodeTitle: string;
    centerId?: string | undefined;
  }

  let { nodeId, nodeTitle, centerId = undefined }: Props = $props();

  let proposals: Proposal[] = $state([]);
  let loading = $state(true);
  let error = $state("");
  let title = $state("");
  let summary = $state("");
  let submitting = $state(false);
  let mounted = $state(false);
  let loadedNodeId = $state("");
  let loadGeneration = 0;

  let nodeProposals = $derived(
    proposals.filter(
      (proposal) =>
        proposal.kind === "sachantrag" && proposal.target_node_id === nodeId,
    ),
  );
  let canCreate = $derived(
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
    } catch (cause) {
      if (generation !== loadGeneration) return;
      console.error(cause);
      error = "Anträge für diesen Knoten können gerade nicht geladen werden.";
    } finally {
      if (generation === loadGeneration) loading = false;
    }
  }

  async function submit() {
    if (!canCreate || submitting || !title.trim()) return;
    submitting = true;
    error = "";
    try {
      const proposal = await createSachProposal(
        title,
        summary,
        centerId,
        nodeId,
      );
      proposals = [
        proposal,
        ...proposals.filter((item) => item.id !== proposal.id),
      ];
      title = "";
      summary = "";
    } catch (cause) {
      console.error(cause);
      error = "Der Sachantrag konnte nicht gespeichert werden.";
    } finally {
      submitting = false;
    }
  }

  $effect(() => {
    if (mounted && nodeId !== loadedNodeId) {
      loadedNodeId = nodeId;
      title = "";
      summary = "";
      void load();
    }
  });

  onMount(() => {
    mounted = true;
    loadedNodeId = nodeId;
    void load();
    return () => {
      mounted = false;
      loadGeneration += 1;
    };
  });
</script>

<section class="node-governance" aria-labelledby="node-governance-heading">
  <div>
    <h4 id="node-governance-heading">Anträge zu diesem Knoten</h4>
    <p class="muted">
      Ein Knoten-Sachantrag ist derselbe Beschluss im Webrat der Ortsweberei.
    </p>
  </div>

  {#if loading}
    <p class="muted" role="status">Anträge werden geladen…</p>
  {:else if error && nodeProposals.length === 0}
    <p class="error" role="alert">{error}</p>
  {:else if nodeProposals.length > 0}
    <ol>
      {#each nodeProposals as proposal (proposal.id)}
        <li>
          <a href={`/antraege?id=${encodeURIComponent(proposal.id)}`}>
            <strong>{proposalTitle(proposal)}</strong>
            <span>
              {statusLabel(proposal.status)} · {formatRemaining(
                proposal.remaining_seconds,
              )}
            </span>
            {#if proposal.summary}<p>{proposal.summary}</p>{/if}
          </a>
        </li>
      {/each}
    </ol>
  {:else}
    <p class="muted">Zu diesem Knoten liegt noch kein Sachantrag vor.</p>
  {/if}

  {#if error && nodeProposals.length > 0}<p class="error" role="alert">
      {error}
    </p>{/if}

  {#if canCreate}
    <form
      onsubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <label for="node-sach-title">Sachantrag zu „{nodeTitle}“</label>
      <input
        id="node-sach-title"
        bind:value={title}
        maxlength="200"
        required
        placeholder="Gewünschten Beschluss benennen"
      />
      <label for="node-sach-summary">Begründung</label>
      <textarea
        id="node-sach-summary"
        bind:value={summary}
        maxlength="2000"
        rows="4"
        placeholder="Ausgangslage und Gründe"></textarea>
      <button type="submit" disabled={submitting || !title.trim()}>
        {submitting ? "Antrag wird gestellt…" : "Sachantrag stellen"}
      </button>
    </form>
  {/if}
</section>

<style>
  .node-governance,
  form,
  a {
    display: grid;
    gap: 0.5rem;
  }
  h4,
  p,
  ol {
    margin: 0;
  }
  ol {
    padding-left: 1.25rem;
  }
  a {
    color: inherit;
  }
  a span,
  .muted {
    color: var(--muted);
    font-size: 0.85rem;
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
