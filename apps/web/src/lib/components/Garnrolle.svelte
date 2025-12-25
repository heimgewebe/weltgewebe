<script lang="ts">
  import { ICONS, MARKER_SIZES } from '$lib/ui/icons';

  export let label = 'Mein Konto';
  export let tooltip = 'Garnrolle – Konto';
</script>

<style>
  .wrap{ position:relative; display:inline-block; text-decoration: none; color: inherit; }
  .roll{
    display:block; cursor:pointer;
    transition: transform 0.1s ease;
  }
  .roll img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
  }
  .roll:active { transform: scale(0.95); }
  .tip{
    position:absolute; right:0; transform:translateY(calc(-100% - 8px));
    background:var(--panel); border:1px solid var(--panel-border); color:var(--text);
    padding:6px 8px; font-size:12px; border-radius:8px; white-space:nowrap;
    opacity:0; pointer-events:none; transition:.15s ease;
  }
  .wrap:hover .tip{ opacity:1; }
  .wrap:focus-visible { outline: 2px solid var(--primary); border-radius: 4px; }
</style>

<a href="/settings" class="wrap" aria-label={label}>
  <div class="roll" title={tooltip} style="width: {MARKER_SIZES.account}px; height: {MARKER_SIZES.account}px;">
    <img src={ICONS.garnrolle} alt={label} />
  </div>
  <div class="tip">{tooltip}</div>
</a>
