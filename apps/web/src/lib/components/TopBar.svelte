<script lang="ts">
  import Garnrolle from './Garnrolle.svelte';
  export let onToggleLeft: () => void;
  export let onToggleRight: () => void;
  export let onToggleTop: () => void;
</script>

<style>
  .topbar{
    position:absolute; inset:0 0 auto 0; min-height:52px; z-index:30;
    display:flex; align-items:center; gap:8px; padding:0 12px;
    padding:calc(env(safe-area-inset-top)) 12px 0 12px;
    background: linear-gradient(180deg, rgba(0,0,0,0.55), rgba(0,0,0,0));
    color:var(--text);
  }
  .btn{
    appearance:none; border:1px solid var(--panel-border); background:var(--panel); color:var(--text);
    height:34px; padding:0 12px; border-radius:10px; display:inline-flex; align-items:center; gap:8px;
    box-shadow: var(--shadow); cursor:pointer;
  }
  .btn:hover{ outline:1px solid var(--accent-soft); }
  .spacer{ flex:1; }
</style>

<div class="topbar" role="toolbar" aria-label="Navigation">
  <button class="btn" on:click={onToggleLeft}>☰ Webrat/Nähstübchen</button>
  <button class="btn" on:click={onToggleRight}>🔎 Filter</button>
  <button class="btn" on:click={onToggleTop}>🧶 Gewebekonto</button>
  <div class="spacer"></div>
  <Garnrolle />
</div>

