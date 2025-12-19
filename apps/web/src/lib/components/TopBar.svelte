<script lang="ts">
  import { viewPanelOpen } from '$lib/stores/uiView';
  import Garnrolle from './Garnrolle.svelte';

  function toggleViewPanel() {
    $viewPanelOpen = !$viewPanelOpen;
  }
</script>

<style>
  .topbar{
    position:absolute; inset:0 0 auto 0; min-height:52px; z-index:30;
    display:flex; align-items:center; gap:8px; padding:0 12px;
    padding:env(safe-area-inset-top) 12px 0 12px;
    background: linear-gradient(180deg, rgba(0,0,0,0.55), rgba(0,0,0,0));
    color:var(--text);
    pointer-events: none;
  }
  .btn{
    pointer-events: auto;
    appearance:none; border:1px solid var(--panel-border); background:var(--panel); color:var(--text);
    height:34px; padding:0 12px; border-radius:10px; display:inline-flex; align-items:center; gap:8px;
    box-shadow: var(--shadow); cursor:pointer;
  }
  .btn:hover{ outline:1px solid var(--accent-soft); }
  .btn:focus-visible{
    outline:2px solid var(--accent);
    outline-offset:3px;
  }
  .btn:focus:not(:focus-visible){ outline:none; }
  .spacer{ flex:1; pointer-events: none; }
</style>

<div class="topbar" role="toolbar" aria-label="Navigation">
  <button
    class="btn"
    type="button"
    aria-label={$viewPanelOpen ? 'Ansicht schließen' : 'Ansicht öffnen'}
    aria-pressed={$viewPanelOpen}
    aria-expanded={$viewPanelOpen}
    on:click={toggleViewPanel}
  >
    👁️ Ansicht
  </button>

  <div class="spacer"></div>
  <div style="pointer-events: auto"><Garnrolle /></div>
</div>
