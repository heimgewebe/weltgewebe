<script lang="ts">
  import { updateStore } from '$lib/stores/updateStore';
  import { dev } from '$app/environment';

  function reload() {
    if (dev) {
      console.debug("[update-reload-click]");
    }
    window.location.reload();
  }
</script>

{#if $updateStore}
  <div class="update-banner" role="alert" aria-live="assertive">
    <div class="content">
      <span class="message">Eine neue Version ist verfügbar.</span>
      <button class="reload-btn" on:click={reload} type="button">Neu laden</button>
    </div>
  </div>
{/if}

<style>
  .update-banner {
    position: fixed;
    top: var(--spacing-4, 16px);
    left: 50%;
    transform: translateX(-50%);
    background-color: transparent;
    pointer-events: none; /* Let clicks pass through the wrapper bounding box */
    z-index: 9999;
    display: flex;
    justify-content: center;
    width: 100%;
    animation: slideDown 0.3s ease-out;
  }

  .content {
    display: flex;
    align-items: center;
    gap: var(--spacing-3, 12px);
    background-color: var(--surface-raised, #333);
    color: var(--text-on-surface, #fff);
    padding: var(--spacing-2, 8px) var(--spacing-4, 16px);
    border-radius: var(--radius-md, 8px);
    box-shadow: var(--shadow-md, 0 4px 6px rgba(0,0,0,0.1));
    pointer-events: auto; /* Reactivate clicks strictly for the banner content */
  }

  .message {
    font-size: 0.9rem;
    font-weight: 500;
  }

  .reload-btn {
    background-color: var(--primary, #007bff);
    color: white;
    border: none;
    padding: 6px 12px;
    border-radius: var(--radius-sm, 4px);
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 600;
    transition: background-color 0.2s;
  }

  .reload-btn:hover {
    background-color: var(--primary-hover, #0056b3);
  }

  @keyframes slideDown {
    from {
      opacity: 0;
      transform: translate(-50%, -20px);
    }
    to {
      opacity: 1;
      transform: translate(-50%, 0);
    }
  }
</style>
