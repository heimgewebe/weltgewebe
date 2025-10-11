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
  class="panel"
  style="position:absolute; right:.75rem; top:4.5rem; bottom:4.5rem; width:320px; overflow:auto"
  aria-label="Filter-Drawer (inaktiv)"
>
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
</aside>
{/if}
