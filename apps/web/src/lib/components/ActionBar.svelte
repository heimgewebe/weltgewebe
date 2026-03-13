<script lang="ts">
  import { systemState, contextPanelOpen, kompositionDraft, selection } from '$lib/stores/uiView';

  function onNewNode() {
    selection.set(null);
    systemState.set('komposition');
    kompositionDraft.set({ mode: 'new-knoten', source: 'action-bar' });
  }
</script>

<nav class="action-bar" class:panel-open={$contextPanelOpen} aria-label="Aktionsleiste">
  <button class="action-btn" aria-label="Suche">Suche</button>
  <button class="action-btn" on:click={onNewNode} aria-label="Neuer Knoten">Neuer Knoten</button>
  <button class="action-btn" aria-label="Mein Konto">Mein Konto</button>
  <button class="action-btn" aria-label="Filter">Filter</button>
</nav>

<style>
  .action-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 60px;
    background: var(--panel, #fff);
    border-top: 1px solid var(--panel-border, rgba(0,0,0,0.1));
    display: flex;
    justify-content: space-around;
    align-items: center;
    z-index: 40;
    padding: 0 1rem;
    box-shadow: var(--shadow, 0 -2px 10px rgba(0,0,0,0.05));
  }

  .action-btn {
    background: none;
    border: none;
    font-size: 0.9rem;
    color: var(--text, #333);
    cursor: pointer;
    padding: 0.5rem 1rem;
    border-radius: 8px;
  }

  .action-btn:hover {
    background: rgba(0,0,0,0.05);
  }

  /* Desktop: adjust layout slightly if needed */
  @media (min-width: 769px) {
    .action-bar.panel-open {
      right: 400px; /* leaves room for ContextPanel */
    }
  }
</style>
