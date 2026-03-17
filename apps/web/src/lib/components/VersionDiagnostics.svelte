<script lang="ts">
  import { onMount } from 'svelte';

  interface VersionData {
    version: string;
    build?: string;
    build_id?: string;
    built_at?: string;
    commit?: string;
    release?: string;
  }

  let versionData: VersionData | null = null;
  let loading = true;
  let error = false;
  let displayText = 'Wird geladen...';
  let builtAtText: string | null = null;

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

  $: {
    if (loading) {
      displayText = 'Wird geladen...';
      builtAtText = null;
    } else if (error || !versionData) {
      displayText = 'Version unbekannt';
      builtAtText = null;
    } else {
      // Prioritize explicit build id sources over generic git commit
      const buildId = versionData.build_id || versionData.version || versionData.build || versionData.commit;
      const release = versionData.release;

      if (release && buildId) {
        displayText = `Release ${release} · Build ${buildId}`;
      } else if (buildId) {
        displayText = `Build ${buildId}`;
      } else {
        displayText = 'Version unbekannt';
      }

      if (versionData.built_at) {
        const date = new Date(versionData.built_at);
        if (!isNaN(date.getTime())) {
          builtAtText = new Intl.DateTimeFormat('de-DE', {
            timeZone: 'UTC',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
          }).format(date);
        } else {
          builtAtText = null;
        }
      } else {
        builtAtText = null;
      }
    }
  }
</script>

<div class="version-diagnostics">
  <span class="label">Versionsdiagnose:</span>
  <span class="value" data-testid="version-text">{displayText}</span>
  {#if builtAtText}
    <span class="timestamp" data-testid="version-date">
      (gebaut am {builtAtText} UTC)
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
