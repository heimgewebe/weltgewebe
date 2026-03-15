<script lang="ts">
  import { ICONS, MARKER_SIZES } from '$lib/ui/icons';

  export let label = 'Kontoeinstellungen';
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
  .wrap:focus-visible { outline: 2px solid var(--primary); border-radius: 4px; }
</style>

<a href="/settings" class="wrap" aria-label={label}>
  <div class="roll" style="width: {MARKER_SIZES.account}px; height: {MARKER_SIZES.account}px;">
    <img src={ICONS.garnrolle} alt={label} />
  </div>
</a>
