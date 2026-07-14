<script lang="ts">
  import { createEventDispatcher, onDestroy } from "svelte";
  import { selection } from "$lib/stores/uiView";
  import { authStore } from "$lib/auth/store";
  import {
    ApiRequestError,
    deleteEdge,
    updateEdgeKind,
  } from "$lib/api/domainWrites";
  import {
    buildPanelEndpoint,
    createPanelDetailsLoader,
  } from "$lib/panels/panelDetails";
  import { formatDate } from "$lib/utils/formatDate";

  type DomainChanged = {
    kind: "edge";
    id: string;
    action: "updated" | "deleted";
  };

  const dispatch = createEventDispatcher<{ domainChanged: DomainChanged }>();

  interface EdgeParticipantDetails {
    id: string;
    title: string;
    type?: string;
  }

  interface EdgeDetails {
    id: string;
    edge_kind: string;
    created_at?: string;
    source_details?: EdgeParticipantDetails | null;
    target_details?: EdgeParticipantDetails | null;
  }

  let editing = false;
  let saving = false;
  let deleting = false;
  let mutationError = "";
  let selectedKind = "reference";

  const detailsLoader = createPanelDetailsLoader<EdgeDetails>(selection, {
    buildEndpoint: (id) => buildPanelEndpoint("edge", id),
    onSelectionChange: () => {
      editing = false;
      saving = false;
      deleting = false;
      mutationError = "";
    },
    resourceLabel: "edge details",
  });
  const edgeDetailsStore = detailsLoader.details;
  const isLoadingDetailsStore = detailsLoader.isLoading;
  onDestroy(detailsLoader.destroy);

  $: edgeDetails = $edgeDetailsStore;
  $: isLoadingDetails = $isLoadingDetailsStore;
  $: canMutate = $authStore.authenticated && $authStore.role !== "gast";
  $: currentKind =
    edgeDetails?.edge_kind || $selection?.data?.edge_kind || "reference";

  function labelForKind(kind: string): string {
    switch (kind) {
      case "delegation":
        return "Übertragen";
      case "membership":
        return "Zugehörigkeit";
      case "ownership":
        return "Verantwortung";
      case "reference":
        return "Verweis";
      default:
        return kind;
    }
  }

  function beginEdit() {
    selectedKind = currentKind;
    mutationError = "";
    editing = true;
  }

  function mutationMessage(error: unknown): string {
    if (error instanceof ApiRequestError) {
      if (error.status === 401 || error.status === 403) {
        return "Diese Garnrolle darf derzeit nicht schreiben.";
      }
      if (error.status === 404) return "Der Faden existiert nicht mehr.";
      if (error.status === 409) {
        return "Das Gewebe ist vorübergehend nur lesbar. Bitte später erneut versuchen.";
      }
    }
    return "Die Änderung konnte nicht gespeichert werden.";
  }

  async function saveEdge() {
    const id = edgeDetails?.id || $selection?.id;
    if (!id) return;
    saving = true;
    mutationError = "";
    try {
      await updateEdgeKind(id, selectedKind);
      dispatch("domainChanged", { kind: "edge", id, action: "updated" });
    } catch (error) {
      mutationError = mutationMessage(error);
    } finally {
      saving = false;
    }
  }

  async function removeEdge() {
    const id = edgeDetails?.id || $selection?.id;
    if (!id) return;
    if (!window.confirm("Faden wirklich aus dem Gewebe löschen?")) return;
    deleting = true;
    mutationError = "";
    try {
      await deleteEdge(id);
      dispatch("domainChanged", { kind: "edge", id, action: "deleted" });
    } catch (error) {
      mutationError = mutationMessage(error);
    } finally {
      deleting = false;
    }
  }
</script>

<div class="edge-mode">
  <h3>{labelForKind(currentKind)}</h3>

  {#if editing}
    <form class="edit-form" on:submit|preventDefault={saveEdge}>
      <label>
        Bedeutung des Fadens
        <select bind:value={selectedKind}>
          <option value="reference">Verweis</option>
          <option value="membership">Zugehörigkeit</option>
          <option value="ownership">Verantwortung</option>
          <option value="delegation">Übertragen</option>
        </select>
      </label>
      {#if mutationError}<p class="error" role="alert">{mutationError}</p>{/if}
      <div class="form-actions">
        <button
          type="button"
          class="secondary"
          on:click={() => (editing = false)}
          disabled={saving}>Abbrechen</button
        >
        <button type="submit" class="primary" disabled={saving}
          >{saving ? "Speichert…" : "Änderungen speichern"}</button
        >
      </div>
    </form>
  {:else}
    <div class="details">
      {#if isLoadingDetails}
        <p class="ghost">Lade Details…</p>
      {:else}
        <p><strong>Bedeutung:</strong> {labelForKind(currentKind)}</p>
        <p>
          <strong>Geknüpft am:</strong>
          {formatDate(edgeDetails?.created_at || $selection?.data?.created_at)}
        </p>

        <div class="participants">
          <p><strong>Ursprung:</strong></p>
          {#if edgeDetails?.source_details}
            <ul>
              <li>
                <span class="participant-name"
                  >{edgeDetails.source_details.title}</span
                >
                {#if edgeDetails.source_details.type}
                  <span class="participant-role"
                    >({edgeDetails.source_details.type})</span
                  >
                {/if}
              </li>
            </ul>
          {:else}
            <p class="ghost">
              {$selection?.data?.source_id || "Unbekannt"}
              {#if $selection?.data?.source_type}
                <span class="participant-role"
                  >({$selection?.data?.source_type})</span
                >
              {/if}
            </p>
          {/if}

          <p class="target-title"><strong>Ziel:</strong></p>
          {#if edgeDetails?.target_details}
            <ul>
              <li>
                <span class="participant-name"
                  >{edgeDetails.target_details.title}</span
                >
                {#if edgeDetails.target_details.type}
                  <span class="participant-role"
                    >({edgeDetails.target_details.type})</span
                  >
                {/if}
              </li>
            </ul>
          {:else}
            <p class="ghost">
              {$selection?.data?.target_id || "Unbekannt"}
              {#if $selection?.data?.target_type}
                <span class="participant-role"
                  >({$selection?.data?.target_type})</span
                >
              {/if}
            </p>
          {/if}
        </div>
      {/if}
    </div>

    {#if canMutate}
      <div class="mutation-actions" aria-label="Faden bearbeiten">
        {#if mutationError}<p class="error" role="alert">
            {mutationError}
          </p>{/if}
        <button type="button" class="secondary" on:click={beginEdit}
          >Bearbeiten</button
        >
        <button
          type="button"
          class="danger"
          on:click={removeEdge}
          disabled={deleting}>{deleting ? "Löscht…" : "Faden löschen"}</button
        >
        <p class="collective-note">
          Fäden gehören zum gemeinsamen Gewebe und können von allen Webern
          gepflegt werden.
        </p>
      </div>
    {/if}
  {/if}
</div>

<style>
  h3 {
    margin: 0;
    font-size: 1.5rem;
    line-height: 1.2;
  }
  .details {
    padding-top: 0.5rem;
  }
  .details p {
    margin-bottom: 0.5rem;
    font-size: 0.95rem;
  }
  .participants,
  .mutation-actions {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--panel-border, rgba(0, 0, 0, 0.1));
  }
  .participants ul {
    list-style: none;
    padding: 0;
    margin: 0.25rem 0 1rem;
  }
  .participants li {
    display: flex;
    gap: 0.5rem;
    align-items: baseline;
  }
  .participant-name {
    font-weight: 500;
    color: var(--text, #333);
  }
  .participant-role {
    font-size: 0.85em;
    color: var(--ghost, #666);
  }
  .target-title {
    margin-top: 1rem;
  }
  .ghost,
  .collective-note {
    color: var(--muted, #9aa4b2);
    font-size: 0.9rem;
  }
  .collective-note {
    margin: 0;
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
  .edit-form select {
    width: 100%;
    box-sizing: border-box;
    padding: 0.7rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 8px;
    background: var(--panel-solid);
    color: var(--text);
    font: inherit;
  }
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
  @media (max-width: 420px) {
    .form-actions {
      grid-template-columns: 1fr;
    }
  }
</style>
