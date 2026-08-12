<script lang="ts">
  import { authStore } from "$lib/auth/store";
  import { onDestroy } from "svelte";

  interface Props {
    balance?: string;
    trend?: "stable" | "up" | "down";
    note?: string;
  }

  let {
    balance = "1 250 WE",
    trend = "stable",
    note = "Attrappe · UX-Test",
  }: Props = $props();

  const trendLabels = {
    stable: "gleichbleibend",
    up: "steigend",
    down: "sinkend",
  } as const;

  let loggedIn = $state(false);

  const unsubscribe = authStore.subscribe((value) => {
    loggedIn = value.authenticated;
  });

  onDestroy(unsubscribe);
</script>

<div
  class="gewebekonto panel"
  role="group"
  aria-label="Gewebekonto-Widget (Attrappe)"
>
  <div class="meta row">
    <span class="badge">Gewebekonto</span>
    <span class="ghost">Status: {trendLabels[trend]}</span>
  </div>
  <div class="balance" aria-live="polite">
    <strong>{balance}</strong>
  </div>
  <p class="note ghost">{note}</p>
  <div class="actions row" aria-hidden="true">
    <button class="btn" type="button" disabled title="Funktion folgt – Attrappe"
      >Einzahlen</button
    >
    <button class="btn" type="button" disabled title="Funktion folgt – Attrappe"
      >Auszahlen</button
    >
  </div>
  <div class="auth-actions row">
    {#if loggedIn}
      <button
        class="btn ghost"
        type="button"
        onclick={() => authStore.logout()}
        data-testid="widget-logout">Abmelden</button
      >
    {:else}
      <button
        class="btn"
        type="button"
        onclick={() =>
          authStore.devLogin("7d97a42e-3704-4a33-a61f-0e0a6b4d65d8")}
        >Login Demo</button
      >
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
