<script lang="ts">
  import { createEventDispatcher, onDestroy, tick } from "svelte";
  import { selection } from "$lib/stores/uiView";
  import { authStore } from "$lib/auth/store";
  import {
    ApiRequestError,
    deleteNode,
    replaceNode,
  } from "$lib/api/domainWrites";
  import {
    buildPanelEndpoint,
    createPanelDetailsLoader,
  } from "$lib/panels/panelDetails";
  import { formatDate } from "$lib/utils/formatDate";
  import { nodeKindLabel } from "$lib/ui/productLanguage";
  import NodeConversation from "./NodeConversation.svelte";

  type DomainChanged = {
    kind: "node";
    id: string;
    action: "updated" | "deleted";
  };

  const dispatch = createEventDispatcher<{
    selectRelated: { type: "garnrolle"; id: string };
    domainChanged: DomainChanged;
  }>();

  type NodeTab = "uebersicht" | "gespraech" | "verlauf" | "bearbeiten";
  let activeTab: NodeTab = "uebersicht";
  let tabs: NodeTab[] = ["uebersicht", "gespraech", "verlauf"];
  let overviewTab: HTMLButtonElement | null = null;
  let editTab: HTMLButtonElement | null = null;
  let titleInput: HTMLInputElement | null = null;
  let editing = false;
  let saving = false;
  let deleting = false;
  let mutationError = "";
  let formTitle = "";
  let formKind = "";
  let formSummary = "";
  let formInfo = "";
  let formAddress = "";
  let formLat = "";
  let formLon = "";
  let formTags = "";
  let conflictNode: NodeDetails | null = null;

  interface NodeDetails {
    id: string;
    title: string;
    summary?: string | null;
    info?: string | null;
    tags?: string[];
    address?: string | null;
    location?: { lat: number; lon: number };
    created_at?: string;
    updated_at?: string;
    created_by_account_id?: string | null;
    kind?: string;
    participants?: {
      account_title?: string;
      account_id: string;
      edge_kind?: string;
    }[];
    history?: { date: string; event: string }[];
  }

  function resetMutationState() {
    activeTab = "uebersicht";
    editing = false;
    saving = false;
    deleting = false;
    mutationError = "";
  }

  const detailsLoader = createPanelDetailsLoader<NodeDetails>(selection, {
    buildEndpoint: (id) => buildPanelEndpoint("node", id),
    onSelectionChange: resetMutationState,
    resourceLabel: "node details",
  });
  const nodeDetailsStore = detailsLoader.details;
  const isLoadingDetailsStore = detailsLoader.isLoading;
  onDestroy(detailsLoader.destroy);

  $: nodeDetails = $nodeDetailsStore;
  $: isLoadingDetails = $isLoadingDetailsStore;
  $: summary = nodeDetails?.summary || $selection?.data?.summary;
  $: kind = nodeKindLabel(nodeDetails?.kind || $selection?.data?.kind);
  $: nodeCreator =
    nodeDetails?.created_by_account_id ||
    ($selection?.data?.created_by_account_id as string | undefined);
  $: canMutate =
    $authStore.authenticated &&
    ($authStore.role === "weber" ||
      $authStore.role === "admin" ||
      (!!nodeCreator && nodeCreator === $authStore.account_id));

  $: tabs = canMutate
    ? ["uebersicht", "gespraech", "verlauf", "bearbeiten"]
    : ["uebersicht", "gespraech", "verlauf"];
  $: if (!canMutate) {
    const shouldRestoreFocus = activeTab === "bearbeiten" || editing;
    if (activeTab === "bearbeiten") activeTab = "uebersicht";
    if (editing) editing = false;
    if (shouldRestoreFocus) void focusAfterRender(() => overviewTab);
  }

  async function focusAfterRender(
    resolveTarget: () => HTMLElement | null,
  ): Promise<void> {
    await tick();
    resolveTarget()?.focus();
  }

  function setTab(tab: NodeTab) {
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
      ?.querySelectorAll<HTMLButtonElement>('button[role="tab"]');
    buttons?.item(nextIndex)?.focus();
  }

  function beginEdit() {
    const fallback = $selection?.data;
    const location =
      nodeDetails?.location ??
      (typeof fallback?.lat === "number" && typeof fallback?.lon === "number"
        ? { lat: fallback.lat, lon: fallback.lon }
        : undefined);
    formTitle = nodeDetails?.title || fallback?.title || "";
    formKind = nodeDetails?.kind || fallback?.kind || "";
    formSummary = nodeDetails?.summary || fallback?.summary || "";
    formInfo = nodeDetails?.info || fallback?.info || "";
    formAddress = nodeDetails?.address || "";
    formLat = location ? String(location.lat) : "";
    formLon = location ? String(location.lon) : "";
    formTags = (nodeDetails?.tags || fallback?.tags || []).join(", ");
    mutationError = "";
    conflictNode = null;
    editing = true;
    void focusAfterRender(() => titleInput);
  }

  function cancelEdit() {
    editing = false;
    void focusAfterRender(() => editTab);
  }

  function mutationMessage(error: unknown): string {
    if (error instanceof ApiRequestError) {
      if (error.status === 401 || error.status === 403) {
        return "Diese Garnrolle darf derzeit nicht schreiben.";
      }
      if (error.status === 404) return "Der Knoten existiert nicht mehr.";
      if (error.status === 400) {
        return "Die Eingaben sind ungültig. Bitte prüfe alle Felder.";
      }
      if (error.status === 409) {
        return "Der Knoten konnte wegen eines Datenkonflikts nicht geändert werden. Es wurde nichts verändert.";
      }
      if (error.status === 428) {
        return "Die geladene Knotenversion ist unvollständig. Bitte öffne den Knoten erneut und versuche es noch einmal.";
      }
    }
    return "Die Änderung konnte nicht gespeichert werden.";
  }

  async function saveNode() {
    const id = nodeDetails?.id || $selection?.id;
    const lat = Number(formLat);
    const lon = Number(formLon);
    if (!id) return;
    if (!formTitle.trim() || !formKind.trim() || !formAddress.trim()) {
      mutationError = "Titel, Knotenart und Adresse werden benötigt.";
      return;
    }
    if (
      !Number.isFinite(lat) ||
      !Number.isFinite(lon) ||
      lat < -90 ||
      lat > 90 ||
      lon < -180 ||
      lon > 180
    ) {
      mutationError = "Die Koordinaten sind ungültig.";
      return;
    }

    saving = true;
    mutationError = "";
    try {
      const updatedNode = await replaceNode(
        id,
        {
          title: formTitle.trim(),
          kind: formKind.trim(),
          address: formAddress.trim(),
          location: { lat, lon },
          summary: formSummary.trim() || undefined,
          info: formInfo.trim() || undefined,
          tags: Array.from(
            new Set(
              formTags
                .split(",")
                .map((tag) => tag.trim())
                .filter(Boolean),
            ),
          ),
        },
        nodeDetails?.updated_at,
      );
      detailsLoader.setDetails({
        ...(nodeDetails ?? {}),
        ...updatedNode,
      } as NodeDetails);
      conflictNode = null;
      editing = false;
      activeTab = "uebersicht";
      void focusAfterRender(() => overviewTab);
      dispatch("domainChanged", { kind: "node", id, action: "updated" });
    } catch (error) {
      if (
        error instanceof ApiRequestError &&
        error.status === 412 &&
        error.body
      ) {
        const currentNode = error.body as NodeDetails;
        mutationError =
          "Der Knoten wurde in der Zwischenzeit geändert. Dein Entwurf bleibt erhalten. Vergleiche ihn mit dem aktuellen Stand und speichere anschließend erneut.";
        conflictNode = currentNode;
        detailsLoader.setDetails({
          ...(nodeDetails ?? {}),
          ...currentNode,
        } as NodeDetails);
      } else {
        mutationError = mutationMessage(error);
      }
    } finally {
      saving = false;
    }
  }

  async function removeNode() {
    const id = nodeDetails?.id || $selection?.id;
    if (!id) return;
    const confirmed = window.confirm(
      "Knoten wirklich löschen? Alle Fäden, die mit ihm verbunden sind, werden ebenfalls gelöscht.",
    );
    if (!confirmed) return;

    deleting = true;
    mutationError = "";
    try {
      await deleteNode(id, nodeDetails?.updated_at);
      dispatch("domainChanged", { kind: "node", id, action: "deleted" });
    } catch (error) {
      if (
        error instanceof ApiRequestError &&
        error.status === 412 &&
        error.body
      ) {
        mutationError =
          "Der Knoten wurde in der Zwischenzeit geändert und konnte nicht gelöscht werden. Die Ansicht zeigt nun den aktuellen Stand.";
        detailsLoader.setDetails({
          ...(nodeDetails ?? {}),
          ...(error.body as object),
        } as NodeDetails);
      } else {
        mutationError = mutationMessage(error);
      }
    } finally {
      deleting = false;
    }
  }
</script>

<div class="node-mode">
  <h3>{nodeDetails?.title || $selection?.data?.title || $selection?.id}</h3>
  {#if summary && !editing}<p class="summary">{summary}</p>{/if}

  {#if editing}
    <form class="edit-form" on:submit|preventDefault={saveNode}>
      <label>
        Titel
        <input
          bind:this={titleInput}
          bind:value={formTitle}
          maxlength="200"
          required
        />
      </label>
      <label>
        Knotenart
        <input bind:value={formKind} maxlength="100" required />
      </label>
      <label>
        Kurzbeschreibung
        <textarea bind:value={formSummary} maxlength="500" rows="3"></textarea>
      </label>
      <label>
        Ausführliche Information
        <textarea bind:value={formInfo} maxlength="20000" rows="6"></textarea>
      </label>
      <label>
        Adresse
        <input bind:value={formAddress} maxlength="500" required />
      </label>
      <div class="coordinate-grid">
        <label>
          Breitengrad
          <input bind:value={formLat} inputmode="decimal" required />
        </label>
        <label>
          Längengrad
          <input bind:value={formLon} inputmode="decimal" required />
        </label>
      </div>
      <label>
        Schlagwörter, durch Kommas getrennt
        <input bind:value={formTags} />
      </label>

      {#if mutationError}<p class="error" role="alert">{mutationError}</p>{/if}
      {#if conflictNode}
        <section class="conflict-current" aria-label="Aktueller Serverstand">
          <strong>Aktueller Stand im Weltgewebe</strong>
          <dl>
            <div>
              <dt>Titel</dt>
              <dd>{conflictNode.title}</dd>
            </div>
            <div>
              <dt>Knotenart</dt>
              <dd>{conflictNode.kind}</dd>
            </div>
            {#if conflictNode.summary}<div>
                <dt>Kurzbeschreibung</dt>
                <dd>{conflictNode.summary}</dd>
              </div>{/if}
            {#if conflictNode.info}<div>
                <dt>Information</dt>
                <dd>{conflictNode.info}</dd>
              </div>{/if}
            {#if conflictNode.address}<div>
                <dt>Adresse</dt>
                <dd>{conflictNode.address}</dd>
              </div>{/if}
            {#if conflictNode.tags?.length}<div>
                <dt>Schlagwörter</dt>
                <dd>{conflictNode.tags.join(", ")}</dd>
              </div>{/if}
          </dl>
        </section>
      {/if}
      <div class="form-actions">
        <button
          type="button"
          class="secondary"
          on:click={cancelEdit}
          disabled={saving}>Abbrechen</button
        >
        <button type="submit" class="primary" disabled={saving}
          >{saving ? "Speichert…" : "Änderungen speichern"}</button
        >
      </div>
    </form>
  {:else}
    <div class="tabs" role="tablist" aria-label="Knoten-Tabs">
      <button
        class:active={activeTab === "uebersicht"}
        on:click={() => setTab("uebersicht")}
        on:keydown={handleKeydown}
        role="tab"
        aria-selected={activeTab === "uebersicht"}
        aria-controls="panel-uebersicht"
        id="tab-uebersicht"
        bind:this={overviewTab}
        tabindex={activeTab === "uebersicht" ? 0 : -1}>Übersicht</button
      >
      <button
        class:active={activeTab === "gespraech"}
        on:click={() => setTab("gespraech")}
        on:keydown={handleKeydown}
        role="tab"
        aria-selected={activeTab === "gespraech"}
        aria-controls="panel-gespraech"
        id="tab-gespraech"
        tabindex={activeTab === "gespraech" ? 0 : -1}>Gespräch</button
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
      {#if canMutate}
        <button
          class:active={activeTab === "bearbeiten"}
          on:click={() => setTab("bearbeiten")}
          on:keydown={handleKeydown}
          role="tab"
          aria-selected={activeTab === "bearbeiten"}
          aria-controls="panel-bearbeiten"
          id="tab-bearbeiten"
          bind:this={editTab}
          tabindex={activeTab === "bearbeiten" ? 0 : -1}>Bearbeiten</button
        >
      {/if}
    </div>

    <div class="tab-content">
      {#if activeTab === "uebersicht"}
        <div
          class="overview"
          id="panel-uebersicht"
          role="tabpanel"
          aria-labelledby="tab-uebersicht"
          tabindex="0"
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
            {#if nodeDetails?.address}<p>
                <strong>Adresse:</strong>
                {nodeDetails.address}
              </p>{/if}
            {#if nodeDetails?.info}<p class="long-info">
                <strong>Information:</strong>
                {nodeDetails.info}
              </p>{/if}
            {#if nodeDetails?.tags?.length}<p>
                <strong>Schlagwörter:</strong>
                {nodeDetails.tags.join(", ")}
              </p>{/if}
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
      {:else if activeTab === "gespraech"}
        <div
          id="panel-gespraech"
          role="tabpanel"
          aria-labelledby="tab-gespraech"
        >
          {#key nodeDetails?.id || $selection?.id || ""}
            <NodeConversation
              nodeId={nodeDetails?.id || $selection?.id || ""}
            />
          {/key}
        </div>
      {:else if activeTab === "verlauf"}
        <div
          id="panel-verlauf"
          role="tabpanel"
          aria-labelledby="tab-verlauf"
          tabindex="0"
        >
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
      {:else if activeTab === "bearbeiten" && canMutate}
        <div
          class="mutation-actions"
          id="panel-bearbeiten"
          role="tabpanel"
          aria-labelledby="tab-bearbeiten"
        >
          {#if mutationError}<p class="error" role="alert">
              {mutationError}
            </p>{/if}
          <button type="button" class="secondary" on:click={beginEdit}
            >Bearbeiten</button
          >
          <button
            type="button"
            class="danger"
            on:click={removeNode}
            disabled={deleting}
            >{deleting ? "Löscht…" : "Knoten löschen"}</button
          >
          <p class="collective-note">
            Eigene Knoten kannst du selbst pflegen. Weber können zusätzlich
            gemeinschaftliche Knoten weiterentwickeln.
          </p>
        </div>
      {/if}
    </div>
  {/if}
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
  .ghost,
  .collective-note {
    color: var(--muted);
    font-size: 0.9rem;
  }
  .overview > p {
    margin: 0 0 0.65rem;
    font-size: 0.95rem;
  }
  .long-info {
    white-space: pre-wrap;
  }
  .participants {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--panel-border);
  }
  .mutation-actions {
    padding-top: 0.25rem;
  }
  .participants p,
  .collective-note {
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
  .edit-form,
  .mutation-actions {
    display: grid;
    gap: 0.85rem;
  }
  .edit-form {
    margin-top: 1rem;
  }
  .edit-form label {
    display: grid;
    gap: 0.35rem;
    font-size: 0.9rem;
    font-weight: 650;
  }
  .edit-form input,
  .edit-form textarea {
    width: 100%;
    box-sizing: border-box;
    padding: 0.7rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 8px;
    background: var(--panel-solid);
    color: var(--text);
    font: inherit;
  }
  .coordinate-grid,
  .form-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }
  .form-actions button,
  .mutation-actions > button {
    min-height: 44px;
    border-radius: 8px;
    padding: 0.65rem 0.85rem;
    font: inherit;
    font-weight: 700;
    cursor: pointer;
  }
  .primary {
    border: 1px solid var(--accent);
    background: var(--accent);
    color: var(--panel-solid);
  }
  .secondary {
    border: 1px solid var(--panel-border-strong);
    background: var(--panel-solid);
    color: var(--text);
  }
  .danger {
    border: 1px solid #a33;
    background: transparent;
    color: #a33;
  }
  button:disabled {
    cursor: wait;
    opacity: 0.65;
  }
  .error {
    margin: 0;
    color: #a33;
    font-weight: 650;
  }
  .conflict-current {
    border: 1px solid color-mix(in srgb, #a33 35%, transparent);
    border-radius: 0.5rem;
    padding: 0.75rem;
  }
  .conflict-current dl {
    display: grid;
    gap: 0.4rem;
    margin: 0.55rem 0 0;
  }
  .conflict-current dl div {
    display: grid;
    grid-template-columns: minmax(6rem, auto) 1fr;
    gap: 0.65rem;
  }
  .conflict-current dt {
    font-weight: 600;
  }
  .conflict-current dd {
    margin: 0;
    overflow-wrap: anywhere;
    white-space: pre-wrap;
  }
  @media (max-width: 420px) {
    .coordinate-grid,
    .form-actions {
      grid-template-columns: 1fr;
    }
  }
</style>
