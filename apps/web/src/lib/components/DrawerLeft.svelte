<script lang="ts">
  export let open = true;
  let tab: 'webrat' | 'naehstuebchen' = 'webrat';
</script>

{#if open}
<aside
  class="panel"
  style="position:absolute; left:.75rem; top:4.5rem; bottom:4.5rem; width:320px; overflow:auto"
  aria-label="Primärer Bereichs-Drawer"
>
  <div class="row" style="gap:.5rem" role="tablist" aria-label="Bereich auswählen">
    <button
      class="btn"
      id="drawer-tab-webrat"
      role="tab"
      aria-selected={tab === 'webrat'}
      aria-controls="drawer-panel-webrat"
      on:click={() => (tab = 'webrat')}
    >
      Webrat
    </button>
    <button
      class="btn"
      id="drawer-tab-naehstuebchen"
      role="tab"
      aria-selected={tab === 'naehstuebchen'}
      aria-controls="drawer-panel-naehstuebchen"
      on:click={() => (tab = 'naehstuebchen')}
    >
      Nähstübchen
    </button>
  </div>
  <div class="divider"></div>
  {#if tab === 'webrat'}
    <div id="drawer-panel-webrat" role="tabpanel" aria-labelledby="drawer-tab-webrat">
      <p>Platzhalter – „coming soon“ (Diskussionen/Abstimmungen)</p>
    </div>
  {:else}
    <div id="drawer-panel-naehstuebchen" role="tabpanel" aria-labelledby="drawer-tab-naehstuebchen">
      <p>Platzhalter – „coming soon“ (Community-Werkzeuge)</p>
    </div>
  {/if}
</aside>
{/if}
