<script lang="ts">
  import { onMount } from "svelte";
  import {
    NotificationsApiError,
    applicationServerKey,
    deletePushSubscription,
    getNotificationPreferences,
    getPushConfig,
    registerPushSubscription,
    updateNotificationPreferences,
    type NotificationPreferences,
    type PushConfig,
  } from "$lib/api/notifications";

  let supported = $state(false);
  let loading = $state(true);
  let savingPreference = $state(false);
  let changingDevice = $state(false);
  let config: PushConfig | null = $state(null);
  let preferences: NotificationPreferences = $state({
    direct_messages_push: false,
  });
  let browserSubscription: PushSubscription | null = $state(null);
  let permission: NotificationPermission | "unsupported" =
    $state("unsupported");
  let error = $state("");
  let notice = $state("");

  function describeError(cause: unknown): string {
    if (cause instanceof NotificationsApiError) {
      if (cause.status === 401)
        return "Bitte melde dich an, um Benachrichtigungen einzustellen.";
      if (cause.code === "push_not_configured")
        return "Push ist in dieser Weltgewebe-Zelle noch nicht eingerichtet.";
      if (cause.code === "push_delivery_unavailable")
        return "Der Push-Zustellweg ist derzeit nicht verbunden.";
      if (cause.code === "invalid_push_subscription")
        return "Die Browserfreigabe konnte nicht sicher übernommen werden.";
      if (cause.code === "push_subscription_limit_reached")
        return "Für dieses Konto sind bereits 20 Geräte aktiv. Deaktiviere zuerst ein nicht mehr verwendetes Gerät.";
    }
    if (cause instanceof Error && cause.message) return cause.message;
    return "Die Benachrichtigungseinstellung konnte nicht verarbeitet werden.";
  }

  async function loadBrowserSubscription(): Promise<void> {
    const registration = await navigator.serviceWorker.getRegistration("/");
    browserSubscription =
      (await registration?.pushManager.getSubscription()) ?? null;
  }

  async function load(): Promise<void> {
    loading = true;
    error = "";
    const controller = new AbortController();
    try {
      [config, preferences] = await Promise.all([
        getPushConfig(controller.signal),
        getNotificationPreferences(controller.signal),
      ]);
      await loadBrowserSubscription();
    } catch (cause) {
      error = describeError(cause);
    } finally {
      loading = false;
    }
  }

  async function changePreference(event: Event): Promise<void> {
    const checked = (event.currentTarget as HTMLInputElement).checked;
    const previous = preferences.direct_messages_push;
    preferences = { ...preferences, direct_messages_push: checked };
    savingPreference = true;
    error = "";
    notice = "";
    try {
      preferences = await updateNotificationPreferences(checked);
      notice = checked
        ? "Private Nachrichten sind für Push freigegeben."
        : "Push-Hinweise für private Nachrichten sind ausgeschaltet.";
    } catch (cause) {
      preferences = { ...preferences, direct_messages_push: previous };
      error = describeError(cause);
    } finally {
      savingPreference = false;
    }
  }

  async function enableCurrentDevice(): Promise<void> {
    if (changingDevice || !config?.enabled || !config.application_server_key)
      return;
    changingDevice = true;
    error = "";
    notice = "";
    let createdSubscription: PushSubscription | null = null;
    try {
      permission = await Notification.requestPermission();
      if (permission !== "granted") {
        throw new Error(
          "Das Gerät hat Push nicht freigegeben. Du kannst die Berechtigung in den Browser- oder Systemeinstellungen ändern.",
        );
      }
      const registration = await navigator.serviceWorker.register("/sw.js", {
        scope: "/",
      });
      await navigator.serviceWorker.ready;
      const existing = await registration.pushManager.getSubscription();
      createdSubscription =
        existing ??
        (await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: applicationServerKey(
            config.application_server_key,
          ),
        }));
      await registerPushSubscription(createdSubscription);
      preferences = await updateNotificationPreferences(true);
      browserSubscription = createdSubscription;
      notice = "Push ist auf diesem Gerät aktiviert.";
    } catch (cause) {
      if (createdSubscription && !browserSubscription) {
        await createdSubscription.unsubscribe().catch(() => false);
      }
      error = describeError(cause);
    } finally {
      changingDevice = false;
    }
  }

  async function disableCurrentDevice(): Promise<void> {
    if (changingDevice || !browserSubscription) return;
    changingDevice = true;
    error = "";
    notice = "";
    const endpoint = browserSubscription.endpoint;
    try {
      await browserSubscription.unsubscribe();
      browserSubscription = null;
      try {
        await deletePushSubscription(endpoint);
        notice = "Push ist auf diesem Gerät deaktiviert.";
      } catch (cause) {
        error = `${describeError(cause)} Die Browserfreigabe ist trotzdem beendet; der alte Endpunkt wird beim nächsten Zustellversuch automatisch stillgelegt.`;
      }
    } catch (cause) {
      error = describeError(cause);
    } finally {
      changingDevice = false;
    }
  }

  onMount(() => {
    supported =
      "serviceWorker" in navigator &&
      "PushManager" in window &&
      "Notification" in window;
    permission = supported ? Notification.permission : "unsupported";
    if (supported) void load();
    else loading = false;
  });
</script>

<section
  id="benachrichtigungen"
  class="notification-settings"
  aria-labelledby="notification-settings-heading"
>
  <div class="section-heading">
    <div>
      <p class="eyebrow">Benachrichtigungen</p>
      <h2 id="notification-settings-heading">Push auf deinen Geräten</h2>
    </div>
    <a class="inbox-link" href="/settings">Einstellungen</a>
  </div>

  <p class="explanation">
    Push ist nur ein Hinweis. Die Nachricht selbst bleibt im Weltgewebe und wird
    erst nach dem Öffnen geladen. Auf dem Sperrbildschirm erscheint daher kein
    Nachrichtentext und kein Absendername.
  </p>

  <p class="platform-note">
    Auf iPhone und iPad funktioniert Push in der zum Home-Bildschirm
    hinzugefügten Weltgewebe-Web-App.
  </p>

  {#if !supported}
    <p class="status warning">
      Dieser Browser unterstützt Web Push nicht. Das Nachrichtenpostfach bleibt
      vollständig nutzbar.
    </p>
  {:else if loading}
    <p class="status">Benachrichtigungseinstellungen werden geladen …</p>
  {:else if error && !config}
    <p class="status error" role="alert">{error}</p>
  {:else}
    <div class="preference-row">
      <div>
        <strong>Private Nachrichten</strong>
        <p>
          Kontoweit auswählbar. Ohne aktiviertes Gerät entstehen trotzdem keine
          Push-Hinweise.
        </p>
      </div>
      <label class="switch-label">
        <input
          type="checkbox"
          checked={preferences.direct_messages_push}
          disabled={savingPreference}
          onchange={changePreference}
        />
        <span>{preferences.direct_messages_push ? "An" : "Aus"}</span>
      </label>
    </div>

    <div class="device-card">
      <div>
        <strong>Dieses Gerät</strong>
        <p>
          {#if browserSubscription}
            Die Browserfreigabe ist aktiv.
          {:else if permission === "denied"}
            Push wurde im Browser oder Betriebssystem blockiert.
          {:else}
            Noch nicht für Push freigegeben.
          {/if}
        </p>
      </div>

      {#if browserSubscription}
        <button
          class="btn secondary touch-target"
          type="button"
          disabled={changingDevice}
          onclick={disableCurrentDevice}
        >
          {changingDevice
            ? "Wird deaktiviert …"
            : "Auf diesem Gerät deaktivieren"}
        </button>
      {:else}
        <button
          class="btn primary touch-target"
          type="button"
          disabled={changingDevice || !config?.enabled}
          onclick={enableCurrentDevice}
        >
          {changingDevice ? "Wird aktiviert …" : "Auf diesem Gerät aktivieren"}
        </button>
      {/if}
    </div>

    {#if config && !config.enabled}
      <p class="status warning">
        Die Oberfläche ist vorbereitet, aber der Betreiber hat den
        verschlüsselten Push-Zustellweg noch nicht konfiguriert.
      </p>
    {/if}
    {#if notice}<p class="status success" aria-live="polite">{notice}</p>{/if}
    {#if error}<p class="status error" role="alert">{error}</p>{/if}
  {/if}
</section>

<style>
  .notification-settings {
    display: grid;
    gap: 1rem;
    padding: clamp(1rem, 3vw, 1.5rem);
  }

  .section-heading,
  .preference-row,
  .device-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  h2,
  p {
    margin: 0;
  }

  .eyebrow {
    color: var(--muted);
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .explanation,
  .platform-note,
  .preference-row p,
  .device-card p {
    color: var(--muted);
  }

  .preference-row,
  .device-card {
    padding: 1rem;
    border: 1px solid var(--panel-border);
    border-radius: var(--radius, 0.8rem);
    background: var(--panel-solid);
  }

  .switch-label {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    min-height: 44px;
    white-space: nowrap;
  }

  .switch-label input {
    width: 1.2rem;
    height: 1.2rem;
  }

  .touch-target {
    min-height: 44px;
  }

  .inbox-link {
    color: var(--accent);
  }

  .status {
    padding: 0.75rem 0.9rem;
    border-radius: 0.65rem;
    background: var(--panel-solid);
  }

  .warning {
    border-inline-start: 3px solid var(--accent);
  }

  .error {
    border-inline-start: 3px solid var(--danger, currentColor);
  }

  .success {
    border-inline-start: 3px solid var(--accent);
  }

  @media (max-width: 620px) {
    .section-heading,
    .preference-row,
    .device-card {
      align-items: stretch;
      flex-direction: column;
    }

    .section-heading .inbox-link,
    .device-card button {
      width: 100%;
    }
  }
</style>
