<script lang="ts">
  export let title = "Weltgewebe – Click-Dummy";
  export let timeCursor: string = "T-0";
</script>

<div class="col" style="height:100vh">
  <header class="row panel" style="justify-content:space-between">
    <div class="row" style="gap:.5rem">
      <strong>{title}</strong>
      <span class="badge">Gate A</span>
      <span class="ghost">Frontend-only</span>
    </div>
    <div class="row" style="gap:.5rem">
      <slot name="topright" />
    </div>
  </header>
  <div style="flex:1; position:relative">
    <slot />
  </div>
  <footer class="panel row" style="justify-content:space-between">
    <div>Zeitachse (Stub): Cursor <span class="badge">{timeCursor}</span></div>
    <div class="ghost">Replay deaktiviert · Gate B/C später</div>
  </footer>
</div>
