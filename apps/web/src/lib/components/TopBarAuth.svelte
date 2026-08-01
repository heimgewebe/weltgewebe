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
      class="message-entry"
      href="/nachrichten"
      aria-label="Private Nachrichten"
      title="Private Nachrichten"
    >
      <span aria-hidden="true">✉</span>
    </a>
  {/if}

  <a
    class="garnrolle-link"
    href="/settings"
    aria-label="Einstellungen öffnen"
    title="Einstellungen"
  >
    <img src={garnrolleIcon} alt="" />
  </a>

  {#if authView.showAccountLink}
    {#if authView.showRetry}
      <button
        type="button"
        class="auth-retry"
        on:click={retryAuth}
        aria-label="Anmeldung erneut prüfen"
      >
        <span class="auth-symbol" aria-hidden="true">↻</span>
        <span class="auth-label">{authView.retryLabel}</span>
      </button>
    {/if}
  {:else if authView.showLoginLink}
    <a class="login-entry" href="/login" aria-label="Anmelden">
      <span class="auth-symbol" aria-hidden="true">↪</span>
      <span class="auth-label">Anmelden</span>
    </a>
  {:else}
    <button
      type="button"
      class="login-entry"
      on:click={retryAuth}
      aria-label="Anmeldung erneut prüfen"
    >
      <span class="auth-symbol" aria-hidden="true">↻</span>
      <span class="auth-label">{authView.retryLabel}</span>
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
  .message-entry:focus-visible,
  .login-entry:focus-visible,
  .auth-retry:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 3px;
  }

  .message-entry,
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

  .message-entry {
    box-sizing: border-box;
    width: 44px;
    min-width: 44px;
    padding: 0;
    font-size: 1.15rem;
    line-height: 1;
  }

  .auth-symbol {
    display: none;
    font-size: 1.15rem;
    line-height: 1;
  }

  .auth-retry {
    min-height: 36px;
    max-width: 9rem;
    padding: 0 0.65rem;
    font-size: 0.75rem;
  }

  @media (max-width: 360px) {
    .auth-slot {
      gap: 0.125rem;
    }

    .login-entry,
    .auth-retry {
      box-sizing: border-box;
      width: 44px;
      min-width: 44px;
      min-height: 44px;
      padding: 0;
    }

    .auth-symbol {
      display: inline;
    }

    .auth-label {
      display: none;
    }
  }
</style>
