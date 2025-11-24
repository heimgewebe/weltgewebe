<script lang="ts">
  type TabId = 'webrat' | 'naehstuebchen';

  export let open = true;
  let tab: TabId = 'webrat';
  let webratButton: HTMLButtonElement | null = null;
  let naehstuebchenButton: HTMLButtonElement | null = null;

  const orderedTabs: TabId[] = ['webrat', 'naehstuebchen'];

  function select(next: TabId, focus = false) {
    tab = next;
    if (focus) {
      (next === 'webrat' ? webratButton : naehstuebchenButton)?.focus();
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    const { key } = event;
    if (key === 'ArrowLeft' || key === 'ArrowRight' || key === 'Home' || key === 'End') {
      event.preventDefault();
      const currentIndex = orderedTabs.indexOf(tab);
      if (key === 'Home') {
        select(orderedTabs[0], true);
        return;
      }

      if (key === 'End') {
        select(orderedTabs[orderedTabs.length - 1], true);
        return;
      }

      const delta = key === 'ArrowRight' ? 1 : -1;
      const nextIndex = (currentIndex + delta + orderedTabs.length) % orderedTabs.length;
      select(orderedTabs[nextIndex], true);
    }
  }
</script>

{#if open}
<aside class="panel drawer drawer-left" aria-label="Primärer Bereichs-Drawer">
  <div
    class="row"
    style="gap:.5rem"
    role="tablist"
    aria-label="Bereich auswählen"
    aria-orientation="horizontal"
    on:keydown={handleKeydown}
  >
    <button
      class="btn"
      id="drawer-tab-webrat"
      role="tab"
      aria-selected={tab === 'webrat'}
      aria-controls="drawer-panel-webrat"
      type="button"
      tabindex={tab === 'webrat' ? 0 : -1}
      bind:this={webratButton}
      on:click={() => select('webrat')}
    >
      Webrat
    </button>
    <button
      class="btn"
      id="drawer-tab-naehstuebchen"
      role="tab"
      aria-selected={tab === 'naehstuebchen'}
      aria-controls="drawer-panel-naehstuebchen"
      type="button"
      tabindex={tab === 'naehstuebchen' ? 0 : -1}
      bind:this={naehstuebchenButton}
      on:click={() => select('naehstuebchen')}
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

<style>
  .drawer {
    position: absolute;
    z-index: 2;
    left: 50%;
    transform: translateX(-50%);
    bottom: 12rem;
    width: min(22rem, calc(100% - 1.5rem));
    max-height: min(45vh, 22rem);
    overflow: auto;
  }

  .drawer :global(p) {
    margin: 0;
  }

  .drawer [role="tab"] {
    outline: none;
  }

  .drawer [role="tab"]:focus-visible {
    outline: 2px solid rgba(112, 184, 255, 0.9);
    outline-offset: 2px;
  }

  @media (min-width: 48rem) {
    .drawer {
      top: clamp(0.75rem, 2vw, 1.5rem);
      bottom: clamp(3.5rem, 12vh, 4.75rem);
      left: clamp(1rem, 2vw, 1.5rem);
      transform: none;
      width: min(20rem, 28vw);
      max-height: none;
    }
  }
</style>
