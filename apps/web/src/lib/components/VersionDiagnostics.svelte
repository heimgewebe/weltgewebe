<script lang="ts">
  import { onMount } from 'svelte';

  interface VersionData {
    version: string;
    build?: string;
    built_at?: string;
    commit?: string;
    release?: string;
  }

  let versionData: VersionData | null = null;
  let loading = true;
  let error = false;

  onMount(async () => {
    try {
      const res = await fetch('/_app/version.json', { cache: 'no-store' });
      if (!res.ok) {
        throw new Error('Failed to fetch version data');
      }
      versionData = await res.json();
    } catch (err) {
      error = true;
    } finally {
      loading = false;
    }
  });

  $: displayText = (() => {
    if (loading) return 'Wird geladen...';
    if (error || !versionData) return 'Version unbekannt';

    const buildId = versionData.version || versionData.build || versionData.commit;
    const release = versionData.release;

    if (release && buildId) {
      return `Release ${release} · Build ${buildId}`;
    } else if (buildId) {
      return `Build ${buildId}`;
    } else {
      return 'Version unbekannt';
    }
  })();
</script>

<div class="version-diagnostics">
  <span class="label">Versionsdiagnose:</span>
  <span class="value" data-testid="version-text">{displayText}</span>
  {#if versionData?.built_at}
    <span class="timestamp" data-testid="version-date">
      (gebaut am {new Intl.DateTimeFormat('de-DE', { timeZone: 'UTC', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(versionData.built_at))} UTC)
    </span>
  {/if}
</div>

<style>
  .version-diagnostics {
    font-size: 0.85rem;
    color: var(--muted);
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }
  .label {
    font-weight: 500;
  }
  .value {
    font-family: monospace;
  }
  .timestamp {
    font-size: 0.75rem;
    opacity: 0.8;
  }
</style>
