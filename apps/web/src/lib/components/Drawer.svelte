<script lang="ts">
  export let title = '';
  export let open = false;
  export let side: 'left'|'right'|'top' = 'left';
</script>

<style>
  .drawer{
    position:absolute; z-index:26; padding:12px; color:var(--text);
    background:var(--panel); border:1px solid var(--panel-border); border-radius: var(--radius);
    box-shadow: var(--shadow);
    transform: translateY(-20px); opacity:0; pointer-events:none; transition:.18s ease;
  }
  .drawer.open{ transform:none; opacity:1; pointer-events:auto; }
  .left{ left:12px; top:calc(64px + env(safe-area-inset-top)); bottom:calc(64px + env(safe-area-inset-bottom)); width:360px; border-radius: var(--radius); }
  .right{ right:12px; top:calc(64px + env(safe-area-inset-top)); bottom:calc(64px + env(safe-area-inset-bottom)); width:360px; }
  .top{ left:50%; transform:translate(-50%,-20px); top:calc(64px + env(safe-area-inset-top)); width:min(860px, calc(100vw - 32px)); }
  .top.open{ transform:translate(-50%,0); }
  h3{ margin:0 0 8px 0; font-size:14px; color:var(--muted); letter-spacing:.2px; }
  .section{ margin-bottom:12px; padding:10px; border:1px solid var(--panel-border); border-radius:10px; background:rgba(255,255,255,0.02); }
  @media (prefers-reduced-motion: reduce){
    .drawer{ transition:none; }
  }
</style>

<div class="drawer {side} {open ? 'open' : ''}">
  {#if title}<h3>{title}</h3>{/if}
  <slot />
  <slot name="footer" />
  <slot name="overlays" />
</div>

