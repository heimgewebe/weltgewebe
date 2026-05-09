<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { authStore } from '$lib/auth/store';
  import { isRecord } from '$lib/utils/guards';

  interface DeviceInfo {
    device_id: string;
    created_at: string;
    last_active: string;
    current: boolean;
  }

  let devices: DeviceInfo[] = [];
  let devicesStatus: 'idle' | 'loading' | 'ok' | 'unauthorized' | 'error' = 'idle';
  let actionMessage: string | null = null;
  let actionVariant: 'info' | 'error' | 'success' = 'info';
  let pending = false;

  function formatTimestamp(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat('de-DE', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date);
  }

  function shortenDeviceId(id: string): string {
    if (id.length <= 12) return id;
    return `${id.slice(0, 8)}…${id.slice(-4)}`;
  }

  function isDeviceInfo(value: unknown): value is DeviceInfo {
    if (!isRecord(value)) return false;
    return (
      typeof value.device_id === 'string' &&
      typeof value.created_at === 'string' &&
      typeof value.last_active === 'string' &&
      typeof value.current === 'boolean'
    );
  }

  async function loadDevices() {
    if (!browser) return;
    if (!$authStore.authenticated) {
      devicesStatus = 'unauthorized';
      devices = [];
      return;
    }
    devicesStatus = 'loading';
    try {
      const res = await fetch('/api/auth/devices', { credentials: 'include' });
      if (res.status === 401) {
        devicesStatus = 'unauthorized';
        devices = [];
        return;
      }
      if (!res.ok) {
        devicesStatus = 'error';
        devices = [];
        return;
      }
      const data = (await res.json()) as unknown;
      if (Array.isArray(data) && data.every(isDeviceInfo)) {
        devices = data;
        devicesStatus = 'ok';
      } else {
        devicesStatus = 'error';
        devices = [];
      }
    } catch {
      devicesStatus = 'error';
      devices = [];
    }
  }

  async function handleLogout() {
    if (pending) return;
    pending = true;
    actionMessage = null;
    try {
      await authStore.logout();
      actionVariant = 'info';
      actionMessage = 'Abgemeldet.';
      devices = [];
      devicesStatus = 'unauthorized';
    } finally {
      pending = false;
    }
  }

  async function handleLogoutAll() {
    if (pending || !browser) return;
    pending = true;
    actionMessage = null;
    try {
      const res = await fetch('/api/auth/logout-all', {
        method: 'POST',
        credentials: 'include'
      });
      if (res.status === 403) {
        const payload = await res.json().catch(() => null);
        if (
          isRecord(payload) &&
          payload.error === 'STEP_UP_REQUIRED' &&
          typeof payload.challenge_id === 'string'
        ) {
          try {
            const stepUpRes = await fetch('/api/auth/step-up/magic-link/request', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              credentials: 'include',
              body: JSON.stringify({ challenge_id: payload.challenge_id })
            });
            if (stepUpRes.ok) {
              actionVariant = 'info';
              actionMessage =
                'Zur Bestätigung wurde ein Bestätigungslink an deine hinterlegte E-Mail-Adresse versendet.';
            } else {
              actionVariant = 'error';
              actionMessage = 'Bestätigungslink konnte nicht versendet werden.';
            }
          } catch {
            actionVariant = 'error';
            actionMessage = 'Netzwerkfehler beim Versenden des Bestätigungslinks.';
          }
          return;
        }
      }
      if (!res.ok) {
        actionVariant = 'error';
        actionMessage = 'Aktion konnte nicht ausgelöst werden.';
        return;
      }
      actionVariant = 'success';
      actionMessage = 'Alle Sitzungen wurden beendet.';
      await authStore.checkAuth();
    } catch {
      actionVariant = 'error';
      actionMessage = 'Netzwerkfehler beim Auslösen der Aktion.';
    } finally {
      pending = false;
    }
  }

  let lastAuthenticated: boolean | null = null;

  onMount(() => {
    const unsubscribe = authStore.subscribe((state) => {
      if (state.authenticated === lastAuthenticated) return;
      lastAuthenticated = state.authenticated;
      if (state.authenticated) {
        void loadDevices();
      } else {
        devices = [];
        devicesStatus = 'unauthorized';
      }
    });
    return unsubscribe;
  });
</script>

<section class="account-section" data-testid="account-section">
  <h2>Konto &amp; Sicherheit</h2>

  {#if !$authStore.authenticated}
    <div class="row" data-testid="account-section-anonymous">
      <p class="muted">Du bist derzeit nicht angemeldet.</p>
      <a class="btn btn-primary" href="/login">Login</a>
    </div>
  {:else}
    <dl class="status" data-testid="account-section-status">
      <dt>Konto</dt>
      <dd data-testid="account-section-account-id">
        {$authStore.account_id ?? '–'}
      </dd>
      <dt>Rolle</dt>
      <dd data-testid="account-section-role">{$authStore.role}</dd>
    </dl>

    <div class="actions">
      <button
        type="button"
        class="btn"
        on:click={handleLogout}
        disabled={pending}
        data-testid="account-section-logout"
      >
        Abmelden
      </button>
      <button
        type="button"
        class="btn btn-secondary"
        on:click={handleLogoutAll}
        disabled={pending}
        data-testid="account-section-logout-all"
      >
        Auf allen Geräten abmelden
      </button>
    </div>

    {#if actionMessage}
      <div
        class="message {actionVariant}"
        role={actionVariant === 'error' ? 'alert' : 'status'}
        aria-live={actionVariant === 'error' ? 'assertive' : 'polite'}
        data-testid="account-section-action-message"
      >
        {actionMessage}
      </div>
    {/if}

    <div class="devices" data-testid="account-section-devices">
      <h3>Aktive Geräte</h3>
      {#if devicesStatus === 'loading'}
        <p class="muted">Wird geladen…</p>
      {:else if devicesStatus === 'unauthorized'}
        <p class="muted">Geräteliste benötigt eine aktive Sitzung.</p>
      {:else if devicesStatus === 'error'}
        <p class="error">Geräteliste konnte nicht geladen werden.</p>
      {:else if devices.length === 0}
        <p class="muted">Keine aktiven Geräte gefunden.</p>
      {:else}
        <ul>
          {#each devices as device (device.device_id)}
            <li
              class="device"
              class:current={device.current}
              data-testid="account-section-device"
              data-device-current={device.current ? 'true' : 'false'}
            >
              <div class="device-id">
                <code>{shortenDeviceId(device.device_id)}</code>
                {#if device.current}
                  <span class="badge" data-testid="account-section-device-current">
                    Dieses Gerät
                  </span>
                {/if}
              </div>
              <div class="device-meta">
                Erstellt: {formatTimestamp(device.created_at)}
                · Zuletzt aktiv: {formatTimestamp(device.last_active)}
              </div>
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <div class="passkey" data-testid="account-section-passkey">
      <h3>Passkey</h3>
      <p class="muted">
        Passkeys sind als optionaler Komfort- und Sicherheitsgewinn vorgesehen
        (siehe Auth-Roadmap Phase 4). Die Aktivierung wird hier sichtbar gemacht,
        sobald Register-Verify, Auth-Optionen und Auth-Verify im Backend
        vollständig nachgewiesen sind.
      </p>
      <button
        type="button"
        class="btn"
        disabled
        aria-disabled="true"
        data-testid="account-section-passkey-cta"
        title="Backend-Pfad noch nicht vollständig implementiert"
      >
        Passkey aktivieren (demnächst)
      </button>
    </div>
  {/if}
</section>

<style>
  .account-section {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  h2 {
    font-size: 1.25rem;
    margin: 0;
  }
  h3 {
    font-size: 1rem;
    margin: 0 0 0.5rem;
  }
  .row {
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
  }
  .status {
    display: grid;
    grid-template-columns: max-content 1fr;
    column-gap: 16px;
    row-gap: 4px;
    margin: 0;
  }
  .status dt {
    font-weight: 600;
    opacity: 0.8;
  }
  .status dd {
    margin: 0;
    font-family: monospace;
    word-break: break-all;
  }
  .actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .btn {
    cursor: pointer;
    padding: 0.45rem 0.9rem;
    border-radius: 6px;
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.12));
    background: transparent;
    color: inherit;
    font: inherit;
  }
  .btn[disabled] {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .btn-primary {
    background: var(--accent, #ff8c42);
    color: var(--bg, #0e1116);
    border-color: transparent;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
  }
  .btn-secondary {
    background: rgba(255, 255, 255, 0.04);
  }
  .message {
    padding: 8px 12px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.08));
    font-size: 0.9rem;
  }
  .message.success {
    border-color: var(--color-theme-2, #2ecc71);
    color: var(--color-theme-2, #2ecc71);
  }
  .message.error {
    border-color: var(--color-danger, #ff6b6b);
    color: var(--color-danger, #ff6b6b);
  }
  .devices ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .device {
    padding: 8px 12px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.08));
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .device.current {
    border-color: var(--accent, #ff8c42);
  }
  .device-id {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .device-meta {
    font-size: 0.8rem;
    opacity: 0.75;
  }
  .badge {
    font-size: 0.7rem;
    padding: 2px 6px;
    border-radius: 99px;
    background: var(--accent, #ff8c42);
    color: var(--bg, #0e1116);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .muted {
    opacity: 0.75;
    margin: 0;
  }
  .error {
    color: var(--color-danger, #ff6b6b);
    margin: 0;
  }
  .passkey {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
</style>
