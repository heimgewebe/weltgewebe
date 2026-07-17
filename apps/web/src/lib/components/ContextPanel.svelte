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
  const SHEET_STAGES: SheetStage[] = ["preview", "half", "full"];
  let sheetStage: SheetStage = "preview";
  let previousPanelIdentity = "";
  let panelTitle = "Details";
  let dragStartY = 0;
  let dragStartHeight = 0;
  let dragHeight: number | null = null;
  let dragging = false;

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

  $: {
    panelTitle = derivePanelTitle($systemState, $kompositionDraft, $selection);
    const nextPanelIdentity =
      $systemState === "komposition"
        ? `komposition:${$kompositionDraft?.mode ?? "unknown"}`
        : $selection
          ? `${$selection.type}:${$selection.id}`
          : "";

    if (nextPanelIdentity !== previousPanelIdentity) {
      previousPanelIdentity = nextPanelIdentity;
      sheetStage = $systemState === "komposition" ? "full" : "preview";
      dragHeight = null;
      dragging = false;
    }
  }

  function setSheetStage(stage: SheetStage): void {
    sheetStage = stage;
    dragHeight = null;
    dragging = false;
  }

  function stepSheetStage(direction: -1 | 1): void {
    const index = SHEET_STAGES.indexOf(sheetStage);
    const next = Math.min(
      SHEET_STAGES.length - 1,
      Math.max(0, index + direction),
    );
    setSheetStage(SHEET_STAGES[next]);
  }

  function nearestSheetStage(height: number): SheetStage {
    const viewport = window.innerHeight;
    const preview = Math.min(270, Math.max(190, viewport * 0.29));
    const targets: Array<[SheetStage, number]> = [
      ["preview", preview],
      ["half", viewport * 0.55],
      ["full", viewport * 0.88],
    ];
    return targets.reduce((nearest, current) =>
      Math.abs(current[1] - height) < Math.abs(nearest[1] - height)
        ? current
        : nearest,
    )[0];
  }

  function handleSheetPointerDown(event: PointerEvent): void {
    if (window.innerWidth > 768) return;
    const panel = event.currentTarget as HTMLElement;
    const aside = panel.closest<HTMLElement>('[data-testid="context-panel"]');
    if (!aside) return;
    event.preventDefault();
    panel.setPointerCapture(event.pointerId);
    dragStartY = event.clientY;
    dragStartHeight = aside.getBoundingClientRect().height;
    dragHeight = dragStartHeight;
    dragging = true;
  }

  function handleSheetPointerMove(event: PointerEvent): void {
    if (!dragging) return;
    const minHeight = 190;
    const maxHeight = window.innerHeight * 0.88;
    dragHeight = Math.min(
      maxHeight,
      Math.max(minHeight, dragStartHeight + dragStartY - event.clientY),
    );
  }

  function handleSheetPointerUp(event: PointerEvent): void {
    if (!dragging) return;
    const panel = event.currentTarget as HTMLElement;
    if (panel.hasPointerCapture(event.pointerId)) {
      panel.releasePointerCapture(event.pointerId);
    }
    const finalHeight = dragHeight ?? dragStartHeight;
    setSheetStage(nearestSheetStage(finalHeight));
  }

  function handleSheetKeydown(event: KeyboardEvent): void {
    if (event.key === "ArrowUp") {
      event.preventDefault();
      stepSheetStage(1);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      stepSheetStage(-1);
    } else if (event.key === "Home") {
      event.preventDefault();
      setSheetStage("preview");
    } else if (event.key === "End") {
      event.preventDefault();
      setSheetStage("full");
    }
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
    class:dragging
    data-testid="context-panel"
    data-sheet-stage={sheetStage}
    aria-label={panelTitle}
    style={dragHeight === null ? undefined : `height: ${dragHeight}px`}
  >
    <button
      type="button"
      class="sheet-handle"
      data-testid="sheet-handle"
      aria-label={`Panelhöhe ziehen, aktuell ${
        sheetStage === "preview"
          ? "Vorschau"
          : sheetStage === "half"
            ? "halbe Höhe"
            : "Vollbild"
      }`}
      on:pointerdown={handleSheetPointerDown}
      on:pointermove={handleSheetPointerMove}
      on:pointerup={handleSheetPointerUp}
      on:pointercancel={handleSheetPointerUp}
      on:keydown={handleSheetKeydown}
    >
      <span aria-hidden="true"></span>
    </button>
    <header
      class="panel-header"
      class:composition={$systemState === "komposition"}
    >
      <div class="heading-group">
        <h2>{panelTitle}</h2>
      </div>
      <div class="header-actions">
        <div class="sheet-controls" role="group" aria-label="Panelgröße">
          <button
            type="button"
            aria-label="Vorschau"
            aria-pressed={sheetStage === "preview"}
            on:click={() => setSheetStage("preview")}>Vorschau</button
          >
          <button
            type="button"
            aria-label="Halbe Höhe"
            aria-pressed={sheetStage === "half"}
            on:click={() => setSheetStage("half")}>Halbe Höhe</button
          >
          <button
            type="button"
            aria-label="Vollbild"
            aria-pressed={sheetStage === "full"}
            on:click={() => setSheetStage("full")}>Vollbild</button
          >
        </div>
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
    z-index: var(--z-map-context-panel);
    background: var(--panel);
    color: var(--text);
    box-shadow: var(--shadow);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-sizing: border-box;
  }

  .sheet-handle {
    display: none;
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
    min-width: 44px;
    min-height: 44px;
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
      transition: height var(--motion-ui);
    }
    .context-panel.stage-preview {
      height: clamp(190px, 29dvh, 270px);
    }
    .context-panel.stage-half {
      height: 55dvh;
    }
    .context-panel.stage-full {
      height: 88dvh;
    }
    .sheet-handle {
      width: 100%;
      min-height: 44px;
      margin: 0;
      padding: 0;
      border: 0;
      background: transparent;
      display: grid;
      place-items: center;
      cursor: ns-resize;
      touch-action: none;
    }
    .sheet-handle span {
      width: 44px;
      height: 4px;
      border-radius: 999px;
      background: var(--panel-border-strong);
    }
    .sheet-handle:focus-visible {
      outline: 3px solid var(--accent);
      outline-offset: -4px;
    }
    .context-panel.dragging {
      transition: none;
      user-select: none;
    }
    .panel-header {
      min-height: 64px;
      padding-top: 0.25rem;
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
