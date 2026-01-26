<script lang="ts">
  import { authStore } from './store';
  import { browser, dev } from '$app/environment';

  async function logout() {
    if (!browser) return;
    await authStore.logout();
    window.location.reload();
  }
</script>

{#if browser && dev}
  <div class="auth-status">
    {#if $authStore.authenticated}
      <span class="role-badge" class:admin={$authStore.role === 'admin'} class:weber={$authStore.role === 'weber'}>
        {$authStore.role}
      </span>
      <button class="logout-btn" on:click={logout} title="Logout">
        ✕
      </button>
    {:else}
      <span class="role-badge gast">Gast</span>
      <a href="/_dev/auth" class="login-link">Login</a>
    {/if}
  </div>
{/if}

<style>
  .auth-status {
    position: fixed;
    top: 0.5rem;
    right: 0.5rem;
    z-index: 9999;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--color-bg-1, var(--panel));
    padding: 0.25rem;
    border-radius: 99px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    font-size: 0.8rem;
    pointer-events: auto;
  }

  .role-badge {
    padding: 0.1rem 0.5rem;
    border-radius: 99px;
    background: var(--color-bg-2, var(--muted));
    text-transform: uppercase;
    font-weight: bold;
    font-size: 0.7rem;
  }

  .role-badge.gast {
    background: var(--muted);
    color: var(--bg);
  }

  .role-badge.admin {
    background: var(--color-theme-1);
    color: var(--color-bg-1);
  }

  .role-badge.weber {
    background: var(--color-theme-2);
    color: var(--color-bg-1);
  }

  .login-link {
    font-size: 0.8rem;
    color: var(--fg, #e7ebee);
    text-decoration: none;
    font-weight: bold;
    padding: 0 0.25rem;
    margin-right: 0.25rem;
  }
  .login-link:hover {
     text-decoration: underline;
  }

  .logout-btn {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
    padding: 0 0.25rem;
    opacity: 0.6;
  }
  .logout-btn:hover {
    opacity: 1;
    color: var(--color-danger);
  }
</style>
