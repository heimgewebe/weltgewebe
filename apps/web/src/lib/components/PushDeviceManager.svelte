<script lang="ts">
  import { tick } from "svelte";
  import {
    deleteManagedPushSubscription,
    listPushSubscriptions,
    type ManagedPushSubscription,
  } from "$lib/api/notifications";
  import { describeNotificationError } from "$lib/notifications/feedback";

  interface Props {
    currentEndpoint?: string | null;
  }

  let { currentEndpoint = null }: Props = $props();
  let subscriptions: ManagedPushSubscription[] = $state([]);
  let limit = $state(20);
  let loading = $state(true);
  let error = $state("");
  let notice = $state("");
  let removingId: string | null = $state(null);
  let noticeElement: HTMLParagraphElement | null = $state(null);
  let requestVersion = 0;

  function deviceLabel(subscription: ManagedPushSubscription): string {
    if (subscription.current) return "Dieses Gerät";
    const otherIndex = subscriptions
      .filter((item) => !item.current)
      .findIndex((item) => item.id === subscription.id);
    return `Push-Gerät ${Math.max(1, otherIndex + 1)}`;
  }

  function registeredAt(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Registrierungszeit unbekannt";
    return `Registriert ${new Intl.DateTimeFormat("de-DE", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date)}`;
  }

  async function loadDevices(
    endpoint: string | null = currentEndpoint,
    showLoading = true,
  ): Promise<boolean> {
    const version = ++requestVersion;
    if (showLoading) loading = true;
    error = "";
    try {
      const view = await listPushSubscriptions(endpoint);
      if (version !== requestVersion) return false;
      subscriptions = view.items;
      limit = view.limit;
      return true;
    } catch (cause) {
      if (version !== requestVersion) return false;
      error = describeNotificationError(cause, "device-list");
      return false;
    } finally {
      if (version === requestVersion && showLoading) loading = false;
    }
  }

  async function removeDevice(subscription: ManagedPushSubscription): Promise<void> {
    if (subscription.current || removingId) return;
    removingId = subscription.id;
    error = "";
    notice = "";
    try {
      await deleteManagedPushSubscription(subscription.id, currentEndpoint);
      subscriptions = subscriptions.filter((item) => item.id !== subscription.id);
      notice = "Push-Gerät entfernt. Ein Platz für ein neues Push-Gerät ist wieder frei.";
      await loadDevices(currentEndpoint, false);
      await tick();
      noticeElement?.focus();
    } catch (cause) {
      error = describeNotificationError(cause, "device-remove");
    } finally {
      removingId = null;
    }
  }

  $effect(() => {
    const endpoint = currentEndpoint;
    void loadDevices(endpoint);
  });
</script>

<section
  class="managed-devices"
  aria-labelledby="push-device-manager-heading"
  aria-busy={loading || removingId !== null}
>
  <div class="manager-heading">
    <div>
      <h3 id="push-device-manager-heading">Registrierte Push-Geräte</h3>
      <p>
        Hier siehst du nur Push-Abos dieses Kontos, keine vollständigen
        Geräteprofile. Nicht mehr benötigte Einträge kannst du entfernen.
      </p>
    </div>
    {#if !loading && !error}
      <span class="device-count" aria-label={`${subscriptions.length} von ${limit} Push-Geräten belegt`}>
        {subscriptions.length} / {limit}
      </span>
    {/if}
  </div>

  {#if loading}
    <p class="status" role="status">Push-Geräte werden geladen …</p>
  {:else if error}
    <div class="status error status-with-action" role="alert">
      <p>{error}</p>
      <button class="btn secondary touch-target" type="button" onclick={() => void loadDevices()}>
        Erneut laden
      </button>
    </div>
  {:else}
    {#if subscriptions.length >= limit}
      <p class="status warning" role="status">
        Das Push-Gerätelimit ist erreicht. Entferne ein nicht mehr benötigtes
        Gerät; danach kannst du Push auf einem neuen Gerät wieder aktivieren.
      </p>
    {/if}

    {#if subscriptions.length === 0}
      <p class="empty-state">Für dieses Konto sind keine aktiven Push-Geräte registriert.</p>
    {:else}
      <ul class="device-list" aria-label="Aktive Push-Geräte">
        {#each subscriptions as subscription (subscription.id)}
          <li class="device-row">
            <div class="device-copy">
              <div class="device-title">
                <strong>{deviceLabel(subscription)}</strong>
                {#if subscription.current}<span class="current-badge">Aktuell</span>{/if}
              </div>
              <p>{registeredAt(subscription.created_at)}</p>
              {#if subscription.current}
                <p class="current-note">
                  Dieses Gerät wird mit „Auf diesem Gerät deaktivieren“ entfernt,
                  damit nicht versehentlich das falsche Browser-Abo beendet wird.
                </p>
              {/if}
            </div>

            {#if !subscription.current}
              <button
                class="btn secondary touch-target remove-button"
                type="button"
                disabled={removingId !== null}
                aria-label={`${deviceLabel(subscription)} aus den registrierten Push-Geräten entfernen`}
                onclick={() => void removeDevice(subscription)}
              >
                {removingId === subscription.id ? "Wird entfernt …" : "Gerät entfernen"}
              </button>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  {/if}

  {#if notice}
    <p
      class="status success"
      aria-live="polite"
      tabindex="-1"
      bind:this={noticeElement}
    >
      {notice}
    </p>
  {/if}
</section>

<style>
  .managed-devices {
    display: grid;
    gap: 0.8rem;
    padding: 1rem;
    border: 1px solid var(--panel-border);
    border-radius: var(--radius, 0.8rem);
    background: var(--panel-solid);
  }

  .manager-heading,
  .device-row,
  .status-with-action {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  h3,
  p {
    margin: 0;
  }

  .manager-heading p,
  .device-copy p,
  .empty-state {
    color: var(--muted);
  }

  .device-count,
  .current-badge {
    flex: 0 0 auto;
    border: 1px solid var(--panel-border);
    border-radius: 999px;
    padding: 0.25rem 0.55rem;
    font-size: 0.82rem;
  }

  .device-list {
    display: grid;
    gap: 0.7rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .device-row {
    padding: 0.85rem;
    border: 1px solid var(--panel-border);
    border-radius: 0.65rem;
  }

  .device-copy {
    display: grid;
    gap: 0.25rem;
    min-width: 0;
  }

  .device-title {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .current-note {
    max-width: 58ch;
  }

  .touch-target {
    min-height: 44px;
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
    .manager-heading,
    .device-row,
    .status-with-action {
      align-items: stretch;
      flex-direction: column;
    }

    .device-count {
      align-self: flex-start;
    }

    .remove-button,
    .status-with-action button {
      width: 100%;
    }
  }
</style>
