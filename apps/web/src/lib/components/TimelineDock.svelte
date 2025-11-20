<script lang="ts">
  // Stub component
</script>

<style>
  .dock{
    position:absolute; left:0; right:0; bottom:0; min-height:56px; z-index:28;
    display:flex; align-items:center; gap:12px;
    padding:0 12px calc(env(safe-area-inset-bottom)) 12px;
    backdrop-filter: blur(6px);
    background: linear-gradient(0deg, rgba(0,0,0,0.55), rgba(0,0,0,0));
    color:var(--text);
  }
  .badge{ border:1px solid var(--panel-border); background:var(--panel); padding:6px 10px; border-radius:10px; }
  .spacer{ flex:1; }
</style>

<div class="dock">
  <div class="badge">⏱️ Timeline (Stub)</div>
  <div class="spacer"></div>
  <div style="opacity:.72; font-size:12px;">Tipp: [ = links · ] = rechts · Alt+G = Gewebekonto</div>
</div>
