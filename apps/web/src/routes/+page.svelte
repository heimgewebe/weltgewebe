<script lang="ts">
  // SvelteKit page data stub – korrekte Signatur,
  // auch wenn das Feld aktuell ungenutzt ist.
  export let data: unknown;
</script>

{#if false}
  <!-- verhindert "unused variable"-Warnungen -->
  {data}
{/if}

<h1 style="padding:2rem">✅ SvelteKit render ok.</h1>
<p style="padding:2rem">Wenn du das siehst, läuft der Dev-Server.
Ist die Map später trotzdem schwarz, liegt es an der Seite/Map-Konfiguration.</p>
