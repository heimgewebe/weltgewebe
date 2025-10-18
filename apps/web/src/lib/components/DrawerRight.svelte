<script lang="ts">
  export let open = true;
  // UI-State nur im Frontend; keine Persistenz
  let distance = 3;
  const filters = {
    knotentypen: {
      strukturknoten: true,
      faeden: false
    },
    bedarf: {
      bohrmaschine: false,
      schlafplatz: false,
      kinderspass: false,
      essen: false
    }
  };
</script>

{#if open}
<aside
  class="panel drawer drawer-right"
  aria-label="Filter- und Such-Drawer (inaktiv)"
  aria-describedby="filters-disabled-note"
>
  <strong>Suche</strong>
  <label class="col">
    <span class="ghost">Stichwort oder Adresse</span>
    <input type="search" placeholder="z. B. Reparatur" disabled />
  </label>
  <div class="divider"></div>
  <strong>Filter (stummgeschaltet)</strong>
  <div class="divider"></div>
  <div class="col">
    <label class="row"><input type="checkbox" bind:checked={filters.knotentypen.strukturknoten} disabled> Strukturknoten</label>
    <label class="row"><input type="checkbox" bind:checked={filters.knotentypen.faeden} disabled> Fäden</label>
  </div>
  <div class="divider"></div>
  <strong>Bedarf</strong>
  <div class="col">
    <label class="row"><input type="checkbox" bind:checked={filters.bedarf.bohrmaschine} disabled> Bohrmaschine</label>
    <label class="row"><input type="checkbox" bind:checked={filters.bedarf.schlafplatz} disabled> Schlafplatz</label>
    <label class="row"><input type="checkbox" bind:checked={filters.bedarf.kinderspass} disabled> Kinderspaß</label>
    <label class="row"><input type="checkbox" bind:checked={filters.bedarf.essen} disabled> Essen</label>
  </div>
  <div class="divider"></div>
  <label class="col">
    <span>Distanz (km) – UI only</span>
    <input type="range" min="1" max="15" bind:value={distance} disabled />
    <span class="ghost">{distance} km</span>
  </label>
  <p class="ghost" id="filters-disabled-note">Filter sind im Click-Dummy deaktiviert.</p>
</aside>
{/if}

<style>
  .drawer {
    position: absolute;
    z-index: 2;
    left: 50%;
    transform: translateX(-50%);
    bottom: 1rem;
    width: min(22rem, calc(100% - 1.5rem));
    max-height: min(50vh, 24rem);
    overflow: auto;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .drawer :global(label) {
    gap: 0.5rem;
  }

  .drawer input[type="search"],
  .drawer input[type="range"] {
    width: 100%;
    background: #101821;
    border: 1px solid #263240;
    border-radius: 8px;
    padding: 0.45rem 0.6rem;
    color: var(--fg);
  }

  .drawer input[disabled] {
    opacity: 0.6;
  }

  @media (min-width: 48rem) {
    .drawer {
      top: clamp(0.75rem, 2vw, 1.5rem);
      bottom: clamp(3.5rem, 12vh, 4.75rem);
      right: clamp(0.75rem, 2vw, 1.5rem);
      left: auto;
      transform: none;
      width: min(20rem, 28vw);
      max-height: none;
    }
  }
</style>
