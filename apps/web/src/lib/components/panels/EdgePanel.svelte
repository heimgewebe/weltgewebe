<script lang="ts">
  import { selection } from '$lib/stores/uiView';
</script>

<div class="edge-mode">
  <h3>Faden: {$selection?.id}</h3>

  <div class="details">
    <p><strong>Ursprung:</strong> {$selection?.data?.source || 'Unbekannt'}</p>
    <p><strong>Ziel:</strong> {$selection?.data?.target || 'Unbekannt'}</p>
    <p><strong>Zeitlichkeit:</strong> ...</p>
  </div>
</div>
