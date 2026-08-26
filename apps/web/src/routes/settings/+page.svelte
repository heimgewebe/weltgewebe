<script lang="ts">
  import { onMount, tick } from "svelte";
  import AccountSection from "$lib/components/AccountSection.svelte";
  import MyGarnrolleSection from "$lib/components/MyGarnrolleSection.svelte";
  import { authStore } from "$lib/auth/store";
  import type { PageData } from "./$types";

  interface Props {
    data: PageData;
  }

  let { data }: Props = $props();
  let NotificationSettings:
    | typeof import("$lib/components/NotificationSettings.svelte").default
    | null = $state(null);
  let notificationFallback: HTMLElement | null = $state(null);
  let notificationModuleError = $state(false);

  function focusNotificationFallback(): void {
    if (window.location.hash !== "#benachrichtigungen") return;
    notificationFallback?.focus({ preventScroll: true });
  }

  async function loadNotificationSettings(): Promise<void> {
    if (NotificationSettings) return;
    notificationModuleError = false;
    try {
      const module = await import("$lib/components/NotificationSettings.svelte");
      NotificationSettings = module.default;
    } catch {
      notificationModuleError = true;
      await tick();
      focusNotificationFallback();
    }
  }

  async function checkNotificationAuth(force = false): Promise<void> {
    const status = await authStore.checkAuth(force ? { force: true } : undefined);
    if (status.state === "authenticated" && status.authenticated) {
      await loadNotificationSettings();
      return;
    }
    await tick();
    focusNotificationFallback();
  }

  onMount(() => {
    let active = true;
    void checkNotificationAuth().then(() => {
      if (!active) return;
      focusNotificationFallback();
    });

    const handleHashChange = () => focusNotificationFallback();
    window.addEventListener("hashchange", handleHashChange);
    focusNotificationFallback();

    return () => {
      active = false;
      window.removeEventListener("hashchange", handleHashChange);
    };
  });
</script>

<svelte:head>
  <title>Einstellungen – Weltgewebe</title>
</svelte:head>

<div class="settings-page">
  <div class="container">
    <header class="page-header">
      <a class="back-link touch-target" href="/map">← Zur Karte</a>
      <h1>Einstellungen</h1>
      <p class="intro">
        Verwalte deine Garnrolle, dein Konto, Benachrichtigungen und die
        Darstellung an einem übersichtlichen Ort.
      </p>
    </header>

    <div class="settings-layout">
      <aside
        class="panel settings-menu"
        aria-label="Einstellungsmenü"
        data-testid="settings-menu"
      >
        <div class="col">
          <p class="menu-heading"><strong>Bereiche</strong></p>
          <nav class="menu-links" aria-label="Einstellungsbereiche">
            <a href="#meine-garnrolle">
              <strong>Meine Garnrolle</strong>
              <span>Profil, Kartenanker und Sichtbarkeit</span>
            </a>
            <a href="#benachrichtigungen">
              <strong>Benachrichtigungen</strong>
              <span>Push-Hinweise und dieses Gerät</span>
            </a>
            <a href="#konto-und-sicherheit">
              <strong>Konto &amp; Sicherheit</strong>
              <span>Sitzungen, Geräte und Anmeldung</span>
            </a>
          </nav>
        </div>

        <div class="col appearance-section">
          <label class="menu-heading" for="theme-select"
            ><strong>Darstellung</strong></label
          >
          <p class="menu-hint">
            „System“ folgt deinem Gerät. Die Auswahl gilt nur in diesem Browser.
          </p>
          <select
            id="theme-select"
            class="btn touch-target"
            data-wg-theme-control
            data-testid="theme-select"
          >
            <option value="system">System</option>
            <option value="light">Hell</option>
            <option value="dark">Dunkel</option>
          </select>
        </div>

        <a
          class="diagnostics-link touch-target"
          href="/build"
          data-testid="build-diagnostics-link"
        >
          Technische Build-Diagnose
        </a>
      </aside>

      <main class="col settings-content">
        <section class="panel primary-card" aria-label="Meine Garnrolle">
          <MyGarnrolleSection
            accounts={data.accounts}
            accountsLoadError={data.accountsLoadError}
          />
        </section>

        <div class="panel notification-card">
          {#if NotificationSettings}
            <NotificationSettings />
          {:else}
            <section
              bind:this={notificationFallback}
              id="benachrichtigungen"
              class="notification-placeholder"
              aria-labelledby="notification-settings-heading"
              tabindex="-1"
            >
              <div class="notification-heading">
                <div>
                  <p class="notification-eyebrow">Push für private Nachrichten</p>
                  <h2 id="notification-settings-heading">Benachrichtigungen</h2>
                </div>
                <a class="notification-inbox touch-target" href="/nachrichten"
                  >Zum Postfach</a
                >
              </div>

              {#if notificationModuleError}
                <div class="notification-status notification-error" role="alert">
                  <p>
                    Die Benachrichtigungseinstellungen konnten nicht geladen
                    werden. Versuche es erneut.
                  </p>
                  <button
                    class="btn secondary touch-target"
                    type="button"
                    onclick={loadNotificationSettings}>Erneut versuchen</button
                  >
                </div>
              {:else if $authStore.state === "degraded"}
                <div class="notification-status notification-error" role="alert">
                  <p>
                    Dein Anmeldestatus konnte nicht geprüft werden. Prüfe die
                    Verbindung und versuche es erneut.
                  </p>
                  <button
                    class="btn secondary touch-target"
                    type="button"
                    onclick={() => checkNotificationAuth(true)}
                    >Anmeldung erneut prüfen</button
                  >
                </div>
              {:else if $authStore.state === "unauthenticated"}
                <div class="notification-status" role="status">
                  <p>
                    Melde dich an, um Push-Hinweise und Gerätefreigaben zu
                    verwalten.
                  </p>
                  <a class="btn secondary touch-target" href="/login">Anmelden</a>
                </div>
              {:else}
                <p class="notification-status" role="status">
                  Benachrichtigungseinstellungen werden geladen …
                </p>
              {/if}
            </section>
          {/if}
        </div>

        <div id="konto-und-sicherheit" class="panel">
          <AccountSection />
        </div>
      </main>
    </div>
  </div>
</div>

<style>
  .settings-page {
    min-height: 100dvh;
    padding: clamp(1rem, 3vw, 2.5rem) 1rem 4rem;
  }

  .container {
    max-width: 75rem;
    margin: auto;
  }

  .page-header {
    display: grid;
    margin-bottom: clamp(1.5rem, 4vw, 2.5rem);
  }

  .page-header h1,
  .intro,
  .menu-heading,
  .menu-hint,
  .notification-placeholder h2,
  .notification-placeholder p {
    margin: 0;
  }

  .settings-layout {
    display: grid;
    grid-template-columns: minmax(15rem, 18rem) minmax(0, 1fr);
    align-items: start;
    gap: clamp(1rem, 3vw, 2rem);
  }

  .settings-menu {
    position: sticky;
    top: 1rem;
    display: grid;
    gap: 1rem;
  }

  .menu-links a {
    display: grid;
    padding: 0.6rem;
    color: var(--text);
    text-decoration: none;
  }

  .menu-links span,
  .menu-hint,
  .diagnostics-link,
  .notification-eyebrow {
    color: var(--muted);
    font-size: 0.82rem;
  }

  .back-link,
  .diagnostics-link,
  .notification-inbox {
    display: inline-flex;
    align-items: center;
    width: fit-content;
  }

  .touch-target {
    min-height: 44px;
  }

  .primary-card,
  .notification-card {
    padding: 0;
  }

  .primary-card :global(.my-garnrolle) {
    padding: clamp(1rem, 3vw, 1.5rem);
  }

  .notification-placeholder {
    display: grid;
    gap: 1rem;
    padding: clamp(1rem, 3vw, 1.5rem);
    scroll-margin-top: 1rem;
  }

  .notification-placeholder:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 3px;
  }

  .notification-heading,
  .notification-status {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  .notification-eyebrow {
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .notification-inbox {
    color: var(--accent);
  }

  .notification-status {
    padding: 0.75rem 0.9rem;
    border-radius: 0.65rem;
    background: var(--panel-solid);
  }

  .notification-error {
    border-inline-start: 3px solid var(--danger, currentColor);
  }

  @media (max-width: 860px) {
    .settings-layout {
      grid-template-columns: 1fr;
    }

    .settings-menu {
      position: static;
    }
  }

  @media (max-width: 620px) {
    .notification-heading,
    .notification-status {
      align-items: stretch;
      flex-direction: column;
    }

    .notification-heading .notification-inbox,
    .notification-status button,
    .notification-status a {
      width: 100%;
    }
  }
</style>
