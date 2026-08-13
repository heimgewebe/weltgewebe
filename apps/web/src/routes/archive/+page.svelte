<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import {
    ArchiveConversationApiError,
    loadArchivedConversation,
    type ArchivedConversationView,
  } from "$lib/api/archiveConversation";

  type ArchiveState =
    | "overview"
    | "loading"
    | "ready"
    | "invalid"
    | "not-found"
    | "forbidden"
    | "malformed"
    | "error";

  const archiveMonths: { label: string; path: string }[] = [];
  // Beispiel-Daten (auskommentiert, da Routen noch nicht existieren)
  // [
  //   { label: "Mai 2024", path: "/archive/2024/05" },
  //   { label: "April 2024", path: "/archive/2024/04" },
  //   { label: "März 2024", path: "/archive/2024/03" }
  // ];
  let archiveState: ArchiveState = $state("overview");
  let archive: ArchivedConversationView | null = $state(null);
  let controller: AbortController | null = null;
  const archiveDate = new Intl.DateTimeFormat("de-DE", {
    timeZone: "UTC",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });

  function classifyError(error: unknown): ArchiveState {
    if (error instanceof ArchiveConversationApiError) {
      if (error.status === 404) return "not-found";
      if (error.status === 401 || error.status === 403) return "forbidden";
      if (error.code === "malformed_response") return "malformed";
    }
    return "error";
  }

  onMount(() => {
    const conversationId = new URLSearchParams(window.location.search).get(
      "id",
    );
    if (conversationId === null) {
      archiveState = "overview";
      return;
    }
    if (!conversationId || conversationId.length > 200) {
      archiveState = "invalid";
      return;
    }

    archiveState = "loading";
    controller = new AbortController();
    void loadArchivedConversation(conversationId, controller.signal)
      .then((loaded) => {
        archive = loaded;
        archiveState = "ready";
      })
      .catch((error: unknown) => {
        if ((error as { name?: string } | null)?.name !== "AbortError") {
          archiveState = classifyError(error);
        }
      });
  });

  onDestroy(() => controller?.abort());
</script>

<svelte:head>
  <title
    >{archive
      ? `${archive.conversation.node_title_snapshot} · Gesprächsarchiv`
      : "Archiv · Weltgewebe"}</title
  >
  <meta
    name="description"
    content="Übersichten und schreibgeschützte öffentliche Gesprächsarchive im Weltgewebe."
  />
</svelte:head>

<main class="archive" aria-busy={archiveState === "loading"}>
  {#if archiveState === "overview"}
    <header>
      <h1>Archiv</h1>
      <p>
        Im Archiv findest du vergangene Monatsübersichten. Wähle einen Monat
        aus, um alle Einträge aus dieser Zeitspanne zu entdecken.
      </p>
    </header>

    <section aria-labelledby="archive-months">
      <h2 id="archive-months">Monate</h2>
      {#if archiveMonths.length > 0}
        <ul class="months">
          {#each archiveMonths as month}
            <li><a href={month.path}>{month.label}</a></li>
          {/each}
        </ul>
      {:else}
        <p class="state">Das Archiv ist derzeit noch leer oder im Aufbau.</p>
      {/if}
    </section>
  {:else if archiveState === "loading"}
    <h1>Gesprächsarchiv</h1>
    <p class="state" role="status">Lade archiviertes Gespräch…</p>
  {:else if archiveState === "invalid"}
    <h1>Archivlink unvollständig</h1>
    <p class="state error" role="alert">
      Dieser Archivlink enthält keine gültige Gesprächskennung.
    </p>
  {:else if archiveState === "not-found"}
    <h1>Archiv nicht gefunden</h1>
    <p class="state error" role="alert">
      Das angeforderte Gesprächsarchiv ist nicht vorhanden.
    </p>
  {:else if archiveState === "forbidden"}
    <h1>Kein Zugriff</h1>
    <p class="state error" role="alert">
      Du darfst dieses Gesprächsarchiv nicht ansehen.
    </p>
  {:else if archiveState === "malformed"}
    <h1>Archivdaten unvollständig</h1>
    <p class="state error" role="alert">
      Das Gesprächsarchiv konnte nicht sicher dargestellt werden.
    </p>
  {:else if archiveState === "error"}
    <h1>Gesprächsarchiv nicht verfügbar</h1>
    <p class="state error" role="alert">
      Das Gesprächsarchiv kann gerade nicht geladen werden. Bitte versuche es
      später erneut.
    </p>
  {:else if archive}
    <header class="archive-header">
      <p class="eyebrow">Schreibgeschütztes Gesprächsarchiv</p>
      <h1>{archive.conversation.node_title_snapshot}</h1>
      <dl>
        <div>
          <dt>Ursprünglicher Knoten</dt>
          <dd>{archive.conversation.node_id_snapshot}</dd>
        </div>
        <div>
          <dt>Archiviert</dt>
          <dd>
            <time datetime={archive.conversation.archived_at}>
              {archiveDate.format(new Date(archive.conversation.archived_at))}
            </time>
          </dd>
        </div>
      </dl>
    </header>

    <section aria-labelledby="archive-messages-heading">
      <h2 id="archive-messages-heading">Erhaltene Gesprächsbeiträge</h2>
      {#if archive.messages.length === 0}
        <p class="state" role="status">
          Dieses Gesprächsarchiv enthält keine Beiträge.
        </p>
      {:else}
        <ol class="messages" aria-label="Archivierte Gesprächsbeiträge">
          {#each archive.messages as message, index (message.id)}
            <li class:deleted={message.deleted_at !== null}>
              <article aria-labelledby={`archive-message-${index}`}>
                <header>
                  <h3 id={`archive-message-${index}`}>
                    {message.author_title}
                  </h3>
                  <time datetime={message.created_at}>
                    {archiveDate.format(new Date(message.created_at))}
                  </time>
                </header>
                {#if message.deleted_at}
                  <p class="tombstone">Beitrag entfernt.</p>
                {:else}
                  <p class="content">{message.content}</p>
                {/if}
              </article>
            </li>
          {/each}
        </ol>
      {/if}
    </section>
  {/if}
</main>

<style>
  .archive {
    max-width: 48rem;
    margin: 0 auto;
    padding: 2rem 1.5rem 3rem;
    color: var(--text);
  }

  .archive-header,
  section {
    display: grid;
    gap: 1rem;
  }

  section {
    margin-top: 2rem;
  }

  h1,
  h2,
  h3,
  p,
  dl,
  dd {
    margin: 0;
  }

  header > p:not(.eyebrow) {
    margin-top: 0.75rem;
    line-height: 1.6;
  }

  .eyebrow,
  dt,
  time,
  .state,
  .tombstone {
    color: var(--muted);
  }

  .eyebrow {
    font-weight: 700;
  }

  dl {
    display: grid;
    gap: 0.75rem;
    padding: 1rem;
    border: 1px solid var(--panel-border);
    border-radius: 10px;
    background: var(--panel-solid);
  }

  dl div {
    display: grid;
    gap: 0.2rem;
  }

  dt {
    font-size: 0.85rem;
  }

  dd {
    overflow-wrap: anywhere;
  }

  .months,
  .messages {
    display: grid;
    gap: 0.85rem;
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .months li,
  .messages li {
    padding: 1rem;
    border: 1px solid var(--panel-border);
    border-radius: 10px;
    background: var(--panel-solid);
  }

  .months li {
    padding: 0.85rem 1rem;
    border-color: var(--panel-border, rgba(255, 255, 255, 0.06));
    border-radius: 0.5rem;
    background: var(--panel, #141a21);
    transition:
      background 0.2s ease-in-out,
      transform 0.2s ease-in-out;
  }

  .months li:hover,
  .months li:focus-within {
    background: var(--accent-soft, #ececec);
    transform: translateY(-1px);
  }

  .months a {
    color: inherit;
    font-weight: 600;
    text-decoration: none;
  }

  .messages li.deleted {
    background: transparent;
  }

  article header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 0.65rem;
  }

  h3 {
    font-size: 1rem;
  }

  .content {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .error {
    color: var(--danger);
  }
</style>
