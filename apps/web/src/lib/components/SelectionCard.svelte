<script lang="ts">
  import { selection } from '$lib/stores/uiView';
  import { slide } from 'svelte/transition';

  function close() {
    $selection = null;
  }
</script>

<style>
  .selection-card {
    position: absolute;
    z-index: 35; /* Above map, below TopBar/ViewPanel */
    background: var(--panel);
    border: 1px solid var(--panel-border);
    box-shadow: var(--shadow);
    border-radius: var(--radius);
    padding: 16px;
    width: 300px;
    color: var(--text);
  }

  /* Desktop: Bottom Right or Floating */
  @media (min-width: 600px) {
    .selection-card {
      bottom: 80px; /* Above TimelineDock */
      right: 12px;
    }
  }

  /* Mobile: Bottom (above dock) */
  @media (max-width: 599px) {
    .selection-card {
      bottom: 80px; /* Above TimelineDock which is ~60px + spacing */
      left: 12px;
      right: 12px;
      width: auto;
    }
  }

  h3 {
    margin: 0 0 8px 0;
    font-size: 16px;
    font-weight: 600;
  }

  .content {
    margin-bottom: 12px;
    font-size: 14px;
    color: var(--muted);
  }

  .actions {
    display: flex;
    justify-content: flex-end;
  }

  button {
    background: transparent;
    border: 1px solid var(--panel-border);
    border-radius: 4px;
    padding: 4px 12px;
    cursor: pointer;
    color: var(--text);
    font-size: 13px;
  }
  button:hover {
    background: var(--bg);
  }
</style>

{#if $selection}
  <div class="selection-card" transition:slide={{ duration: 200, axis: 'y' }}>
    <div style="display: flex; justify-content: space-between; align-items: start;">
      <h3>
        {#if $selection.data && $selection.data.title}
          {$selection.data.title}
        {:else}
          Element {$selection.id}
        {/if}
      </h3>
      <button style="border:none; padding:0; margin-left:8px;" on:click={close} aria-label="Close">✕</button>
    </div>

    <div class="content">
      <p>Typ: {$selection.type}</p>
      {#if $selection.data}
        <p>{$selection.data.description || 'Kurzbeschreibung folgt (Stub)'}</p>
      {/if}
    </div>

    <div class="actions">
      <!-- Actions like "Details", "Edit" could go here -->
    </div>
  </div>
{/if}
