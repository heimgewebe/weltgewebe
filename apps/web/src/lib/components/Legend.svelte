<script lang="ts">
  let open = false;
</script>

<div class="panel" style="position:absolute; right:.75rem; bottom:4.5rem; width:280px">
  <div class="row" style="justify-content:space-between">
    <strong>Legende</strong>
    <button
      class="btn"
      on:click={() => (open = !open)}
      aria-expanded={open}
      aria-controls="legend-panel"
    >
      {open ? "Schließen" : "Öffnen"}
    </button>
  </div>
  {#if open}
    <div class="divider"></div>
    <div class="col" id="legend-panel">
      <div><span class="legend-dot dot-blue"></span>Blau = Zentrum/Meta</div>
      <div><span class="legend-dot dot-gray"></span>Grau = Grundlagen</div>
      <div><span class="legend-dot dot-yellow"></span>Gelb = Prozesse</div>
      <div><span class="legend-dot dot-red"></span>Rot = Hindernisse</div>
      <div><span class="legend-dot dot-green"></span>Grün = Ziele</div>
      <div><span class="legend-dot dot-violet"></span>Violett = Ebenen</div>
    </div>
    <div class="divider"></div>
    <em class="ghost">Essenz: „Karte sichtbar, aber dumm.“</em>
  {/if}
</div>
