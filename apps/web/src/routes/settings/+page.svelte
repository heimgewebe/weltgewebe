<script lang="ts">
  import VersionDiagnostics from '$lib/components/VersionDiagnostics.svelte';
</script>

<div class="container">
  <h1>Einstellungen</h1>
  <p class="intro">Hier kannst du deine Privatsphäre und dein Konto verwalten.</p>

  <div class="card">
    <h2>Sichtbarkeit (Garnrolle)</h2>
    <p>
      Deine Garnrolle ist an deinem Wohnsitz verankert. Du kannst entscheiden, wie genau dieser Ort öffentlich angezeigt wird.
    </p>

    <div class="setting-row disabled">
      <label for="radius">Ungenauigkeitsradius</label>
      <input type="range" id="radius" min="0" max="1000" value="0" disabled />
      <span>0m (exakt)</span>
    </div>



    <p class="coming-soon">🚧 Diese Einstellungen werden bald verfügbar sein.</p>
  </div>

  <div class="card diagnostics-card">
    <VersionDiagnostics />
  </div>
</div>

<style>
  .container { max-width: 600px; margin: 40px auto; padding: 0 20px; color: var(--text); }
  h1 { font-size: 2rem; margin-bottom: 1rem; }
  .intro { margin-bottom: 2rem; opacity: 0.8; }
  .card { background: var(--panel, #141a21); padding: 24px; border-radius: 12px; border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.06)); }
  h2 { font-size: 1.25rem; margin-bottom: 1rem; }
  .setting-row { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; opacity: 0.6; }
  .disabled { pointer-events: none; }
  .coming-soon { margin-top: 1rem; font-weight: bold; color: var(--accent); }
  .diagnostics-card { margin-top: 24px; padding: 16px 24px; }
</style>
