<script lang="ts">
  import Garnrolle from './Garnrolle.svelte';
</script>

<style>
  .topbar{
    position:absolute; inset:0 0 auto 0; min-height:52px; z-index:41;
    display:flex; align-items:center; gap:8px; padding:0 12px;
    padding:env(safe-area-inset-top) 12px 0 12px;
    background: linear-gradient(180deg, rgba(0,0,0,0.55), rgba(0,0,0,0));
    color:var(--text);
    pointer-events: none;
  }

  .spacer{ flex:1; pointer-events: none; }
</style>

<div class="topbar" role="toolbar" aria-label="Navigation">
  <div class="spacer"></div>
  <div style="pointer-events: auto"><Garnrolle /></div>
</div>
