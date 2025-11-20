<script lang="ts">
  import {
    swipe,
    type SwipeDirection,
    type SwipeMeta,
    type SwipeOptions,
    type SwipeRejectMeta
  } from '$lib/gestures';

  let threshold = 24;
  let angleRatio = 0.5;
  let velocityMin = 0.3;
  let lockAxis = true;
  let axisDeadzone = 6;
  let passiveMove = true;
  let allowMouse = true;

  let lastDirection: SwipeDirection | '—' = '—';
  let lastMeta: SwipeMeta | null = null;
  let lastReject: SwipeRejectMeta | null = null;
  let log: string[] = [];

  function addLog(message: string) {
    log = [message, ...log].slice(0, 6);
  }

  function handleSwipe(direction: SwipeDirection, meta: SwipeMeta) {
    lastDirection = direction;
    lastMeta = meta;
    lastReject = null;
    addLog(`${direction === 'left' ? '←' : '→'} dx=${meta.dx.toFixed(1)} v=${meta.v.toFixed(2)}`);
  }

  function handleReject(meta: SwipeRejectMeta) {
    lastDirection = '—';
    lastReject = meta;
    addLog(
      `× dx=${meta.dx.toFixed(1)} v=${meta.v.toFixed(2)} ` +
        `[h:${meta.horizontalEnough ? '✓' : '×'} l:${meta.longEnough ? '✓' : '×'} v:${
          meta.fastEnough ? '✓' : '×'
        }]`
    );
  }

  $: currentOptions = {
    threshold,
    angleRatio,
    velocityMin,
    lockAxis,
    axisDeadzone,
    passiveMove,
    allowMouse,
    onSwipe: handleSwipe,
    onReject: handleReject
  } satisfies SwipeOptions;
</script>

<svelte:head>
  <title>Swipe Debug Playground</title>
</svelte:head>

<div class="col" style="gap:1.5rem; padding:1.5rem; max-width:960px; margin:0 auto;">
  <header class="col">
    <h1>Swipe Playground</h1>
    <p class="ghost">
      Passe Schwellwerte an und teste horizontale Swipes (Touch/Pen oder Maus wenn aktiviert).
      Der aktive Bereich nutzt die globale <code>.swipeable</code>-Konfiguration.
    </p>
  </header>

  <section class="panel col">
    <h2>Parameter</h2>
    <div class="row">
      <label class="col" style="flex:1">
        <span>threshold: {threshold}px</span>
        <input type="range" min="8" max="64" step="1" bind:value={threshold} />
      </label>
      <label class="col" style="flex:1">
        <span>angleRatio: {angleRatio.toFixed(2)}</span>
        <input type="range" min="0.2" max="0.9" step="0.05" bind:value={angleRatio} />
      </label>
    </div>
    <div class="row">
      <label class="col" style="flex:1">
        <span>velocityMin: {velocityMin.toFixed(2)} px/ms</span>
        <input type="range" min="0.1" max="0.6" step="0.02" bind:value={velocityMin} />
      </label>
      <label class="col" style="flex:1">
        <span>axisDeadzone: {axisDeadzone}px</span>
        <input type="range" min="0" max="20" step="1" bind:value={axisDeadzone} />
      </label>
    </div>
    <div class="row" style="flex-wrap:wrap; gap:.75rem;">
      <label class="row" style="gap:.35rem;">
        <input type="checkbox" bind:checked={lockAxis} />
        <span>lockAxis</span>
      </label>
      <label class="row" style="gap:.35rem;">
        <input type="checkbox" bind:checked={passiveMove} />
        <span>passiveMove</span>
      </label>
      <label class="row" style="gap:.35rem;">
        <input type="checkbox" bind:checked={allowMouse} />
        <span>allowMouse</span>
      </label>
    </div>
  </section>

  <section class="panel col" style="gap:1rem;">
    <h2>Testfläche</h2>
    <div class="swipe-parent" style="max-width:100%;">
      <div
        class="swipeable panel"
        style="min-height:200px; display:flex; align-items:center; justify-content:center; text-align:center;"
        use:swipe={currentOptions}
      >
        <div>
          <p style="font-size:2rem; margin:0 0 .5rem;">{lastDirection}</p>
          <p class="ghost" style="margin:0;">
            Wische horizontal, um Richtung und Metadaten zu sehen. Vertikales Scrollen bleibt möglich.
          </p>
        </div>
      </div>
    </div>
    <div class="row" style="align-items:flex-start; gap:1rem;">
      <div class="col" style="flex:1;">
        <h3 class="ghost" style="margin:0;">Letzter Swipe</h3>
        {#if lastMeta}
          <code>dx={lastMeta.dx.toFixed(1)} dy={lastMeta.dy.toFixed(1)} v={lastMeta.v.toFixed(2)}</code>
        {:else}
          <span class="ghost">noch kein Swipe</span>
        {/if}
      </div>
      <div class="col" style="flex:1;">
        <h3 class="ghost" style="margin:0;">Letzte Ablehnung</h3>
        {#if lastReject}
          <code>
            dx={lastReject.dx.toFixed(1)} dy={lastReject.dy.toFixed(1)} v={lastReject.v.toFixed(2)}
            [h:{lastReject.horizontalEnough ? '✓' : '×'} l:{lastReject.longEnough ? '✓' : '×'} v:{
              lastReject.fastEnough ? '✓' : '×'
            }]
          </code>
        {:else}
          <span class="ghost">bisher keine Ablehnung</span>
        {/if}
      </div>
    </div>
  </section>

  <section class="panel col" style="gap:.75rem;">
    <h2>Log</h2>
    {#if log.length === 0}
      <span class="ghost">Noch keine Ereignisse</span>
    {:else}
      <ul style="margin:0; padding-left:1.2rem;">
        {#each log as entry, index (index)}
          <li><code>{entry}</code></li>
        {/each}
      </ul>
    {/if}
  </section>
</div>
