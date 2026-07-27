<script lang="ts">
  import GovernanceFan from "./GovernanceFan.svelte";
  import { authStore } from "$lib/auth/store";
  import { contextPanelOpen } from "$lib/stores/uiView";
  import { garnrolleIcon } from "$lib/ui/icons";

  function retryAuth() {
    void authStore.checkAuth({ force: true });
  }
</script>

<div
  class="topbar"
  class:panel-open={$contextPanelOpen}
  role="toolbar"
  aria-label="Navigation"
>
  <div class="governance-slot">
    <GovernanceFan />
  </div>
  {#if $authStore.state === "authenticated"}
    <a
      class="garnrolle-link"
      href="/settings#meine-garnrolle"
      aria-label="Meine Garnrolle einrichten"
    >
      <img src={garnrolleIcon} alt="" />
    </a>
  {:else if $authStore.state === "unauthenticated"}
    <a class="login-entry" href="/login">Anmelden</a>
  {:else}
    <button
      class="login-entry"
      disabled={$authStore.state === "checking"}
      on:click={retryAuth}
    >
      {$authStore.state === "checking"
        ? "Prüfe Anmeldung …"
        : "Verbindung gestört"}
    </button>
  {/if}
</div>

<style>
  .topbar {
    position: absolute;
    inset: 0 0 auto 0;
    min-height: var(--toolbar-offset);
    z-index: var(--z-map-topbar);
    display: grid;
    grid-template-columns: minmax(44px, 1fr) auto minmax(44px, 1fr);
    align-items: center;
    padding: env(safe-area-inset-top) 12px 0;
    background: linear-gradient(180deg, rgba(0, 0, 0, 0.46), rgba(0, 0, 0, 0));
    color: var(--text);
    pointer-events: none;
    transition: right var(--motion-ui);
  }

  .governance-slot {
    grid-column: 2;
    justify-self: center;
    pointer-events: auto;
  }

  .garnrolle-link,
  .login-entry {
    grid-column: 3;
    justify-self: end;
    pointer-events: auto;
  }

  .garnrolle-link {
    display: block;
    width: 44px;
    height: 44px;
    transition: transform 0.1s ease;
  }

  .garnrolle-link img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .garnrolle-link:active {
    transform: scale(0.95);
  }

  .garnrolle-link:focus-visible,
  .login-entry:focus-visible {
    outline: 2px solid var(--accent, #6aa6ff);
    outline-offset: 3px;
  }

  .login-entry {
    display: grid;
    place-items: center;
    min-height: 44px;
    padding: 0 0.9rem;
    border: 1px solid var(--panel-border-strong);
    border-radius: 999px;
    background: var(--panel);
    color: var(--text);
    text-decoration: none;
    font: inherit;
    font-weight: 600;
  }

  @media (min-width: 769px) {
    .topbar.panel-open {
      right: var(--context-panel-width);
      --governance-fan-menu-width: max(
        304px,
        calc(100vw - var(--context-panel-width) - 24px)
      );
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .topbar {
      transition: none;
    }
  }
</style>
