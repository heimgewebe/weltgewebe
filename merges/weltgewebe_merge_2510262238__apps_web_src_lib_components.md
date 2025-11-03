### 📄 apps/web/src/lib/components/AppShell.svelte

**Größe:** 2 KB | **md5:** `e14cf8f1ddf8c953d273dc988768a07e`

```svelte
<script lang="ts">
  export let title = "Weltgewebe – Click-Dummy";
  export let timeCursor: string = "T-0";
</script>

<div class="app-shell">
  <header class="app-bar panel" aria-label="Navigation und Status">
    <div class="brand">
      <div class="brand-main">
        <strong>{title}</strong>
        <span class="badge">Gate A</span>
      </div>
      <p class="brand-sub ghost">Frontend-only Prototype · UX vor Code</p>
    </div>
    <div class="header-actions">
      <slot name="gewebekonto" />
      <slot name="topright" />
    </div>
  </header>
  <main class="app-main">
    <slot />
  </main>
  <footer class="app-footer panel" aria-label="Zeitachse (Attrappe)">
    <div>Zeitachse: Cursor <span class="badge">{timeCursor}</span></div>
    <div class="ghost">Replay deaktiviert · Gate B/C folgen</div>
  </footer>
</div>

<style>
  .app-shell {
    min-height: 100vh;
    display: grid;
    grid-template-rows: auto 1fr auto;
    gap: 0.75rem;
    padding: 0.75rem;
    box-sizing: border-box;
  }

  .app-bar {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .brand {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .brand-main {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .brand-sub {
    margin: 0;
  }

  .header-actions {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .header-actions :global(.btn:focus-visible),
  .header-actions :global(button:focus-visible),
  .header-actions :global(a:focus-visible) {
    outline: 2px solid rgba(112, 184, 255, 0.9);
    outline-offset: 2px;
    border-radius: 0.5rem;
  }

  .app-main {
    position: relative;
    overflow: hidden;
    border-radius: 18px;
  }

  .app-footer {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  @media (min-width: 42rem) {
    .app-bar {
      flex-direction: row;
      align-items: center;
      justify-content: space-between;
    }

    .header-actions {
      flex-direction: row;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
    }

    .app-footer {
      flex-direction: row;
      align-items: center;
      justify-content: space-between;
    }
  }
</style>
```

### 📄 apps/web/src/lib/components/Drawer.svelte

**Größe:** 3 KB | **md5:** `8f7f125feb0ee4383ac90c07627d16f5`

```svelte
<script lang="ts">
  import { createEventDispatcher, onMount, tick } from 'svelte';

  export let title = '';
  export let open = false;
  export let side: 'left' | 'right' | 'top' = 'left';
  export let id: string | undefined;

  const dispatch = createEventDispatcher<{ open: void; close: void }>();

  let headingId: string | undefined;
  let drawerId: string;
  $: drawerId = id ?? `${side}-drawer`;
  $: headingId = title ? `${drawerId}-title` : undefined;

  let rootEl: HTMLDivElement | null = null;
  let openerEl: HTMLElement | null = null;
  export function setOpener(el: HTMLElement | null) {
    openerEl = el;
  }

  function focusFirstInside() {
    if (!rootEl) return;
    const focusables = Array.from(
      rootEl.querySelectorAll<HTMLElement>(
        'button:not([tabindex="-1"]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )
    ).filter((element) => !element.hasAttribute('disabled'));

    (focusables[0] ?? rootEl).focus();
  }

  async function handleOpen() {
    await tick();
    focusFirstInside();
    dispatch('open');
  }

  async function handleClose() {
    await tick();
    openerEl?.focus();
    dispatch('close');
  }

  let hasMounted = false;
  onMount(() => {
    hasMounted = true;
  });

  let previousOpen = open;
  $: if (hasMounted && open !== previousOpen) {
    if (open) {
      handleOpen();
    } else {
      handleClose();
    }
    previousOpen = open;
  }
</script>

<style>
  .drawer{
    position:absolute; z-index:26; padding:var(--drawer-gap); color:var(--text);
    background:var(--panel); border:1px solid var(--panel-border); border-radius: var(--radius);
    box-shadow: var(--shadow);
    transform: translateY(calc(-1 * var(--drawer-slide-offset)));
    opacity:0;
    pointer-events:none;
    transition:.18s ease;
    overscroll-behavior: contain;
  }
  .drawer.open{ transform:none; opacity:1; pointer-events:auto; }
  .left{
    left:var(--drawer-gap);
    top:calc(var(--toolbar-offset) + env(safe-area-inset-top));
    bottom:calc(var(--toolbar-offset) + env(safe-area-inset-bottom));
    width:var(--drawer-width);
    border-radius: var(--radius);
  }
  .right{
    right:var(--drawer-gap);
    top:calc(var(--toolbar-offset) + env(safe-area-inset-top));
    bottom:calc(var(--toolbar-offset) + env(safe-area-inset-bottom));
    width:var(--drawer-width);
  }
  .top{
    left:50%;
    transform:translate(-50%, calc(-1 * var(--drawer-slide-offset)));
    top:calc(var(--toolbar-offset) + env(safe-area-inset-top));
    width:min(860px, calc(100vw - (2 * var(--drawer-gap))));
  }
  .top.open{ transform:translate(-50%,0); }
  h3{ margin:0 0 8px 0; font-size:14px; color:var(--muted); letter-spacing:.2px; }
  .section{ margin-bottom:12px; padding:10px; border:1px solid var(--panel-border); border-radius:10px; background:rgba(255,255,255,0.02); }
  @media (prefers-reduced-motion: reduce){
    .drawer{ transition:none; }
  }
</style>

<div
  bind:this={rootEl}
  id={drawerId}
  class="drawer"
  class:open={open}
  class:left={side === 'left'}
  class:right={side === 'right'}
  class:top={side === 'top'}
  aria-hidden={!open}
  aria-labelledby={headingId}
  tabindex="-1"
  role="complementary"
  inert={!open ? true : undefined}
  {...$$restProps}
>
  {#if title}<h3 id={headingId}>{title}</h3>{/if}
  <slot />
  <slot name="footer" />
  <slot name="overlays" />
</div>
```

### 📄 apps/web/src/lib/components/DrawerLeft.svelte

**Größe:** 3 KB | **md5:** `6ae20720a86d772bc2ad352b6e991833`

```svelte
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
      left: clamp(0.75rem, 2vw, 1.5rem);
      transform: none;
      width: min(20rem, 28vw);
      max-height: none;
    }
  }
</style>
```

### 📄 apps/web/src/lib/components/DrawerRight.svelte

**Größe:** 3 KB | **md5:** `c2df462c5482b6b2bf4769f21b32a08f`

```svelte
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
```

### 📄 apps/web/src/lib/components/Garnrolle.svelte

**Größe:** 1 KB | **md5:** `598a242724e118a4888305dc6a49eeed`

```svelte
<script lang="ts">
  export let label = 'Mein Konto';
  export let tooltip = 'Garnrolle – Konto';
</script>

<style>
  .wrap{ position:relative; }
  .roll{
    width:34px; height:34px; border-radius:50%;
    background: radial-gradient(circle at 30% 30%, #6aa6ff 0%, #2c6de0 60%, #1b3f7a 100%);
    border:1px solid rgba(255,255,255,0.12);
    box-shadow: var(--shadow);
    display:grid; place-items:center; cursor:pointer;
  }
  .hole{ width:10px; height:10px; border-radius:50%; background:#0f1a2f; box-shadow: inset 0 0 8px rgba(0,0,0,.6); }
  .tip{
    position:absolute; right:0; transform:translateY(calc(-100% - 8px));
    background:var(--panel); border:1px solid var(--panel-border); color:var(--text);
    padding:6px 8px; font-size:12px; border-radius:8px; white-space:nowrap;
    opacity:0; pointer-events:none; transition:.15s ease;
  }
  .wrap:hover .tip{ opacity:1; }
</style>

<div class="wrap" aria-label={label}>
  <div class="roll" title={tooltip}><div class="hole" /></div>
  <div class="tip">{tooltip}</div>
</div>
```

### 📄 apps/web/src/lib/components/GewebekontoWidget.svelte

**Größe:** 1 KB | **md5:** `30e5f7dbd97602fdd51c419f768a06bb`

```svelte
<script lang="ts">
  export let balance = "1 250 WE";
  export let trend: 'stable' | 'up' | 'down' = 'stable';
  export let note = "Attrappe · UX-Test";

  const trendLabels = {
    stable: 'gleichbleibend',
    up: 'steigend',
    down: 'sinkend'
  } as const;
</script>

<div class="gewebekonto panel" role="group" aria-label="Gewebekonto-Widget (Attrappe)">
  <div class="meta row">
    <span class="badge">Gewebekonto</span>
    <span class="ghost">Status: {trendLabels[trend]}</span>
  </div>
  <div class="balance" aria-live="polite">
    <strong>{balance}</strong>
  </div>
  <p class="note ghost">{note}</p>
  <div class="actions row" aria-hidden="true">
    <button class="btn" type="button" disabled>Einzahlen</button>
    <button class="btn" type="button" disabled>Auszahlen</button>
  </div>
</div>

<style>
  .gewebekonto {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    min-width: 14rem;
  }

  .meta {
    justify-content: space-between;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .balance {
    font-size: 1.25rem;
  }

  .note {
    margin: 0;
  }

  .actions {
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  @media (max-width: 40rem) {
    .gewebekonto {
      width: 100%;
    }
  }
</style>
```

### 📄 apps/web/src/lib/components/Legend.svelte

**Größe:** 2 KB | **md5:** `9cc8e254463f5321fb576725d548c346`

```svelte
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
```

### 📄 apps/web/src/lib/components/TimelineDock.svelte

**Größe:** 687 B | **md5:** `6cfaa4f9be468994236a0a6e14e629dd`

```svelte
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
```

### 📄 apps/web/src/lib/components/TopBar.svelte

**Größe:** 2 KB | **md5:** `6891014f2bb2c82ab7637bd0935b65ea`

```svelte
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import Garnrolle from './Garnrolle.svelte';
  export let onToggleLeft: () => void;
  export let onToggleRight: () => void;
  export let onToggleTop: () => void;
  export let leftOpen = false;
  export let rightOpen = false;
  export let topOpen = false;

  const dispatch = createEventDispatcher<{
    openers: {
      left: HTMLButtonElement | null;
      right: HTMLButtonElement | null;
      top: HTMLButtonElement | null;
    };
  }>();

  let btnLeft: HTMLButtonElement | null = null;
  let btnRight: HTMLButtonElement | null = null;
  let btnTop: HTMLButtonElement | null = null;

  onMount(() => {
    dispatch('openers', { left: btnLeft, right: btnRight, top: btnTop });
  });
</script>

<style>
  .topbar{
    position:absolute; inset:0 0 auto 0; min-height:52px; z-index:30;
    display:flex; align-items:center; gap:8px; padding:0 12px;
    padding:env(safe-area-inset-top) 12px 0 12px;
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
  <button
    class="btn"
    type="button"
    aria-pressed={leftOpen}
    aria-expanded={leftOpen}
    aria-controls="left-stack"
    bind:this={btnLeft}
    on:click={onToggleLeft}
  >
    ☰ Webrat/Nähstübchen
  </button>
  <button
    class="btn"
    type="button"
    aria-pressed={rightOpen}
    aria-expanded={rightOpen}
    aria-controls="filter-drawer"
    bind:this={btnRight}
    on:click={onToggleRight}
  >
    🔎 Filter
  </button>
  <button
    class="btn"
    type="button"
    aria-pressed={topOpen}
    aria-expanded={topOpen}
    aria-controls="account-drawer"
    bind:this={btnTop}
    on:click={onToggleTop}
  >
    🧶 Gewebekonto
  </button>
  <div class="spacer"></div>
  <Garnrolle />
</div>
```

