<script lang="ts">
  import { authStore } from '$lib/auth/store';
  import { onDestroy } from 'svelte';

  export let balance = "1 250 WE";
  export let trend: 'stable' | 'up' | 'down' = 'stable';
  export let note = "Attrappe · UX-Test";

  const trendLabels = {
    stable: 'gleichbleibend',
    up: 'steigend',
    down: 'sinkend'
  } as const;

  let loggedIn = false;

  const unsubscribe = authStore.subscribe((value) => {
    loggedIn = value.authenticated;
  });

  onDestroy(unsubscribe);
</script>

<div class="gewebekonto panel" role="group" aria-label="Gewebekonto-Widget (Attrappe)">
  <div class="meta row">
    <span class="badge">Gewebekonto</span>
    <span class="ghost">Status: {trendLabels[trend]}</span>
  </div>
  <div class="balance" aria-live="polite">
    <strong>{balance}</strong>
  </div>
  <p class="note ghost">{note}</p>
  <div class="actions row" aria-hidden="true">
    <button class="btn" type="button" disabled title="Funktion folgt – Attrappe">Einzahlen</button>
    <button class="btn" type="button" disabled title="Funktion folgt – Attrappe">Auszahlen</button>
  </div>
  <div class="auth-actions row">
    {#if loggedIn}
      <button class="btn ghost" type="button" on:click={() => authStore.logout()}>Abmelden</button>
    {:else}
      <button class="btn" type="button" on:click={() => authStore.devLogin('7d97a42e-3704-4a33-a61f-0e0a6b4d65d8')}>Login Demo</button>
    {/if}
  </div>
</div>

<style>
  .gewebekonto {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    min-width: 14rem;
  }

  .meta {
    justify-content: space-between;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .balance {
    font-size: 1.25rem;
  }

  .note {
    margin: 0;
  }

  .actions {
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  @media (max-width: 40rem) {
    .gewebekonto {
      width: 100%;
    }
  }
</style>
