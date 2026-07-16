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
  type SheetStage = "preview" | "half" | "full";

  const dispatch = createEventDispatcher<{
    selectRelated: RelatedSelection;
    domainChanged: DomainChanged;
  }>();
  let kompositionPanel: KompositionPanelHandle | null = null;
  let sheetStage: SheetStage = "preview";
  let previousPanelIdentity = "";

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
  $: panelIdentity =
    $systemState === "komposition"
      ? `komposition:${$kompositionDraft?.mode ?? "unknown"}`
      : $selection
        ? `${$selection.type}:${$selection.id}`
        : "";
  $: if (panelIdentity !== previousPanelIdentity) {
    previousPanelIdentity = panelIdentity;
    sheetStage = $systemState === "komposition" ? "full" : "preview";
  }
  $: if ($systemState === "komposition" && sheetStage !== "full") {
    sheetStage = "full";
  }

  function closePanel() {
    if ($systemState === "komposition") {
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
  <aside
    class="context-panel"
    class:stage-preview={sheetStage === "preview"}
    class:stage-half={sheetStage === "half"}
    class:stage-full={sheetStage === "full"}
    class:composition={$systemState === "komposition"}
    data-testid="context-panel"
    data-sheet-stage={sheetStage}
    aria-label={panelTitle}
  >
    <header
      class="panel-header"
      class:composition={$systemState === "komposition"}
    >
      <div class="heading-group">
        <span class="sheet-handle" aria-hidden="true"></span>
        <h2>{panelTitle}</h2>
      </div>
      <div class="header-actions">
        {#if $systemState !== "komposition"}
          <div class="sheet-controls" role="group" aria-label="Panelgröße">
            <button
              type="button"
              aria-label="Kompakte Vorschau"
              aria-pressed={sheetStage === "preview"}
              on:click={() => (sheetStage = "preview")}>Kompakt</button
            >
            <button
              type="button"
              aria-label="Halbe Ansicht"
              aria-pressed={sheetStage === "half"}
              on:click={() => (sheetStage = "half")}>Halb</button
            >
            <button
              type="button"
              aria-label="Volle Ansicht"
              aria-pressed={sheetStage === "full"}
              on:click={() => (sheetStage = "full")}>Voll</button
            >
          </div>
        {/if}
        <button class="close-btn" on:click={closePanel} aria-label="Schließen"
          >✕</button
        >
      </div>
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
    min-height: 64px;
    padding: 0.6rem 0.8rem 0.6rem 1rem;
    border-bottom: 1px solid var(--panel-border);
    flex: 0 0 auto;
  }

  .heading-group {
    min-width: 0;
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

  .sheet-handle {
    display: none;
  }

  .header-actions,
  .sheet-controls {
    display: flex;
    align-items: center;
  }

  .header-actions {
    gap: 0.35rem;
  }

  .sheet-controls {
    gap: 0.2rem;
  }

  .sheet-controls button {
    min-height: 36px;
    padding: 0 0.55rem;
    border: 1px solid transparent;
    border-radius: 9px;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    font-size: 0.76rem;
  }

  .sheet-controls button[aria-pressed="true"] {
    border-color: var(--panel-border-strong);
    background: var(--accent-soft);
    color: var(--text);
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
    overscroll-behavior: contain;
  }

  @media (max-width: 768px) {
    .context-panel {
      bottom: 0;
      left: 0;
      right: 0;
      max-height: none;
      padding-bottom: env(safe-area-inset-bottom);
      border-radius: 18px 18px 0 0;
      transition: height 0.22s ease;
    }
    .context-panel.stage-preview {
      height: clamp(190px, 29dvh, 270px);
    }
    .context-panel.stage-half {
      height: 55dvh;
    }
    .context-panel.stage-full,
    .context-panel.composition {
      height: 88dvh;
    }
    .sheet-handle {
      display: block;
      width: 42px;
      height: 4px;
      margin: 0 auto 0.45rem;
      border-radius: 999px;
      background: var(--panel-border-strong);
    }
    .panel-header {
      min-height: 72px;
      padding-top: 0.45rem;
    }
    .heading-group {
      flex: 1;
      text-align: left;
    }
    .sheet-controls button {
      min-width: 44px;
      min-height: 44px;
      padding: 0 0.35rem;
      font-size: 0.7rem;
    }
    .stage-preview .panel-content {
      padding-top: 0.65rem;
    }
  }

  @media (max-width: 440px) {
    .sheet-controls button {
      width: 44px;
      overflow: hidden;
      color: transparent;
      position: relative;
    }
    .sheet-controls button::after {
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      color: var(--muted);
      font-size: 1rem;
    }
    .sheet-controls button:nth-child(1)::after {
      content: "▂";
    }
    .sheet-controls button:nth-child(2)::after {
      content: "▅";
    }
    .sheet-controls button:nth-child(3)::after {
      content: "▇";
    }
    .sheet-controls button[aria-pressed="true"]::after {
      color: var(--accent);
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
    .sheet-controls {
      display: none;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .context-panel {
      transition: none;
    }
  }
</style>
