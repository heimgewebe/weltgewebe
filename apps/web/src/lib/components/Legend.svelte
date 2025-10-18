<script lang="ts">
  let open = false;
</script>

<div class="panel legend">
  <div class="legend-header row">
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

<style>
  .legend {
    position: absolute;
    z-index: 2;
    right: clamp(0.75rem, 3vw, 1.5rem);
    top: clamp(0.75rem, 3vw, 1.5rem);
    width: min(18rem, calc(100% - 1.5rem));
  }

  .legend-header {
    justify-content: space-between;
  }

  .legend :global(.col) {
    gap: 0.35rem;
  }

  @media (max-width: 40rem) {
    .legend {
      left: clamp(0.75rem, 3vw, 1.5rem);
      width: auto;
    }
  }

  @media (min-width: 48rem) {
    .legend {
      bottom: clamp(3.5rem, 12vh, 4.75rem);
      top: auto;
    }
  }
</style>
