<script lang="ts">
  import { afterNavigate } from "$app/navigation";
  import { onMount } from "svelte";
  import { accountAttentionInvalidation } from "$lib/accountAttention";
  import {
    listDirectConversations,
    type DirectConversation,
  } from "$lib/api/directMessages";
  import { listProposals, type Proposal } from "$lib/api/governance";
  import { authStore, type AuthStatus } from "$lib/auth/store";
  import { garnrolleIcon } from "$lib/ui/icons";
  import {
    countUnreadDirectMessages,
    hasAcceptedWeberApplication,
    hasPendingWeberApplication,
    unreadMessageBadgeLabel,
  } from "./topBarAttentionState";
  import { deriveTopBarAuthView } from "./topBarAuthState";

  const MESSAGE_POLL_MS = 30_000;

  let observedAccountId = "";
  let pendingWeberApplication = false;
  let unreadMessageCount = 0;
  let messageRequestRevision = 0;
  let weberRequestRevision = 0;

  $: authView = deriveTopBarAuthView($authStore);
  $: guestBadgeHref = pendingWeberApplication
    ? "/antraege"
    : "/antraege#antrag-stellen";
  $: guestBadgeAction = pendingWeberApplication
    ? "Weberstatus beantragt"
    : "Weber werden";
  $: guestBadgeTitle = pendingWeberApplication
    ? "Weberstatus beantragt – Antrag ansehen"
    : "Weberstatus beantragen";
  $: messageBadgeLabel = unreadMessageBadgeLabel(unreadMessageCount);
  $: messageAriaLabel =
    unreadMessageCount === 1
      ? "Private Nachrichten: 1 ungelesene Nachricht"
      : unreadMessageCount > 1
        ? `Private Nachrichten: ${unreadMessageCount} ungelesene Nachrichten`
        : "Private Nachrichten";

  function retryAuth() {
    void authStore.checkAuth({ force: true });
  }

  function resetAttention(accountId = "") {
    observedAccountId = accountId;
    pendingWeberApplication = false;
    unreadMessageCount = 0;
    messageRequestRevision += 1;
    weberRequestRevision += 1;
  }

  function ownsAttentionResult(accountId: string): boolean {
    return (
      $authStore.authenticated &&
      $authStore.account_id === accountId &&
      observedAccountId === accountId
    );
  }

  async function refreshMessages(status: AuthStatus) {
    const accountId = status.account_id;
    if (!status.authenticated || !accountId) return;

    const revision = ++messageRequestRevision;
    try {
      const conversations: DirectConversation[] = await listDirectConversations();
      if (
        revision !== messageRequestRevision ||
        !ownsAttentionResult(accountId)
      ) {
        return;
      }
      unreadMessageCount = countUnreadDirectMessages(conversations);
    } catch {
      // Keep the last confirmed count during transient API failures.
    }
  }

  async function refreshWeberApplication(status: AuthStatus) {
    const accountId = status.account_id;
    if (!status.authenticated || !accountId || status.role !== "gast") {
      weberRequestRevision += 1;
      pendingWeberApplication = false;
      return;
    }

    const revision = ++weberRequestRevision;
    try {
      const proposals: Proposal[] = await listProposals();
      if (
        revision !== weberRequestRevision ||
        !ownsAttentionResult(accountId) ||
        $authStore.role !== "gast"
      ) {
        return;
      }

      const pending = hasPendingWeberApplication(proposals, accountId);
      if (!pending && hasAcceptedWeberApplication(proposals, accountId)) {
        // A governance read can finalize the application and promote the account.
        // Keep the non-actionable application status visible until auth confirms
        // the new role, rather than briefly offering a second Weber application.
        pendingWeberApplication = true;
        await authStore.checkAuth({ force: true });
        return;
      }

      pendingWeberApplication = pending;
    } catch {
      // Keep the last confirmed application state during transient API failures.
    }
  }

  function refreshAttention(status: AuthStatus) {
    const accountId = status.account_id;
    if (!status.authenticated || !accountId) {
      resetAttention();
      return;
    }
    if (observedAccountId !== accountId) resetAttention(accountId);
    void refreshMessages(status);
    void refreshWeberApplication(status);
  }

  afterNavigate(() => {
    refreshAttention($authStore);
  });

  onMount(() => {
    let authKey = "";
    const unsubscribeAuth = authStore.subscribe((status) => {
      const nextAuthKey = status.authenticated
        ? `${status.account_id ?? ""}:${status.role}`
        : "";
      if (nextAuthKey === authKey) return;
      authKey = nextAuthKey;
      refreshAttention(status);
    });

    let attentionSignalPrimed = false;
    const unsubscribeAttention = accountAttentionInvalidation.subscribe(() => {
      if (!attentionSignalPrimed) {
        attentionSignalPrimed = true;
        return;
      }
      refreshAttention($authStore);
    });

    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") {
        refreshAttention($authStore);
      }
    };
    const refreshOnFocus = () => refreshAttention($authStore);
    const messagePoll = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void refreshMessages($authStore);
      }
    }, MESSAGE_POLL_MS);

    document.addEventListener("visibilitychange", refreshWhenVisible);
    window.addEventListener("focus", refreshOnFocus);

    return () => {
      unsubscribeAuth();
      unsubscribeAttention();
      window.clearInterval(messagePoll);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
      window.removeEventListener("focus", refreshOnFocus);
    };
  });
</script>

<div class="auth-slot">
  {#if authView.showAccountLink}
    <a
      class="message-entry"
      href="/nachrichten"
      aria-label={messageAriaLabel}
      title={messageAriaLabel}
    >
      <span aria-hidden="true">✉</span>
      {#if unreadMessageCount > 0}
        <span class="message-unread-badge" aria-hidden="true">
          {messageBadgeLabel}
        </span>
      {/if}
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

  {#if authView.isGuest}
    <a
      class:pending={pendingWeberApplication}
      class="guest-badge"
      href={guestBadgeHref}
      data-testid="topbar-guest-badge"
      aria-label={`Rolle: Gast – ${guestBadgeAction}`}
      title={guestBadgeTitle}
    >
      <span class="guest-badge-role">Gast</span>
      <span class="guest-badge-cta">{guestBadgeAction}</span>
    </a>
  {/if}

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
  .auth-retry:focus-visible,
  .guest-badge:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 3px;
  }

  .guest-badge {
    box-sizing: border-box;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-height: 44px;
    padding: 0 0.75rem;
    border: 1px solid var(--accent);
    border-radius: 999px;
    background: var(--accent-soft);
    color: var(--accent);
    text-decoration: none;
    font: inherit;
    font-weight: 700;
    white-space: nowrap;
  }

  .guest-badge-role {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .guest-badge-cta {
    font-size: 0.75rem;
    opacity: 0.9;
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
    position: relative;
    box-sizing: border-box;
    width: 44px;
    min-width: 44px;
    padding: 0;
    overflow: visible;
    font-size: 1.15rem;
    line-height: 1;
  }

  .message-unread-badge {
    position: absolute;
    top: -0.35rem;
    right: -0.4rem;
    box-sizing: border-box;
    display: grid;
    place-items: center;
    min-width: 1.25rem;
    height: 1.25rem;
    padding: 0 0.2rem;
    border: 2px solid var(--panel);
    border-radius: 999px;
    background: var(--accent);
    color: var(--accent-contrast, #fff);
    font-size: 0.65rem;
    font-weight: 800;
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

  @media (max-width: 510px) {
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

    .guest-badge {
      gap: 0;
      padding: 0 0.6rem;
    }

    .guest-badge-cta {
      display: none;
    }

    .guest-badge.pending {
      gap: 0.3rem;
    }

    .guest-badge.pending .guest-badge-cta {
      display: inline;
      max-width: 8.5rem;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }
</style>
