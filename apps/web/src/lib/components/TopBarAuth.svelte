<script lang="ts">
  import { authStore } from "$lib/auth/store";
  import { garnrolleIcon } from "$lib/ui/icons";
  import { deriveTopBarAuthView } from "./topBarAuthState";

  $: authView = deriveTopBarAuthView($authStore);

  function retryAuth() {
    void authStore.checkAuth({ force: true });
  }
</script>

<div class="auth-slot">
  {#if authView.showAccountLink}
    <a
      class="garnrolle-link"
      href="/settings"
      aria-label="Einstellungen öffnen"
      title="Einstellungen"
    >
      <img src={garnrolleIcon} alt="" />
    </a>
    {#if authView.showRetry}
      <button
        type="button"
        class="auth-retry"
        on:click={retryAuth}
        aria-label="Anmeldung erneut prüfen"
      >
        {authView.retryLabel}
      </button>
    {/if}
  {:else if authView.showLoginLink}
    <a class="login-entry" href="/login">Anmelden</a>
  {:else}
    <button
      type="button"
      class="login-entry"
      on:click={retryAuth}
      aria-label="Anmeldung erneut prüfen"
    >
      {authView.retryLabel}
    </button>
  {/if}
</div>

<style>
  .auth-slot {
    grid-column: 3;
    justify-self: end;
    display: flex;
    align-items: center;
    gap: 0.35rem;
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
  .login-entry:focus-visible,
  .auth-retry:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 3px;
  }

  .login-entry,
  .auth-retry {
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

  .auth-retry {
    min-height: 36px;
    max-width: 9rem;
    padding: 0 0.65rem;
    font-size: 0.75rem;
  }
</style>
