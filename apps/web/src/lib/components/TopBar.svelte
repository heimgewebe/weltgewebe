<script lang="ts">
  import { viewPanelOpen } from '$lib/stores/uiView';
  import Garnrolle from './Garnrolle.svelte';

  function toggleViewPanel() {
    $viewPanelOpen = !$viewPanelOpen;
  }
</script>

<style>
  .topbar{
    position:absolute; inset:0 0 auto 0; min-height:52px; z-index:41; /* Above ViewPanel (40) */
    display:flex; align-items:center; gap:8px; padding:0 12px;
    padding:env(safe-area-inset-top) 12px 0 12px;
    background: linear-gradient(180deg, rgba(0,0,0,0.55), rgba(0,0,0,0));
    color:var(--text);
    pointer-events: none;
  }

  .pill-btn {
    pointer-events: auto;
    appearance: none;
    border: 1px solid var(--panel-border);
    background: var(--panel);
    color: var(--text);
    height: 36px;
    padding: 0 16px;
    border-radius: 99px; /* Pill shape */
    display: inline-flex;
    align-items: center;
    gap: 8px;
    box-shadow: var(--shadow);
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.15s ease;
  }

  .pill-btn:hover {
    background: var(--bg);
    transform: translateY(1px);
  }

  .pill-btn[aria-pressed="true"] {
    background: var(--bg);
    border-color: var(--accent);
    color: var(--accent);
  }

  .pill-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .spacer{ flex:1; pointer-events: none; }
</style>

<div class="topbar" role="toolbar" aria-label="Navigation">
  <button
    class="pill-btn"
    type="button"
    aria-label={$viewPanelOpen ? 'Ansicht schließen' : 'Ansicht öffnen'}
    aria-pressed={$viewPanelOpen}
    aria-expanded={$viewPanelOpen}
    on:click={toggleViewPanel}
  >
    {#if $viewPanelOpen}
      <span>Ansicht ✕</span>
    {:else}
      <span>👁️ Ansicht ▾</span>
    {/if}
  </button>

  <div class="spacer"></div>
  <div style="pointer-events: auto"><Garnrolle /></div>
</div>
