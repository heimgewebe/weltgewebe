<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import {
    selection,
    systemState,
    contextPanelOpen,
    kompositionDraft,
    leaveToNavigation,
  } from "$lib/stores/uiView";
  import { isSearchOpen } from "$lib/stores/searchStore";
  import { isFilterOpen } from "$lib/stores/filterStore";
  import type {
    KompositionDraft,
    Selection,
    SystemState,
  } from "$lib/stores/uiView";

  import NodePanel from "./panels/NodePanel.svelte";
  import AccountPanel from "./panels/AccountPanel.svelte";
  import EdgePanel from "./panels/EdgePanel.svelte";
  import KompositionPanel from "./panels/KompositionPanel.svelte";

  type RelatedSelection = { type: "node" | "garnrolle"; id: string };
  type DomainChanged = {
    kind: "node";
    id: string;
    action: "updated" | "deleted";
  };
  type KompositionPanelHandle = { requestClose: () => void };

  const dispatch = createEventDispatcher<{
    selectRelated: RelatedSelection;
    domainChanged: DomainChanged;
  }>();
  let kompositionPanel: KompositionPanelHandle | null = null;

  function derivePanelTitle(
    state: SystemState,
    draft: KompositionDraft,
    currentSelection: Selection,
  ): string {
    if (state === "komposition") {
      return draft?.mode === "place-garnrolle"
        ? "Garnrolle auf die Karte setzen"
        : "Knoten knüpfen";
    }

    if (currentSelection?.type === "node") return "Knoten";
    if (
      currentSelection?.type === "account" ||
      currentSelection?.type === "garnrolle"
    ) {
      return "Garnrolle";
    }
    if (currentSelection?.type === "edge") return "Faden";
    return "Details";
  }

  $: panelTitle = derivePanelTitle($systemState, $kompositionDraft, $selection);

  function closePanel() {
    if ($systemState === "komposition") {
      // Fail closed: while the child handle is not bound yet, never fall back
      // to discarding a composition draft or a partial-success state.
      kompositionPanel?.requestClose();
      return;
    }
    leaveToNavigation();
  }

  function handleRelated(event: CustomEvent<RelatedSelection>) {
    dispatch("selectRelated", event.detail);
  }

  function handleDomainChanged(event: CustomEvent<DomainChanged>) {
    dispatch("domainChanged", event.detail);
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.repeat || event.defaultPrevented) return;
    if (
      event.key === "Escape" &&
      $contextPanelOpen &&
      !$isSearchOpen &&
      !$isFilterOpen
    )
      closePanel();
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if $contextPanelOpen}
  <aside class="context-panel" data-testid="context-panel">
    <header
      class="panel-header"
      class:composition={$systemState === "komposition"}
    >
      <h2>{panelTitle}</h2>
      <button class="close-btn" on:click={closePanel} aria-label="Schließen"
        >✕</button
      >
    </header>

    <div class="panel-content">
      {#if $systemState === "komposition"}
        <KompositionPanel bind:this={kompositionPanel} />
      {:else if $selection}
        {#if $selection.type === "node"}
          <NodePanel
            on:selectRelated={handleRelated}
            on:domainChanged={handleDomainChanged}
          />
        {:else if $selection.type === "account" || $selection.type === "garnrolle"}
          <AccountPanel on:selectRelated={handleRelated} />
        {:else if $selection.type === "edge"}
          <EdgePanel />
        {/if}
      {/if}
    </div>
  </aside>
{/if}

<style>
  .context-panel {
    position: fixed;
    z-index: 50;
    background: var(--panel);
    color: var(--text);
    box-shadow: var(--shadow);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-sizing: border-box;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    min-height: 68px;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--panel-border);
    flex: 0 0 auto;
  }

  .panel-header h2 {
    margin: 0;
    color: var(--muted);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
  }

  .panel-header.composition h2 {
    color: var(--text);
    font-size: 1.1rem;
    letter-spacing: 0;
    text-transform: none;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 1.2rem;
    cursor: pointer;
    color: var(--text);
    min-width: 44px;
    min-height: 44px;
    display: grid;
    place-items: center;
  }

  .panel-content {
    padding: 1rem;
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
  }

  @media (max-width: 768px) {
    .context-panel {
      bottom: 0;
      left: 0;
      right: 0;
      max-height: 80dvh;
      padding-bottom: env(safe-area-inset-bottom);
      border-radius: 16px 16px 0 0;
    }
  }

  @media (min-width: 769px) {
    .context-panel {
      top: 0;
      right: 0;
      bottom: 0;
      width: var(--context-panel-width);
      box-shadow: -4px 0 16px rgba(0, 0, 0, 0.28);
    }
  }
</style>
