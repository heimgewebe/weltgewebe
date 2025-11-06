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

  export function focus() {
    rootEl?.focus();
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
  role="dialog"
  aria-modal={open ? "true" : undefined}
  tabindex={open ? 0 : -1}
  inert={!open ? true : undefined}
  {...$$restProps}
>
  {#if title}<h3 id={headingId}>{title}</h3>{/if}
  <slot />
  <slot name="footer" />
  <slot name="overlays" />
</div>

