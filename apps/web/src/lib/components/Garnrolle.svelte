<script lang="ts">
  import { ICONS, MARKER_SIZES } from "$lib/ui/icons";
  import { authStore } from "$lib/auth/store";
  export let label = "Meine Garnrolle einrichten";
</script>

<div class="garnrolle-container wrap">
  {#if $authStore.authenticated}
    <a
      class="roll wrap-btn"
      href="/settings#meine-garnrolle"
      aria-label={label}
      title={label}
      style="width: {MARKER_SIZES.account}px; height: {MARKER_SIZES.account}px;"
    >
      <img src={ICONS.garnrolle} alt="" />
    </a>
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
    margin: 0;
    color: inherit;
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

  .roll:focus-visible,
  .login-entry:focus-visible {
    outline: 2px solid var(--accent);
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
    font-weight: 600;
  }
</style>
