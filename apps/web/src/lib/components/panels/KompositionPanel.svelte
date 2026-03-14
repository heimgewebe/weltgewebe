<script lang="ts">
  import { kompositionDraft, leaveToNavigation, systemState } from '$lib/stores/uiView';

  let title = '';
  let description = '';
  let nodeType = 'standard';
  let isSubmitting = false;

  let titleError = false;

  function handleCancel() {
    leaveToNavigation();
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    titleError = false;

    if (!title.trim()) {
      titleError = true;
      return;
    }

    if (!$kompositionDraft?.lngLat) {
      return;
    }

    isSubmitting = true;

    try {
      // Create a local snapshot to guard against stale state transitions
      const submitDraft = $kompositionDraft;

      // Simulate network request
      await new Promise((resolve) => setTimeout(resolve, 500));

      // Guard: only execute success path if we are still in komposition state
      // and the draft hasn't been maliciously replaced
      if ($systemState === 'komposition' && $kompositionDraft === submitDraft) {
        // For now, success path Option A (komposition -> navigation)
        leaveToNavigation();
      }
    } finally {
      isSubmitting = false;
    }
  }
</script>

<div class="komposition-mode">
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

    <div class="form-group">
      <label for="nodeType">Typ</label>
      <select id="nodeType" bind:value={nodeType} class="input" disabled={isSubmitting}>
        <option value="standard">Standard</option>
        <option value="event">Event</option>
        <option value="resource">Ressource</option>
      </select>
    </div>

    <div class="form-group">
      <label for="title">Titel *</label>
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
        <span id="title-error" class="error-msg">Titel ist erforderlich</span>
      {/if}
    </div>

    <div class="form-group">
      <label for="description">Beschreibung</label>
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
        disabled={isSubmitting || !$kompositionDraft?.lngLat || !title.trim()}
      >
        {isSubmitting ? 'Wird erstellt...' : 'Erstellen'}
      </button>
    </div>
  </form>
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
