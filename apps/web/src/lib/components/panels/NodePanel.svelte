<script lang="ts">
  import { createEventDispatcher, onDestroy } from "svelte";
  import { selection } from "$lib/stores/uiView";
  import {
    buildPanelEndpoint,
    createPanelDetailsLoader,
  } from "$lib/panels/panelDetails";
  import { formatDate } from "$lib/utils/formatDate";
  import { nodeKindLabel } from "$lib/ui/productLanguage";

  const dispatch = createEventDispatcher<{
    selectRelated: { type: "garnrolle"; id: string };
  }>();
  let activeTab = "uebersicht";

  interface NodeDetails {
    id: string;
    title: string;
    summary?: string;
    created_at?: string;
    updated_at?: string;
    kind?: string;
    participants?: {
      account_title?: string;
      account_id: string;
      edge_kind?: string;
    }[];
    history?: { date: string; event: string }[];
  }

  const detailsLoader = createPanelDetailsLoader<NodeDetails>(selection, {
    buildEndpoint: (id) => buildPanelEndpoint("node", id),
    onSelectionChange: () => {
      activeTab = "uebersicht";
    },
    resourceLabel: "node details",
  });
  const nodeDetailsStore = detailsLoader.details;
  const isLoadingDetailsStore = detailsLoader.isLoading;
  onDestroy(detailsLoader.destroy);

  $: nodeDetails = $nodeDetailsStore;
  $: isLoadingDetails = $isLoadingDetailsStore;
  $: summary = nodeDetails?.summary || $selection?.data?.summary;
  $: kind = nodeKindLabel(nodeDetails?.kind || $selection?.data?.kind);

  const tabs = ["uebersicht", "verlauf"];
  function setTab(tab: string) {
    activeTab = tab;
  }
  function handleKeydown(e: KeyboardEvent) {
    const currentIndex = tabs.indexOf(activeTab);
    let nextIndex = currentIndex;
    if (e.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    else if (e.key === "ArrowLeft")
      nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") nextIndex = 0;
    else if (e.key === "End") nextIndex = tabs.length - 1;
    else return;
    e.preventDefault();
    setTab(tabs[nextIndex]);
    const buttons = (e.currentTarget as HTMLElement)
      ?.closest(".tabs")
      ?.querySelectorAll('button[role="tab"]');
    (buttons?.[nextIndex] as HTMLElement | undefined)?.focus();
  }
</script>

<div class="node-mode">
  <h3>{nodeDetails?.title || $selection?.data?.title || $selection?.id}</h3>
  {#if summary}<p class="summary">{summary}</p>{/if}

  <div class="tabs" role="tablist" aria-label="Knoten-Tabs">
    <button
      class:active={activeTab === "uebersicht"}
      on:click={() => setTab("uebersicht")}
      on:keydown={handleKeydown}
      role="tab"
      aria-selected={activeTab === "uebersicht"}
      aria-controls="panel-uebersicht"
      id="tab-uebersicht"
      tabindex={activeTab === "uebersicht" ? 0 : -1}>Übersicht</button
    >
    <button
      class:active={activeTab === "verlauf"}
      on:click={() => setTab("verlauf")}
      on:keydown={handleKeydown}
      role="tab"
      aria-selected={activeTab === "verlauf"}
      aria-controls="panel-verlauf"
      id="tab-verlauf"
      tabindex={activeTab === "verlauf" ? 0 : -1}>Verlauf</button
    >
  </div>

  <div class="tab-content">
    {#if activeTab === "uebersicht"}
      <div
        class="overview"
        id="panel-uebersicht"
        role="tabpanel"
        aria-labelledby="tab-uebersicht"
      >
        {#if isLoadingDetails}<p class="ghost">Lade Details…</p>
        {:else}
          {#if nodeDetails?.created_at || $selection?.data?.created_at}<p>
              <strong>Geknüpft am:</strong>
              {formatDate(
                nodeDetails?.created_at || $selection?.data?.created_at,
              )}
            </p>{/if}
          <p><strong>Knotenart:</strong> {kind}</p>
          {#if nodeDetails?.participants?.length}
            <div class="participants">
              <p><strong>Beteiligte Garnrollen</strong></p>
              <ul>
                {#each nodeDetails.participants as participant}<li>
                    <button
                      type="button"
                      on:click={() =>
                        dispatch("selectRelated", {
                          type: "garnrolle",
                          id: participant.account_id,
                        })}
                      >{participant.account_title ||
                        participant.account_id}</button
                    >
                  </li>{/each}
              </ul>
            </div>
          {/if}
        {/if}
      </div>
    {:else}
      <div id="panel-verlauf" role="tabpanel" aria-labelledby="tab-verlauf">
        {#if isLoadingDetails}<p class="ghost">Lade Verlauf…</p>
        {:else if nodeDetails?.history?.length}<ul class="timeline">
            {#each nodeDetails.history as event}<li>
                <span class="date">{formatDate(event.date)}</span><span
                  class="event">{event.event}</span
                >
              </li>{/each}
          </ul>
        {:else if nodeDetails?.created_at || $selection?.data?.created_at}<ul
            class="timeline"
          >
            <li>
              <span class="date"
                >{formatDate(
                  nodeDetails?.created_at || $selection?.data?.created_at,
                )}</span
              ><span class="event">Knoten wurde geknüpft.</span>
            </li>
          </ul>
        {:else}<p class="ghost">Noch kein Verlauf.</p>{/if}
      </div>
    {/if}
  </div>
</div>

<style>
  h3 {
    margin: 0;
    font-size: 1.5rem;
    line-height: 1.2;
  }
  .summary {
    color: var(--muted);
    margin: 0.5rem 0 1.25rem;
  }
  .ghost {
    color: var(--muted);
    font-size: 0.9rem;
  }
  .overview > p {
    margin: 0 0 0.65rem;
    font-size: 0.95rem;
  }
  .participants {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--panel-border);
  }
  .participants p {
    margin: 0 0 0.5rem;
  }
  .participants ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.5rem;
  }
  .participants button {
    width: 100%;
    min-height: 44px;
    padding: 0.65rem 0.75rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 8px;
    background: var(--panel-solid);
    color: var(--text);
    text-align: left;
    font-weight: 600;
    cursor: pointer;
  }
  .participants button:hover,
  .participants button:focus-visible {
    border-color: var(--accent);
  }
</style>
