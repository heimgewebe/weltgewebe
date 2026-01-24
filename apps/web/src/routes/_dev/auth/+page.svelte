<script lang="ts">
  import { onMount } from 'svelte';
  import { authStore } from '$lib/auth/store';

  interface DevAccount {
    id: string;
    title: string;
    role: string;
    summary?: string;
  }

  let accounts: DevAccount[] = [];
  let error: string | null = null;
  let loading = true;

  onMount(async () => {
    try {
      const res = await fetch('/api/auth/dev/accounts');
      if (res.ok) {
        accounts = await res.json();
      } else if (res.status === 404) {
        error = 'Dev login disabled (AUTH_DEV_LOGIN=0).';
      } else {
        error = `Failed to load accounts: ${res.status}`;
      }
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  });

  async function login(id: string) {
    try {
      await authStore.login(id);
      // Refresh to update UI
      window.location.reload();
    } catch (e) {
      alert('Login failed: ' + e);
    }
  }

  async function logout() {
    await authStore.logout();
    window.location.reload();
  }
</script>

<svelte:head>
  <title>Dev Login</title>
</svelte:head>

<div class="col" style="gap:1.5rem; padding:1.5rem; max-width:720px; margin:0 auto;">
  <header class="col" style="gap:.5rem;">
    <h1>Dev Login</h1>
    <p class="ghost">
      Wähle einen Account zum Einloggen. Nur verfügbar wenn AUTH_DEV_LOGIN=1.
    </p>

    {#if $authStore.authenticated}
      <div class="panel row" style="align-items:center; justify-content:space-between; border-color:var(--color-theme-1);">
        <div class="col">
          <strong>Angemeldet als:</strong>
          <span>{$authStore.role} (Account: {$authStore.account_id})</span>
        </div>
        <button class="btn" on:click={logout}>Logout</button>
      </div>
    {/if}
  </header>

  {#if loading}
    <p>Lade Accounts...</p>
  {:else if error}
    <div class="panel" style="border-color:var(--color-danger);">
      Error: {error}
    </div>
  {:else if accounts.length === 0}
    <p>Keine Accounts gefunden.</p>
  {:else}
    <ul class="col" style="gap:1rem; margin:0; padding:0; list-style:none;">
      {#each accounts as account}
        <li class="panel col" style="gap:.5rem;">
          <div class="row" style="justify-content:space-between; align-items:flex-start;">
            <div class="col">
              <h2 style="margin:0; font-size:1.1rem;">{account.title}</h2>
              <code style="font-size:0.8rem; opacity:0.7;">{account.id}</code>
            </div>
            <span class="badge">{account.role}</span>
          </div>

          {#if account.summary}
            <p>{account.summary}</p>
          {/if}

          <div class="row" style="justify-content:flex-end;">
            <button class="btn" on:click={() => login(account.id)} disabled={$authStore.authenticated && $authStore.account_id === account.id}>
              {#if $authStore.authenticated && $authStore.account_id === account.id}
                Aktuell
              {:else}
                Login als {account.role}
              {/if}
            </button>
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .badge {
    background: var(--color-bg-2);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: bold;
    text-transform: uppercase;
  }
</style>
