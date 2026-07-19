<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { authStore } from "$lib/auth/store";
  import { formatDate } from "$lib/utils/formatDate";
  import {
    createConversationMessage,
    getNodeConversation,
    listConversationMessages,
    NodeConversationApiError,
    tombstoneConversationMessage,
    updateConversationMessage,
    type ConversationMessage,
    type NodeConversation,
  } from "$lib/api/nodeConversation";

  export let nodeId: string;

  const POLL_INTERVAL_MS = 5_000;

  let conversation: NodeConversation | null = null;
  let messages: ConversationMessage[] = [];
  let olderCursor: string | null = null;
  let loading = true;
  let loadingOlder = false;
  let loadedOlder = false;
  let loadError = "";
  let draft = "";
  let draftOperationId = "";
  let posting = false;
  let mutationError = "";
  let editingId = "";
  let editDraft = "";
  let savingId = "";
  let tombstoningId = "";
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let destroyed = false;

  $: canWrite =
    $authStore.authenticated &&
    ($authStore.role === "weber" || $authStore.role === "admin");

  function mergeMessages(incoming: ConversationMessage[]) {
    const merged = new Map(messages.map((message) => [message.id, message]));
    for (const message of incoming) merged.set(message.id, message);
    messages = Array.from(merged.values()).sort(
      (left, right) =>
        left.created_at.localeCompare(right.created_at) ||
        left.id.localeCompare(right.id),
    );
  }

  function messageForError(error: unknown): string {
    if (error instanceof NodeConversationApiError) {
      if (error.status === 401 || error.status === 403) {
        return "Du darfst diesen Beitrag derzeit nicht verändern.";
      }
      if (error.code === "message_version_conflict") {
        return "Der Beitrag wurde inzwischen geändert. Dein Entwurf bleibt erhalten.";
      }
      if (error.code === "message_deleted") {
        return "Der Beitrag wurde bereits entfernt.";
      }
      if (error.code === "invalid_message_content") {
        return "Der Beitrag muss zwischen 1 und 4.000 Zeichen enthalten.";
      }
      if (error.code === "message_rate_limited") {
        return "Zu viele neue Beiträge in kurzer Zeit. Bitte versuche es in einer Minute erneut.";
      }
    }
    return "Das Gespräch konnte nicht gespeichert werden. Dein Entwurf bleibt erhalten.";
  }

  async function refresh() {
    try {
      const currentConversation =
        conversation ?? (await getNodeConversation(nodeId));
      if (destroyed) return;
      conversation = currentConversation;
      const page = await listConversationMessages(currentConversation.id);
      if (destroyed) return;
      mergeMessages(page.items);
      if (!loadedOlder) olderCursor = page.page.next_cursor;
      loadError = "";
    } catch (error) {
      if (!destroyed) {
        loadError = "Das Gespräch kann gerade nicht geladen werden.";
        console.error(error);
      }
    } finally {
      if (!destroyed) loading = false;
    }
  }

  async function loadOlder() {
    if (!conversation || !olderCursor || loadingOlder) return;
    loadingOlder = true;
    try {
      const page = await listConversationMessages(conversation.id, olderCursor);
      mergeMessages(page.items);
      olderCursor = page.page.next_cursor;
      loadedOlder = true;
      loadError = "";
    } catch (error) {
      loadError = "Ältere Beiträge können gerade nicht geladen werden.";
      console.error(error);
    } finally {
      loadingOlder = false;
    }
  }

  async function submitMessage() {
    if (!conversation || !draft.trim() || posting) return;
    posting = true;
    mutationError = "";
    if (!draftOperationId) draftOperationId = crypto.randomUUID();
    try {
      const created = await createConversationMessage(
        conversation.id,
        draft.trim(),
        draftOperationId,
      );
      mergeMessages([created]);
      draft = "";
      draftOperationId = "";
    } catch (error) {
      mutationError = messageForError(error);
    } finally {
      posting = false;
    }
  }

  function beginEdit(message: ConversationMessage) {
    editingId = message.id;
    editDraft = message.content ?? "";
    mutationError = "";
  }

  async function saveEdit(message: ConversationMessage) {
    if (!conversation || !editDraft.trim() || savingId) return;
    savingId = message.id;
    mutationError = "";
    try {
      const updated = await updateConversationMessage(
        conversation.id,
        message.id,
        editDraft.trim(),
        message.updated_at,
      );
      mergeMessages([updated]);
      editingId = "";
      editDraft = "";
    } catch (error) {
      if (error instanceof NodeConversationApiError && error.current) {
        mergeMessages([error.current]);
      }
      mutationError = messageForError(error);
    } finally {
      savingId = "";
    }
  }

  async function tombstone(message: ConversationMessage) {
    if (!conversation || tombstoningId) return;
    if (!window.confirm("Eigenen Beitrag wirklich entfernen?")) return;
    tombstoningId = message.id;
    mutationError = "";
    try {
      const removed = await tombstoneConversationMessage(
        conversation.id,
        message.id,
        message.updated_at,
      );
      mergeMessages([removed]);
      if (editingId === message.id) {
        editingId = "";
        editDraft = "";
      }
    } catch (error) {
      if (error instanceof NodeConversationApiError && error.current) {
        mergeMessages([error.current]);
      }
      mutationError = messageForError(error);
    } finally {
      tombstoningId = "";
    }
  }

  function stopPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  function syncPolling() {
    stopPolling();
    if (document.visibilityState !== "visible") return;
    void refresh();
    pollTimer = setInterval(() => void refresh(), POLL_INTERVAL_MS);
  }

  onMount(() => {
    document.addEventListener("visibilitychange", syncPolling);
    syncPolling();
  });

  onDestroy(() => {
    destroyed = true;
    stopPolling();
    document.removeEventListener("visibilitychange", syncPolling);
  });
</script>

<section class="conversation" aria-labelledby="node-conversation-heading">
  <h4 id="node-conversation-heading">Öffentlicher Gesprächsraum</h4>

  {#if loadError}<p class="error" role="alert">{loadError}</p>{/if}
  {#if loading}<p class="muted">Lade Gespräch…</p>
  {:else if messages.length === 0}<p class="empty">
      Noch keine Beiträge. Hier kann das Gespräch über diesen Knoten beginnen.
    </p>
  {:else}
    {#if olderCursor}<button
        type="button"
        class="older"
        on:click={loadOlder}
        disabled={loadingOlder}
        >{loadingOlder ? "Lädt…" : "Ältere Beiträge laden"}</button
      >{/if}
    <ol class="messages" aria-label="Gesprächsbeiträge">
      {#each messages as message (message.id)}<li
          class:deleted={message.deleted_at !== null}
        >
          <header>
            <strong>{message.author_title}</strong>
            <time datetime={message.created_at}
              >{formatDate(message.created_at)}</time
            >
          </header>
          {#if message.deleted_at}<p class="tombstone">Beitrag entfernt.</p>
          {:else if editingId === message.id}
            <form on:submit|preventDefault={() => saveEdit(message)}>
              <label for={`edit-message-${message.id}`}
                >Beitrag bearbeiten</label
              >
              <textarea
                id={`edit-message-${message.id}`}
                bind:value={editDraft}
                maxlength="4000"
                rows="4"
                required></textarea>
              <div class="actions">
                <button
                  type="button"
                  class="secondary"
                  on:click={() => (editingId = "")}>Abbrechen</button
                >
                <button type="submit" disabled={savingId === message.id}
                  >{savingId === message.id
                    ? "Speichert…"
                    : "Änderung speichern"}</button
                >
              </div>
            </form>
          {:else}<p class="content">{message.content}</p>
            {#if message.author_account_id === $authStore.account_id || $authStore.role === "admin"}<div
                class="message-actions"
                aria-label={`Beitrag von ${message.author_title}`}
              >
                {#if message.author_account_id === $authStore.account_id}<button
                    type="button"
                    class="link"
                    on:click={() => beginEdit(message)}>Bearbeiten</button
                  >{/if}
                <button
                  type="button"
                  class="link danger-link"
                  on:click={() => tombstone(message)}
                  disabled={tombstoningId === message.id}
                  >{tombstoningId === message.id
                    ? "Entfernt…"
                    : "Entfernen"}</button
                >
              </div>{/if}
          {/if}
        </li>{/each}
    </ol>
  {/if}

  {#if canWrite}
    <form class="composer" on:submit|preventDefault={submitMessage}>
      <label for="node-conversation-draft">Neuer Beitrag</label>
      <textarea
        id="node-conversation-draft"
        bind:value={draft}
        maxlength="4000"
        rows="4"
        placeholder="Schreibe einen Beitrag…"
        required></textarea>
      {#if mutationError}<p class="error" role="alert">{mutationError}</p>{/if}
      <button type="submit" disabled={posting || !draft.trim()}
        >{posting ? "Veröffentlicht…" : "Beitrag veröffentlichen"}</button
      >
    </form>
  {:else}<p class="guest-note">
      Als Gast kannst du den Gesprächsraum lesen. Schreiben beginnt mit dem
      Weberstatus.
    </p>{/if}
</section>

<style>
  .conversation {
    display: grid;
    gap: 1rem;
  }
  h4,
  p {
    margin: 0;
  }
  .muted,
  .empty,
  .guest-note,
  time,
  .tombstone {
    color: var(--muted);
  }
  .messages {
    display: grid;
    gap: 0.75rem;
    list-style: none;
    padding: 0;
    margin: 0;
  }
  .messages li {
    padding: 0.8rem;
    border: 1px solid var(--panel-border);
    border-radius: 10px;
    background: var(--panel-solid);
  }
  .messages li.deleted {
    background: transparent;
  }
  header {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.45rem;
    font-size: 0.9rem;
  }
  .content {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  form,
  .composer {
    display: grid;
    gap: 0.55rem;
  }
  textarea {
    width: 100%;
    box-sizing: border-box;
    resize: vertical;
    border: 1px solid var(--panel-border-strong);
    border-radius: 8px;
    padding: 0.65rem;
    background: var(--panel-solid);
    color: var(--text);
    font: inherit;
  }
  button {
    min-height: 44px;
    border: 1px solid var(--accent);
    border-radius: 8px;
    padding: 0.55rem 0.8rem;
    background: var(--accent);
    color: var(--panel-solid);
    font-weight: 700;
    cursor: pointer;
  }
  button:disabled {
    opacity: 0.6;
    cursor: wait;
  }
  .actions,
  .message-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .secondary,
  .older {
    background: transparent;
    color: var(--text);
    border-color: var(--panel-border-strong);
  }
  .link {
    min-height: 32px;
    padding: 0.25rem 0;
    border: 0;
    background: transparent;
    color: var(--accent);
  }
  .danger-link,
  .error {
    color: var(--danger);
  }
  .guest-note {
    padding-top: 0.75rem;
    border-top: 1px solid var(--panel-border);
    font-size: 0.9rem;
  }
</style>
