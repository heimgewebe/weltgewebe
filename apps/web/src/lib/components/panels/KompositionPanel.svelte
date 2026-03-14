<script lang="ts">
  import { kompositionDraft } from '$lib/stores/uiView';
</script>

<div class="komposition-mode">
  {#if $kompositionDraft?.lngLat}
    <div class="state-set">
      <p><strong>Ort gesetzt:</strong> {$kompositionDraft.lngLat[1].toFixed(5)}, {$kompositionDraft.lngLat[0].toFixed(5)}</p>
      <p class="ghost">Du kannst den Ort ändern, indem du einen anderen Punkt auf der Karte lange drückst.</p>
      <!-- Future: Form for Node Type and Details goes here -->
    </div>
  {:else}
    <div class="state-pending">
      <p><strong>Ort ausstehend</strong></p>
      <p>Bitte wähle den Startpunkt für den neuen Knoten, indem du lange auf die Karte tippst (Longpress).</p>
    </div>
  {/if}
</div>

<style>
  .ghost {
    color: var(--ghost, #666);
  }
</style>
