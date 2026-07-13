<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import { ICONS, MARKER_SIZES } from "$lib/ui/icons";
  import { authStore } from "$lib/auth/store";
  import { browser } from "$app/environment";
  import type { Account } from "$lib/map/types";
  import {
    describeGarnrolleVisibility,
    findOwnGarnrolle,
  } from "$lib/garnrolle/visibility";

  export let label = "Meine Garnrolle und Konto";
  export let accounts: Account[] = [];

  const dispatch = createEventDispatcher<{ requestZoomToOwnGarnrolle: void }>();
  let menuOpen = false;

  $: ownGarnrolle = findOwnGarnrolle(accounts, $authStore.account_id);
  $: visibility = describeGarnrolleVisibility(ownGarnrolle);

  function handleZoomToOwnGarnrolle() {
    menuOpen = false;
    dispatch("requestZoomToOwnGarnrolle");
  }

  function toggleMenu() {
    menuOpen = !menuOpen;
  }

  function closeMenu(event: MouseEvent) {
    if (!menuOpen) return;
    const target = event.target as HTMLElement;
    if (!target.closest(".garnrolle-container")) menuOpen = false;
  }

  function handleKeydown(event: KeyboardEvent) {
    if (!menuOpen) return;
    if (event.key === "Escape") {
      event.preventDefault();
      menuOpen = false;
    }
  }

  async function logout() {
    if (!browser) return;
    await authStore.logout();
    menuOpen = false;
  }
</script>

<svelte:window on:click={closeMenu} on:keydown|capture={handleKeydown} />

<div class="garnrolle-container wrap">
  {#if $authStore.authenticated}
    <button
      class="roll wrap-btn"
      aria-label={label}
      aria-expanded={menuOpen}
      on:click={toggleMenu}
      style="width: {MARKER_SIZES.account}px; height: {MARKER_SIZES.account}px;"
    >
      <img src={ICONS.garnrolle} alt="" />
    </button>

    {#if menuOpen}
      <div class="menu" aria-label="Meine Garnrolle und Konto">
        {#if visibility.canZoomToMap}
          <button class="menu-item" on:click={handleZoomToOwnGarnrolle}
            >Meine Garnrolle auf Karte zeigen</button
          >
        {/if}
        <a
          href="/settings#meine-garnrolle"
          class="menu-item"
          on:click={() => (menuOpen = false)}
        >
          {visibility.canZoomToMap
            ? "Meine Garnrolle"
            : "Meine Garnrolle (noch nicht auf der Karte)"}
        </a>
        <a
          href="/settings"
          class="menu-item"
          on:click={() => (menuOpen = false)}>Konto & Sicherheit</a
        >
        <button class="menu-item logout-btn" on:click={logout}>Abmelden</button>
      </div>
    {/if}
  {:else}
    <a class="login-entry" href="/login">Anmelden</a>
  {/if}
</div>

<style>
  .wrap {
    position: relative;
    display: inline-block;
  }
  .wrap-btn {
    background: none;
    border: none;
    padding: 0;
    margin: 0;
    color: inherit;
    appearance: none;
  }
  .wrap-btn:focus-visible,
  .login-entry:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 3px;
  }
  .roll {
    display: block;
    cursor: pointer;
    transition: transform 0.1s ease;
  }
  .roll img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
  }
  .roll:active {
    transform: scale(0.95);
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
    font-weight: 600;
  }

  .menu {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    background: var(--panel-solid);
    border: 1px solid var(--panel-border-strong);
    border-radius: 8px;
    box-shadow: var(--shadow);
    min-width: 220px;
    z-index: 50;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    pointer-events: auto;
  }

  .menu-item {
    display: block;
    min-height: 44px;
    padding: 12px 16px;
    box-sizing: border-box;
    text-decoration: none;
    color: var(--text);
    font-size: 0.9rem;
    font-weight: 500;
    background: none;
    border: none;
    text-align: left;
    cursor: pointer;
    width: 100%;
  }
  .menu-item:hover {
    background: var(--accent-soft);
  }
  .logout-btn {
    color: var(--danger);
    border-top: 1px solid var(--panel-border);
  }
</style>
