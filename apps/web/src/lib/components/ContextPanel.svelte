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
  import type { MapEntityViewModel } from "$lib/map/types";

  import NodePanel from "./panels/NodePanel.svelte";
  import AccountPanel from "./panels/AccountPanel.svelte";
  import EdgePanel from "./panels/EdgePanel.svelte";
  import KompositionPanel from "./panels/KompositionPanel.svelte";

  type RelatedSelection = {
    type: "node" | "garnrolle";
    id: string;
    title?: string;
    data?: MapEntityViewModel;
  };
  type DomainChanged = {
    kind: "node";
    id: string;
    action: "updated" | "deleted";
  };
  type KompositionPanelHandle = { requestClose: () => void };
  type SheetStage = "preview" | "full";

  const dispatch = createEventDispatcher<{
    selectRelated: RelatedSelection;
    domainChanged: DomainChanged;
  }>();
  let kompositionPanel: KompositionPanelHandle | null = null;
  let sheetStage: SheetStage = "preview";
  let previousPanelIdentity = "";
  let panelTitle = "Details";
  let dragStartY = 0;
  let dragStartHeight = 0;
  let dragHeight: number | null = null;
  let dragging = false;
  let dragMoved = false;

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
      dragMoved = false;
    }
  }

  function setSheetStage(stage: SheetStage): void {
    sheetStage = stage;
    dragHeight = null;
    dragging = false;
    dragMoved = false;
  }

  function toggleSheetStage(): void {
    setSheetStage(sheetStage === "preview" ? "full" : "preview");
  }

  function nearestSheetStage(height: number): SheetStage {
    const viewport = window.innerHeight;
    const preview = Math.min(270, Math.max(190, viewport * 0.29));
    return height < (preview + viewport * 0.88) / 2 ? "preview" : "full";
  }

  function handleSheetPointerDown(event: PointerEvent): void {
    const handle = event.currentTarget as HTMLElement;
    const aside = handle.closest<HTMLElement>('[data-testid="context-panel"]');
    if (!aside) return;
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    dragStartY = event.clientY;
    dragStartHeight = aside.getBoundingClientRect().height;
    dragHeight = dragStartHeight;
    dragging = true;
    dragMoved = false;
  }

  function handleSheetPointerMove(event: PointerEvent): void {
    if (!dragging) return;
    const minHeight = 190;
    const maxHeight = window.innerHeight * 0.88;
    dragMoved = dragMoved || Math.abs(event.clientY - dragStartY) > 6;
    dragHeight = Math.min(
      maxHeight,
      Math.max(minHeight, dragStartHeight + dragStartY - event.clientY),
    );
  }

  function releasePointer(event: PointerEvent): void {
    const handle = event.currentTarget as HTMLElement;
    if (handle.hasPointerCapture(event.pointerId)) {
      handle.releasePointerCapture(event.pointerId);
    }
  }

  function handleSheetPointerUp(event: PointerEvent): void {
    if (!dragging) return;
    releasePointer(event);
    setSheetStage(
      dragMoved
        ? nearestSheetStage(dragHeight ?? dragStartHeight)
        : sheetStage === "preview"
          ? "full"
          : "preview",
    );
  }

  function handleSheetPointerCancel(event: PointerEvent): void {
    if (!dragging) return;
    releasePointer(event);
    setSheetStage(sheetStage);
  }

  function handleSheetClick(event: MouseEvent): void {
    if (event.detail === 0) toggleSheetStage();
  }

  function handleSheetKeydown(event: KeyboardEvent): void {
    const stage =
      event.key === "ArrowUp" || event.key === "End"
        ? "full"
        : event.key === "ArrowDown" || event.key === "Home"
          ? "preview"
          : null;
    if (!stage) return;
    event.preventDefault();
    setSheetStage(stage);
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
    ) {
      closePanel();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if $contextPanelOpen}
  <aside
    class="context-panel"
    class:stage-preview={sheetStage === "preview"}
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
      aria-label={`Panel, ${sheetStage === "preview" ? "Kompaktkarte" : "Vollansicht"}; ziehen oder wechseln`}
      aria-pressed={sheetStage === "full"}
      on:pointerdown={handleSheetPointerDown}
      on:pointermove={handleSheetPointerMove}
      on:pointerup={handleSheetPointerUp}
      on:pointercancel={handleSheetPointerCancel}
      on:click={handleSheetClick}
      on:keydown={handleSheetKeydown}
    >
      <span aria-hidden="true"></span>
    </button>
    <header
      class="panel-header"
      class:composition={$systemState === "komposition"}
    >
      <div class="heading-group">
        <h2 class="desktop-heading">{panelTitle}</h2>
        <h2 class="mobile-heading">
          <button
            type="button"
            class="heading-toggle"
            aria-label={`${panelTitle}, ${sheetStage === "preview" ? "Kompaktkarte" : "Vollansicht"}; Ansicht wechseln`}
            aria-pressed={sheetStage === "full"}
            on:click={toggleSheetStage}
          >
            {panelTitle}
          </button>
        </h2>
      </div>
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
    flex: 1;
  }

  .panel-header h2 {
    margin: 0;
    color: var(--muted);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
  }

  .heading-toggle {
    max-width: 100%;
    margin: 0;
    padding: 0;
    border: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    font-weight: inherit;
    letter-spacing: inherit;
    text-align: left;
    text-transform: inherit;
  }

  .mobile-heading {
    display: none;
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
    overscroll-behavior: contain;
  }

  @media (max-width: 768px) {
    .desktop-heading {
      display: none;
    }

    .mobile-heading {
      display: block;
    }

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

    .sheet-handle:focus-visible,
    .heading-toggle:focus-visible {
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

    .heading-toggle {
      min-height: 44px;
      cursor: pointer;
    }

    .stage-preview .panel-content {
      padding-top: 0.65rem;
    }

    .stage-preview .panel-content :global(.tabs) {
      display: none;
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

  @media (prefers-reduced-motion: reduce) {
    .context-panel {
      transition: none;
    }
  }
</style>
