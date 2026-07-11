<script lang="ts">
  import { browser } from '$app/environment';
  import { goto, invalidateAll } from '$app/navigation';
  import { kompositionDraft, lastCreatedNodeId, leaveToNavigation, systemState } from '$lib/stores/uiView';
  import { authStore } from '$lib/auth/store';
  import { createEdge, createNode, ApiRequestError } from '$lib/api/domainWrites';

  let title = '';
  let description = '';
  let address = '';
  let nodeType = 'standard';
  let isSubmitting = false;

  let titleError = false;
  let addressError = false;
  let formError: string | null = null;

  // Set once the node itself is durably created. While set (and edgeError is
  // set alongside it), the panel shows the partial-success/retry state
  // instead of the create form — the node exists, the account->node Faden
  // does not yet, and the UI must say so rather than imply one atomic step.
  let createdNodeId: string | null = null;
  let edgeError: string | null = null;

  $: canWrite = $authStore.role === 'weber' || $authStore.role === 'admin';
  $: placingGarnrolle = $kompositionDraft?.mode === 'place-garnrolle';
  $: canSubmit = !!$kompositionDraft?.lngLat && !!title.trim() && !!address.trim();

  async function returnToGarnrolleSettings(withLocation: boolean) {
    const location = withLocation ? $kompositionDraft?.lngLat : undefined;
    const accountId = $authStore.account_id;
    if (browser && location && accountId) {
      sessionStorage.setItem(
        `weltgewebe:garnrolle-return-location:${accountId}`,
        JSON.stringify({ lat: location[1], lon: location[0] })
      );
    }
    leaveToNavigation();
    await goto('/settings#meine-garnrolle');
  }

  function handleCancel() {
    if (placingGarnrolle) {
      void returnToGarnrolleSettings(false);
      return;
    }
    if (createdNodeId) {
      // The node already exists — closing the panel must not hide that.
      void finalizeSuccess(createdNodeId);
      return;
    }
    leaveToNavigation();
  }

  function describeCreateNodeError(err: unknown): string {
    if (err instanceof ApiRequestError) {
      if (err.status === 401 || err.status === 403) {
        return 'Du hast keine Berechtigung, einen Knoten anzulegen.';
      }
      if (err.status === 400) {
        return 'Bitte prüfe deine Eingaben: Name, Art, Adresse und Ort müssen ausgefüllt sein.';
      }
      if (err.status === 409) {
        return 'Dieser Knoten existiert bereits.';
      }
    }
    return 'Der Knoten konnte nicht gespeichert werden. Bitte versuche es später erneut.';
  }

  async function finalizeSuccess(nodeId: string) {
    await invalidateAll();
    lastCreatedNodeId.set(nodeId);
    leaveToNavigation();
  }

  async function attemptCreateEdge(nodeId: string) {
    edgeError = null;
    const accountId = $authStore.account_id;
    if (!accountId) {
      edgeError =
        'Der Knoten wurde gespeichert, aber die Verknüpfung zu deiner Garnrolle konnte nicht hergestellt werden (keine aktive Sitzung). Du kannst es erneut versuchen.';
      return;
    }
    try {
      await createEdge({
        source_id: accountId,
        source_type: 'account',
        target_id: nodeId,
        target_type: 'node',
        edge_kind: 'reference',
      });
      await finalizeSuccess(nodeId);
    } catch (e) {
      edgeError =
        'Der Knoten wurde gespeichert, aber die Verknüpfung zu deiner Garnrolle konnte nicht hergestellt werden. Du kannst es erneut versuchen oder ohne Verknüpfung fortfahren.';
    }
  }

  async function retryEdge() {
    if (!createdNodeId || isSubmitting) return;
    isSubmitting = true;
    try {
      await attemptCreateEdge(createdNodeId);
    } finally {
      isSubmitting = false;
    }
  }

  async function continueWithoutEdge() {
    if (!createdNodeId || isSubmitting) return;
    isSubmitting = true;
    try {
      await finalizeSuccess(createdNodeId);
    } finally {
      isSubmitting = false;
    }
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    formError = null;
    titleError = !title.trim();
    addressError = !address.trim();

    if (titleError || addressError || !$kompositionDraft?.lngLat || !canWrite) {
      return;
    }

    isSubmitting = true;
    try {
      // Create a local snapshot to guard against stale state transitions
      const submitDraft = $kompositionDraft;
      const [lon, lat] = submitDraft.lngLat!;

      const node = await createNode({
        title: title.trim(),
        kind: nodeType,
        address: address.trim(),
        location: { lat, lon },
        summary: description.trim() || undefined,
      });

      // Guard: only proceed if we are still in komposition state and the
      // draft hasn't been replaced in the meantime.
      if ($systemState === 'komposition' && $kompositionDraft === submitDraft) {
        createdNodeId = node.id;
        await attemptCreateEdge(node.id);
      }
    } catch (err) {
      formError = describeCreateNodeError(err);
    } finally {
      isSubmitting = false;
    }
  }
</script>

<div class="komposition-mode">
  {#if !canWrite}
    <div class="state-pending">
      <p><strong>Kein Zugriff</strong></p>
      <p>Nur Weber und Admins können neue Knoten anlegen.</p>
    </div>
    <div class="actions">
      <button type="button" class="btn btn-secondary" on:click={handleCancel}>Schließen</button>
    </div>
  {:else if placingGarnrolle}
    <div data-testid="garnrolle-placement">
      {#if $kompositionDraft?.lngLat}
        <div class="state-set">
          <p><strong>Kartenpunkt gewählt</strong></p>
          <p>
            {$kompositionDraft.lngLat[1].toFixed(5)},
            {$kompositionDraft.lngLat[0].toFixed(5)}
          </p>
          <p class="ghost">
            Prüfe, ob dieser Punkt zu deiner Adresse passt. Erst in den
            Einstellungen wird die Garnrolle gespeichert.
          </p>
        </div>
      {:else}
        <div class="state-pending">
          <p><strong>Kartenpunkt ausstehend</strong></p>
          <p>
            Drücke etwa eine Sekunde auf den gewünschten Ort der Karte. Du
            kannst den Punkt danach bestätigen oder erneut setzen.
          </p>
        </div>
      {/if}
      <div class="actions">
        <button
          type="button"
          class="btn btn-secondary"
          on:click={() => returnToGarnrolleSettings(false)}
        >
          Abbrechen
        </button>
        <button
          type="button"
          class="btn btn-primary"
          disabled={!$kompositionDraft?.lngLat}
          on:click={() => returnToGarnrolleSettings(true)}
          data-testid="confirm-garnrolle-location"
        >
          Diesen Punkt übernehmen
        </button>
      </div>
    </div>
  {:else if createdNodeId && edgeError}
    <div class="state-set">
      <p><strong>Knoten gespeichert</strong></p>
      <p>{edgeError}</p>
    </div>
    <div class="actions">
      <button type="button" class="btn btn-secondary" on:click={continueWithoutEdge} disabled={isSubmitting}>
        Ohne Verknüpfung fortfahren
      </button>
      <button type="button" class="btn btn-primary" on:click={retryEdge} disabled={isSubmitting}>
        {isSubmitting ? 'Versuche erneut…' : 'Erneut verknüpfen'}
      </button>
    </div>
  {:else}
    <form on:submit={handleSubmit} class="komposition-form">
      {#if $kompositionDraft?.lngLat}
        <div class="state-set">
          <p><strong>Ort gesetzt:</strong> {$kompositionDraft.lngLat[1].toFixed(5)}, {$kompositionDraft.lngLat[0].toFixed(5)}</p>
          <p class="ghost">Du kannst den Ort ändern, indem du einen anderen Punkt auf der Karte lange drückst.</p>
        </div>
      {:else}
        <div class="state-pending">
          <p><strong>Ort ausstehend</strong></p>
          <p>Bitte wähle den Startpunkt für den neuen Knoten, indem du lange auf die Karte tippst (Longpress).</p>
        </div>
      {/if}

      {#if formError}
        <div class="form-error" role="alert">{formError}</div>
      {/if}

      <div class="form-group">
        <label for="nodeType">Art</label>
        <select id="nodeType" bind:value={nodeType} class="input" disabled={isSubmitting}>
          <option value="standard">Standard</option>
          <option value="event">Event</option>
          <option value="resource">Ressource</option>
        </select>
      </div>

      <div class="form-group">
        <label for="title">Name *</label>
        <input
          type="text"
          id="title"
          bind:value={title}
          class="input"
          class:error={titleError}
          placeholder="Name des Knotens"
          disabled={isSubmitting}
          required
          aria-invalid={titleError}
          aria-describedby={titleError ? 'title-error' : undefined}
        />
        {#if titleError}
          <span id="title-error" class="error-msg">Name ist erforderlich</span>
        {/if}
      </div>

      <div class="form-group">
        <label for="address">Adresse *</label>
        <input
          type="text"
          id="address"
          bind:value={address}
          class="input"
          class:error={addressError}
          placeholder="Straße, Hausnummer, Ort"
          disabled={isSubmitting}
          required
          aria-invalid={addressError}
          aria-describedby={addressError ? 'address-error' : undefined}
        />
        {#if addressError}
          <span id="address-error" class="error-msg">Adresse ist erforderlich</span>
        {/if}
      </div>

      <div class="form-group">
        <label for="description">Kurze Beschreibung</label>
        <textarea
          id="description"
          bind:value={description}
          class="input"
          placeholder="Worum geht es hier?"
          rows="4"
          disabled={isSubmitting}
        ></textarea>
      </div>

      <div class="actions">
        <button type="button" class="btn btn-secondary" on:click={handleCancel} disabled={isSubmitting}>
          Abbrechen
        </button>
        <button
          type="submit"
          class="btn btn-primary"
          disabled={isSubmitting || !canSubmit}
        >
          {isSubmitting ? 'Wird erstellt...' : 'Erstellen'}
        </button>
      </div>
    </form>
  {/if}
</div>

<style>
  .komposition-mode {
    padding: 1rem;
    height: 100%;
    overflow-y: auto;
  }

  .state-set, .state-pending {
    background: var(--panel-border, rgba(255, 255, 255, 0.06));
    padding: 1rem;
    border-radius: var(--radius, 8px);
    margin-bottom: 1.5rem;
  }

  .state-pending {
    border: 2px dashed var(--muted, #9aa4b2);
    background: transparent;
  }

  .ghost {
    color: var(--muted, #9aa4b2);
    font-size: 0.85rem;
    margin-top: 0.5rem;
  }

  .form-error {
    background: rgba(255, 107, 107, 0.12);
    border: 1px solid #ff6b6b;
    border-radius: var(--radius, 8px);
    color: var(--text, #e9eef5);
    padding: 0.75rem 1rem;
    margin-bottom: 1.25rem;
    font-size: 0.9rem;
  }

  .form-group {
    margin-bottom: 1.25rem;
  }

  label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
    color: var(--text, #e9eef5);
  }

  .input {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.06));
    border-radius: var(--radius, 6px);
    font-family: inherit;
    font-size: 1rem;
    background: var(--bg, #0f1115);
    color: var(--text, #e9eef5);
    box-sizing: border-box;
  }

  .input:focus {
    outline: none;
    border-color: var(--accent, #6aa6ff);
    box-shadow: 0 0 0 2px var(--accent-soft, rgba(106, 166, 255, 0.18));
  }

  .input.error {
    border-color: #ff6b6b;
  }

  .error-msg {
    color: #ff6b6b;
    font-size: 0.85rem;
    display: block;
    margin-top: 0.25rem;
  }

  textarea.input {
    resize: vertical;
  }

  .actions {
    display: flex;
    gap: 1rem;
    margin-top: 2rem;
  }

  .btn {
    flex: 1;
    padding: 0.75rem;
    border: none;
    border-radius: var(--radius, 6px);
    font-size: 1rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-primary {
    background: var(--accent, #6aa6ff);
    color: #0f1115; /* dark text on light accent */
  }

  .btn-primary:hover:not(:disabled) {
    background: #5088e0;
  }

  .btn-secondary {
    background: var(--bg, #0f1115);
    color: var(--text, #e9eef5);
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.06));
  }

  .btn-secondary:hover:not(:disabled) {
    background: var(--panel-border, rgba(255, 255, 255, 0.1));
  }
</style>
