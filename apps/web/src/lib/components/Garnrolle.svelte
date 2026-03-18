<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { ICONS, MARKER_SIZES } from '$lib/ui/icons';
  import { authStore } from '$lib/auth/store';
  import { browser } from '$app/environment';

  export let label = 'Kontoeinstellungen';

  const dispatch = createEventDispatcher();
  let menuOpen = false;

  function toggleMenu() {
    menuOpen = !menuOpen;
  }

  function closeMenu(event: MouseEvent) {
    if (!menuOpen) return;
    const target = event.target as HTMLElement;
    if (!target.closest('.garnrolle-container')) {
      menuOpen = false;
    }
  }

  async function logout() {
    if (!browser) return;
    await authStore.logout();
    menuOpen = false;
  }
</script>

<svelte:window on:click={closeMenu} />

<div class="garnrolle-container wrap">
  <button
    class="roll wrap-btn"
    aria-label={label}
    aria-expanded={menuOpen}
    on:click={toggleMenu}
    style="width: {MARKER_SIZES.account}px; height: {MARKER_SIZES.account}px;"
  >
    <img src={ICONS.garnrolle} alt={label} />
  </button>

  {#if menuOpen}
    <div class="menu">
      {#if $authStore.authenticated}
        <div class="menu-header">
          <span class="role-badge" class:admin={$authStore.role === 'admin'} class:weber={$authStore.role === 'weber'} class:gast={$authStore.role === 'gast'}>
            {$authStore.role}
          </span>
        </div>
        <button class="menu-item" on:click={() => { menuOpen = false; dispatch('requestZoomToOwnGarnrolle'); }}>Meine Garnrolle auf Karte zeigen</button>
        <a href="/settings" class="menu-item" on:click={() => menuOpen = false}>Einstellungen</a>
        <button class="menu-item logout-btn" on:click={logout}>Logout</button>
      {:else}
        <div class="menu-header">
          <span class="role-badge gast">gast</span>
        </div>
        <a href="/login" class="menu-item" on:click={() => menuOpen = false}>Login</a>
      {/if}
    </div>
  {/if}
</div>

<style>
  .wrap { position: relative; display: inline-block; }
  .wrap-btn {
    background: none;
    border: none;
    padding: 0;
    margin: 0;
    text-decoration: none;
    color: inherit;
    outline: none;
    appearance: none;
  }
  .wrap-btn:focus-visible { outline: 2px solid var(--primary); border-radius: 4px; }

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
  .roll:active { transform: scale(0.95); }

  .menu {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    background: var(--panel);
    border: 1px solid var(--panel-border);
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    min-width: 150px;
    z-index: 50;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    pointer-events: auto;
  }

  .menu-header {
    padding: 12px 16px 8px;
    border-bottom: 1px solid var(--panel-border);
    background: var(--bg);
  }

  .role-badge {
    padding: 0.1rem 0.5rem;
    border-radius: 99px;
    background: rgba(255, 255, 255, 0.05);
    text-transform: uppercase;
    font-weight: bold;
    font-size: 0.7rem;
    display: inline-block;
  }
  .role-badge.admin { background: var(--accent); color: var(--panel); }
  .role-badge.weber { background: #54e1a6; color: var(--panel); }
  .role-badge.gast { background: var(--muted); color: var(--bg); }

  .menu-item {
    display: block;
    padding: 12px 16px;
    text-decoration: none;
    color: var(--text);
    font-size: 0.9rem;
    font-weight: 500;
    background: none;
    border: none;
    text-align: left;
    cursor: pointer;
    width: 100%;
    transition: background 0.1s ease;
  }
  .menu-item:hover {
    background: rgba(255, 255, 255, 0.05);
  }

  .logout-btn {
    color: #ff6b6b;
    border-top: 1px solid var(--panel-border);
  }
  .logout-btn:hover {
    background: #ff6b6b;
    color: white;
  }
</style>
