<script lang="ts">
  export let data: unknown;
</script>

{#if false}{data}{/if}

<div style="padding: 2rem; font-family: sans-serif; max-width: 600px; margin: 0 auto;">
  <h1>Weltgewebe Dev Root</h1>
  <p>Der Dev-Server läuft erfolgreich.</p>

  <p>
    <a
      href="/map"
      style="display: inline-block; background: #0070f3; color: white; padding: 1rem 2rem; text-decoration: none; border-radius: 4px; font-weight: bold;"
    >
      Karte öffnen (/map)
    </a>
  </p>

  <div style="margin-top: 2rem; padding: 1rem; background: #f5f5f5; border-radius: 4px; color: #666; font-size: 0.9em;">
    <p style="margin: 0 0 0.5rem 0;"><strong>Warum sehe ich das?</strong></p>
    <p style="margin: 0;">
      In Production wird automatisch nach <code>/map</code> weitergeleitet.
      Im Dev-Modus zeigen wir diese Seite, um Probleme mit automatischen Redirects in Codespaces oder Safari zu vermeiden.
    </p>
  </div>
</div>
