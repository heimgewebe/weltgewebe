<script lang="ts">
  import { createEventDispatcher, onDestroy } from "svelte";
  import { nodeKindLabel } from "$lib/ui/productLanguage";
  import {
    buildSimilarNodeQuery,
    nodeToMapEntity,
    searchNodes,
  } from "$lib/api/search";
  import type { MapEntityNode, MapEntityViewModel } from "$lib/map/types";

  export let sourceId: string;
  export let title: string | null | undefined = null;
  export let kind: string | null | undefined = null;
  export let summary: string | null | undefined = null;
  export let info: string | null | undefined = null;
  export let tags: string[] | null | undefined = null;

  const dispatch = createEventDispatcher<{
    select: { type: "node"; id: string; data: MapEntityViewModel };
  }>();

  let similarNodes: MapEntityNode[] = [];
  let loading = false;
  let error = "";
  let mode: string | null = null;
  let previousKey = "";
  let abortController: AbortController | null = null;
  let requestSequence = 0;

  $: query = buildSimilarNodeQuery({ title, kind, summary, info, tags });

  async function load(query: string) {
    abortController?.abort();
    const controller = new AbortController();
    abortController = controller;
    const sequence = ++requestSequence;
    loading = true;
    error = "";
    mode = null;
    similarNodes = [];
    try {
      const response = await searchNodes(query, {
        limit: 6,
        signal: controller.signal,
      });
      if (controller.signal.aborted || sequence !== requestSequence) return;
      mode = response.mode;
      similarNodes = response.items
        .filter((item) => item.id !== sourceId)
        .map(nodeToMapEntity)
        .slice(0, 4);
    } catch {
      if (controller.signal.aborted || sequence !== requestSequence) return;
      error =
        "Maschinell berechnete ähnliche Knoten sind gerade nicht verfügbar.";
    } finally {
      if (sequence === requestSequence) loading = false;
      if (abortController === controller) abortController = null;
    }
  }

  $: {
    const key = sourceId && query ? `${sourceId}\u0000${query}` : "";
    if (key !== previousKey) {
      previousKey = key;
      requestSequence += 1;
      abortController?.abort();
      abortController = null;
      similarNodes = [];
      loading = false;
      error = "";
      mode = null;
      if (sourceId && query) void load(query);
    }
  }

  onDestroy(() => {
    requestSequence += 1;
    abortController?.abort();
  });
</script>

<section
  class="similar-nodes"
  aria-labelledby="similar-nodes-heading"
  aria-describedby="similar-nodes-explainer"
  aria-busy={loading}
>
  <h4 id="similar-nodes-heading">Ähnliche Knoten</h4>
  <p id="similar-nodes-explainer" class="similar-explainer">
    Maschinell aus Inhalt und Schlagwörtern dieses Knotens berechnet. Das sind
    Vorschläge – keine Fäden, keine kuratierten Beziehungen und keine Aussage
    über gemeinsame Autorenschaft.
  </p>
  {#if loading}
    <p class="ghost" role="status" aria-live="polite">
      Ähnliche Knoten werden berechnet…
    </p>
  {:else if error}
    <p class="similar-error" role="status" aria-live="polite">{error}</p>
  {:else}
    {#if mode === "lexical_fallback"}
      <p class="similar-note" role="status" aria-live="polite">
        Die semantische Ergänzung ist gerade nicht verfügbar; die Vorschläge
        stammen aus dem lexikalischen Serverpfad.
      </p>
    {/if}
    {#if similarNodes.length > 0}
      <p class="similar-result-status" role="status" aria-live="polite">
        {similarNodes.length} maschinell berechnete {similarNodes.length === 1
          ? "Ähnlichkeit"
          : "Ähnlichkeiten"} gefunden.
      </p>
      <ul aria-label="Maschinell berechnete ähnliche Knoten">
        {#each similarNodes as similar}
          <li>
            <button
              type="button"
              on:click={() =>
                dispatch("select", {
                  type: "node",
                  id: similar.id,
                  data: similar,
                })}
            >
              <span>{similar.title}</span>
              <small>{nodeKindLabel(similar.kind)}</small>
            </button>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="ghost" role="status" aria-live="polite">
        Keine ähnlichen Knoten gefunden.
      </p>
    {/if}
  {/if}
</section>

<style>
  .similar-nodes {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--panel-border);
  }
  h4 {
    margin: 0;
    font-size: 1rem;
  }
  .similar-explainer,
  .similar-note,
  .similar-error,
  .similar-result-status {
    margin: 0.45rem 0 0.65rem;
    font-size: 0.82rem;
    line-height: 1.4;
    color: var(--muted);
  }
  .similar-result-status {
    margin-top: 0;
  }
  .similar-error {
    color: var(--text);
    border-left: 3px solid color-mix(in srgb, #a33 70%, var(--text));
    padding-left: 0.6rem;
  }
  ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.5rem;
  }
  button {
    width: 100%;
    min-height: 44px;
    padding: 0.65rem 0.75rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 8px;
    background: var(--panel-solid);
    color: var(--text);
    text-align: left;
    cursor: pointer;
    display: grid;
    gap: 0.15rem;
  }
  button:hover,
  button:focus-visible {
    border-color: var(--accent);
  }
  button span {
    font-weight: 650;
  }
  button small {
    color: var(--muted);
  }
</style>
