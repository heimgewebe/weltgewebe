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
  let buildIdText: string | null = null;
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
      buildIdText = null;
      builtAtText = null;
    } else if (error || !versionData) {
      displayText = 'Version unbekannt';
      buildIdText = null;
      builtAtText = null;
    } else {
      // Prioritize canonical version
      const canonicalVersion = versionData.version || versionData.commit || versionData.build;
      const buildId = versionData.build_id;
      const release = versionData.release;

      if (release && canonicalVersion) {
        displayText = `Release ${release} · Version ${canonicalVersion}`;
      } else if (canonicalVersion) {
        displayText = `Version ${canonicalVersion}`;
      } else if (buildId) {
        displayText = `Build ${buildId}`;
      } else {
        displayText = 'Version unbekannt';
      }

      // Secondary diagnostic build context
      buildIdText = buildId && buildId !== canonicalVersion ? buildId : null;

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
  {#if buildIdText || builtAtText}
    <span class="meta" data-testid="version-meta">
      {#if buildIdText}(Build {buildIdText}){/if}
      {#if buildIdText && builtAtText} · {/if}
      {#if builtAtText}gebaut am {builtAtText} UTC{/if}
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
  .meta {
    font-size: 0.75rem;
    opacity: 0.8;
  }
</style>
