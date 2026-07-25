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
  type SheetStage = "compact" | "full";

  const dispatch = createEventDispatcher<{
    selectRelated: RelatedSelection;
    domainChanged: DomainChanged;
  }>();
  const DRAG_THRESHOLD_PX = 6;
  const MOBILE_BREAKPOINT_PX = 768;

  let kompositionPanel: KompositionPanelHandle | null = null;
  let sheetStage: SheetStage = "compact";
  let previousPanelIdentity = "";
  let panelTitle = "Details";
  let dragStartY = 0;
  let dragStartHeight = 0;
  let dragHeight: number | null = null;
  let dragging = false;
  let dragMoved = false;
  let activePointerId: number | null = null;
  let viewportWidth = MOBILE_BREAKPOINT_PX + 1;
  let compactContent = false;

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

  $: compactContent =
    viewportWidth <= MOBILE_BREAKPOINT_PX && sheetStage === "compact";

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
      sheetStage = $systemState === "komposition" ? "full" : "compact";
      dragHeight = null;
      dragging = false;
      dragMoved = false;
      activePointerId = null;
    }
  }

  function setSheetStage(stage: SheetStage): void {
    sheetStage = stage;
    dragHeight = null;
    dragging = false;
    dragMoved = false;
    activePointerId = null;
  }

  function toggleSheetStage(): void {
    if (viewportWidth > MOBILE_BREAKPOINT_PX) return;
    setSheetStage(sheetStage === "compact" ? "full" : "compact");
  }

  function nearestSheetStage(height: number): SheetStage {
    const viewport = window.innerHeight;
    const compact = Math.min(270, Math.max(190, viewport * 0.29));
    return Math.abs(height - compact) <= Math.abs(height - viewport * 0.88)
      ? "compact"
      : "full";
  }

  function handleSheetPointerDown(event: PointerEvent): void {
    if (
      viewportWidth > MOBILE_BREAKPOINT_PX ||
      !event.isPrimary ||
      event.button !== 0 ||
      dragging
    )
      return;
    const handle = event.currentTarget as HTMLElement;
    const aside = handle.closest<HTMLElement>('[data-testid="context-panel"]');
    if (!aside) return;
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    activePointerId = event.pointerId;
    dragStartY = event.clientY;
    dragStartHeight = aside.getBoundingClientRect().height;
    dragHeight = dragStartHeight;
    dragging = true;
    dragMoved = false;
  }

  function handleSheetPointerMove(event: PointerEvent): void {
    if (!dragging || event.pointerId !== activePointerId) return;
    const delta = dragStartY - event.clientY;
    if (Math.abs(delta) >= DRAG_THRESHOLD_PX) dragMoved = true;
    if (!dragMoved) return;

    event.preventDefault();
    const minHeight = 190;
    const maxHeight = window.innerHeight * 0.88;
    dragHeight = Math.min(
      maxHeight,
      Math.max(minHeight, dragStartHeight + delta),
    );
  }

  function finishSheetPointer(event: PointerEvent, cancelled: boolean): void {
    if (!dragging || event.pointerId !== activePointerId) return;
    const moved = dragMoved;
    const finalHeight = dragHeight ?? dragStartHeight;
    const handle = event.currentTarget as HTMLElement;

    dragHeight = null;
    dragging = false;
    dragMoved = false;
    activePointerId = null;
    if (handle.hasPointerCapture(event.pointerId)) {
      handle.releasePointerCapture(event.pointerId);
    }

    if (cancelled) return;

    if (moved) setSheetStage(nearestSheetStage(finalHeight));
    else toggleSheetStage();
  }

  function handleSheetPointerUp(event: PointerEvent): void {
    finishSheetPointer(event, false);
  }

  function handleSheetPointerCancel(event: PointerEvent): void {
    finishSheetPointer(event, true);
  }

  function handleSheetLostPointerCapture(event: PointerEvent): void {
    if (!dragging || event.pointerId !== activePointerId) return;
    dragHeight = null;
    dragging = false;
    dragMoved = false;
    activePointerId = null;
  }

  function handleSheetHandleClick(event: MouseEvent): void {
    if (event.detail === 0) toggleSheetStage();
  }

  function handleSheetKeydown(event: KeyboardEvent): void {
    if (viewportWidth > MOBILE_BREAKPOINT_PX) return;
    if (event.key === "ArrowUp" || event.key === "End") {
      event.preventDefault();
      setSheetStage("full");
    } else if (event.key === "ArrowDown" || event.key === "Home") {
      event.preventDefault();
      setSheetStage("compact");
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

<svelte:window bind:innerWidth={viewportWidth} on:keydown={handleKeydown} />

{#if $contextPanelOpen}
  <aside
    class="context-panel"
    class:stage-compact={sheetStage === "compact"}
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
      aria-controls="context-panel-content"
      aria-expanded={sheetStage === "full"}
      aria-label={sheetStage === "compact"
        ? "Panel vollständig öffnen oder ziehen"
        : "Panel kompakt anzeigen oder ziehen"}
      on:pointerdown={handleSheetPointerDown}
      on:pointermove={handleSheetPointerMove}
      on:pointerup={handleSheetPointerUp}
      on:pointercancel={handleSheetPointerCancel}
      on:lostpointercapture={handleSheetLostPointerCapture}
      on:click={handleSheetHandleClick}
      on:keydown={handleSheetKeydown}
    >
      <span aria-hidden="true"></span>
    </button>
    <header
      class="panel-header"
      class:composition={$systemState === "komposition"}
    >
      <div class="heading-group">
        <h2 class="desktop-panel-title">{panelTitle}</h2>
        <button
          type="button"
          class="mobile-panel-title"
          aria-controls="context-panel-content"
          aria-expanded={sheetStage === "full"}
          aria-label={`${panelTitle}: ${
            sheetStage === "compact" ? "vollständig öffnen" : "kompakt anzeigen"
          }`}
          on:click={toggleSheetStage}
        >
          <span>{panelTitle}</span>
        </button>
      </div>
      <button class="close-btn" on:click={closePanel} aria-label="Schließen"
        >✕</button
      >
    </header>

    <div class="panel-content" id="context-panel-content">
      {#if $systemState === "komposition"}
        <KompositionPanel bind:this={kompositionPanel} />
      {:else if $selection}
        {#if $selection.type === "node"}
          <NodePanel
            compact={compactContent}
            on:selectRelated={handleRelated}
            on:domainChanged={handleDomainChanged}
          />
        {:else if $selection.type === "account" || $selection.type === "garnrolle"}
          <AccountPanel
            compact={compactContent}
            on:selectRelated={handleRelated}
          />
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

  .sheet-handle,
  .mobile-panel-title {
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

  .desktop-panel-title,
  .mobile-panel-title {
    margin: 0;
    color: var(--muted);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
  }

  .panel-header.composition .desktop-panel-title,
  .panel-header.composition .mobile-panel-title {
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
    .context-panel {
      bottom: 0;
      left: 0;
      right: 0;
      max-height: none;
      padding-bottom: env(safe-area-inset-bottom);
      border-radius: 18px 18px 0 0;
      transition: height var(--motion-ui);
    }

    .context-panel.stage-compact {
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
    .mobile-panel-title:focus-visible {
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

    .desktop-panel-title {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }

    .mobile-panel-title {
      display: flex;
      align-items: center;
      width: 100%;
      min-height: 44px;
      padding: 0;
      border: 0;
      background: transparent;
      color: inherit;
      font: inherit;
      font-weight: inherit;
      letter-spacing: inherit;
      text-align: left;
      text-transform: inherit;
      cursor: pointer;
    }

    .stage-compact .panel-content {
      padding-top: 0.65rem;
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
