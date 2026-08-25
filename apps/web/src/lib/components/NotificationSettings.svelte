<script lang="ts">
  import { onMount } from "svelte";
  import {
    applicationServerKey,
    deletePushSubscription,
    getNotificationPreferences,
    getPushConfig,
    registerPushSubscription,
    updateNotificationPreferences,
    type NotificationPreferences,
    type PushConfig,
  } from "$lib/api/notifications";
  import {
    PUSH_PERMISSION_BLOCKED,
    describeNotificationError,
  } from "$lib/notifications/feedback";

  let supported = $state(false);
  let loading = $state(true);
  let savingPreference = $state(false);
  let changingDevice = $state(false);
  let config: PushConfig | null = $state(null);
  let preferences: NotificationPreferences = $state({
    direct_messages_push: false,
  });
  let browserSubscription: PushSubscription | null = $state(null);
  let pendingRemovalEndpoint: string | null = $state(null);
  let permission: NotificationPermission | "unsupported" =
    $state("unsupported");
  let error = $state("");
  let warning = $state("");
  let notice = $state("");

  function clearFeedback(): void {
    error = "";
    warning = "";
    notice = "";
  }

  function refreshPermission(): void {
    if (!supported || document.visibilityState === "hidden") return;
    permission = Notification.permission;
  }

  async function loadBrowserSubscription(): Promise<void> {
    const registration = await navigator.serviceWorker.getRegistration("/");
    browserSubscription =
      (await registration?.pushManager.getSubscription()) ?? null;
  }

  async function load(): Promise<void> {
    loading = true;
    clearFeedback();
    const controller = new AbortController();
    try {
      [config, preferences] = await Promise.all([
        getPushConfig(controller.signal),
        getNotificationPreferences(controller.signal),
      ]);
      await loadBrowserSubscription();
      refreshPermission();
    } catch (cause) {
      error = describeNotificationError(cause, "load");
    } finally {
      loading = false;
    }
  }

  async function changePreference(event: Event): Promise<void> {
    const checked = (event.currentTarget as HTMLInputElement).checked;
    const previous = preferences.direct_messages_push;
    preferences = { ...preferences, direct_messages_push: checked };
    savingPreference = true;
    clearFeedback();
    try {
      preferences = await updateNotificationPreferences(checked);
      notice = checked
        ? browserSubscription
          ? "Push-Hinweise für private Nachrichten sind für dein Konto eingeschaltet."
          : "Push-Hinweise sind für dein Konto eingeschaltet. Aktiviere dieses Gerät, um sie hier zu empfangen."
        : "Push-Hinweise für private Nachrichten sind für dein Konto ausgeschaltet.";
    } catch (cause) {
      preferences = { ...preferences, direct_messages_push: previous };
      error = describeNotificationError(cause, "preference");
    } finally {
      savingPreference = false;
    }
  }

  async function enableCurrentDevice(): Promise<void> {
    if (changingDevice || !config?.enabled || !config.application_server_key)
      return;
    if (permission === "denied") {
      warning = PUSH_PERMISSION_BLOCKED;
      return;
    }

    changingDevice = true;
    clearFeedback();
    let createdSubscription: PushSubscription | null = null;
    let registeredEndpoint: string | null = null;
    try {
      permission = await Notification.requestPermission();
      if (permission !== "granted") {
        warning =
          permission === "denied"
            ? PUSH_PERMISSION_BLOCKED
            : "Benachrichtigungen wurden nicht freigegeben. Ohne Freigabe bleibt Push auf diesem Gerät aus.";
        return;
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
      registeredEndpoint = createdSubscription.endpoint;
      preferences = await updateNotificationPreferences(true);
      browserSubscription = createdSubscription;
      notice =
        "Push ist auf diesem Gerät aktiviert. Push-Hinweise für private Nachrichten sind für dein Konto eingeschaltet.";
    } catch (cause) {
      if (registeredEndpoint) {
        await deletePushSubscription(registeredEndpoint).catch(() => undefined);
      }
      if (createdSubscription && !browserSubscription) {
        await createdSubscription.unsubscribe().catch(() => false);
      }
      error = describeNotificationError(cause, "device");
    } finally {
      changingDevice = false;
    }
  }

  function removalWarning(): string {
    return "Push ist auf diesem Gerät deaktiviert. Der gespeicherte Geräte-Eintrag konnte gerade nicht entfernt werden und kann vorübergehend noch als aktives Gerät zählen.";
  }

  async function retryServerRemoval(): Promise<void> {
    if (changingDevice || !pendingRemovalEndpoint) return;
    changingDevice = true;
    clearFeedback();
    const endpoint = pendingRemovalEndpoint;
    try {
      await deletePushSubscription(endpoint);
      pendingRemovalEndpoint = null;
      notice = "Der alte Geräte-Eintrag wurde entfernt.";
    } catch {
      // Keep pendingRemovalEndpoint intact. Its dedicated status stays visible
      // until the server confirms that the stale device entry is gone.
    } finally {
      changingDevice = false;
    }
  }

  async function disableCurrentDevice(): Promise<void> {
    if (changingDevice || !browserSubscription) return;
    changingDevice = true;
    clearFeedback();
    const endpoint = browserSubscription.endpoint;
    try {
      await browserSubscription.unsubscribe();
      browserSubscription = null;
      try {
        await deletePushSubscription(endpoint);
        pendingRemovalEndpoint = null;
        notice = "Push ist auf diesem Gerät deaktiviert.";
      } catch {
        pendingRemovalEndpoint = endpoint;
      }
    } catch (cause) {
      error = describeNotificationError(cause, "device");
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

    const handleVisibilityChange = () => refreshPermission();
    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("focus", refreshPermission);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("focus", refreshPermission);
    };
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
      Web Push ist in diesem Browser oder in dieser Browser-Ansicht nicht
      verfügbar. Das Nachrichtenpostfach bleibt vollständig nutzbar.
    </p>
  {:else if loading}
    <p class="status">Benachrichtigungseinstellungen werden geladen …</p>
  {:else if error && !config}
    <div class="status error status-with-action" role="alert">
      <p>{error}</p>
      <button
        class="btn secondary touch-target"
        type="button"
        onclick={load}>Erneut versuchen</button
      >
    </div>
  {:else}
    <div class="preference-row">
      <div>
        <strong>Private Nachrichten</strong>
        <p>
          Diese Einstellung gilt für dein Konto. Push-Hinweise werden nur an
          Geräte gesendet, auf denen du Push zusätzlich aktiviert hast.
        </p>
      </div>
      <label class="switch-label">
        <input
          type="checkbox"
          aria-label="Push-Hinweise für private Nachrichten"
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
            Push ist auf diesem Gerät freigegeben.
          {:else if permission === "denied"}
            Benachrichtigungen sind im Browser oder Betriebssystem blockiert.
          {:else}
            Push ist auf diesem Gerät noch nicht aktiviert.
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
      {:else if permission === "denied"}
        <span class="blocked-action">
          In Browser- oder Systemeinstellungen freigeben
        </span>
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
        Push ist auf diesem Weltgewebe-Server derzeit nicht verfügbar. Deine
        Nachrichten bleiben im Postfach.
      </p>
    {/if}
    {#if notice}<p class="status success" aria-live="polite">{notice}</p>{/if}
    {#if warning}
      <div class="status warning status-with-action" role="status">
        <p>{warning}</p>
      </div>
    {/if}
    {#if pendingRemovalEndpoint}
      <div class="status warning status-with-action" role="status">
        <p>{removalWarning()}</p>
        <button
          class="btn secondary touch-target"
          type="button"
          disabled={changingDevice}
          onclick={retryServerRemoval}
        >
          {changingDevice ? "Wird entfernt …" : "Geräte-Eintrag erneut entfernen"}
        </button>
      </div>
    {/if}
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
  .device-card,
  .status-with-action {
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
  .device-card p,
  .blocked-action {
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
    .device-card,
    .status-with-action {
      align-items: stretch;
      flex-direction: column;
    }

    .section-heading .inbox-link,
    .device-card button,
    .status-with-action button {
      width: 100%;
    }
  }
</style>
