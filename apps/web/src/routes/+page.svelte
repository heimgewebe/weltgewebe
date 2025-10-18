<script lang="ts">
  import { browser } from "$app/environment";
  import { onDestroy, onMount } from "svelte";
  import { derived } from "svelte/store";
  import { createBooleanToggle, createLoopingCountdown } from "$lib/stores";

  let mapHost: HTMLDivElement | null = null;
  let mapReady = false;
  let loading = false;
  let error: string | null = null;
  let map: import("maplibre-gl").Map | null = null;
  let mounted = false;

  const freezeDurationMs = 24 * 60 * 60 * 1000;
  const freezeTimer = createLoopingCountdown(freezeDurationMs);
  const freezeFormatted = derived(freezeTimer, formatDuration);

  const reportThread = createBooleanToggle();

  const governanceTooltip =
    "7 Tage Beratung + 7 Tage Einspruch – Governance-Matrix (7+7-Modell).";

  type MapLibreModule = typeof import("maplibre-gl");

  const pageTitle = "Weltgewebe · Home";
  const pageDescription =
    "Interaktive Übersicht des Webrats mit Karte, Archiv und Timeline.";

  function canInitialise(container: HTMLDivElement | null): container is HTMLDivElement {
    if (typeof window === "undefined") return false;
    if (!container || !container.isConnected) return false;
    const rect = container.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  async function enableMap() {
    if (!browser || loading || mapReady || !mounted) return;

    if (!canInitialise(mapHost)) {
      error = "Karte konnte nicht geladen werden.";
      return;
    }

    const container = mapHost;
    loading = true;
    error = null;

    try {
      const modulePromise = import("maplibre-gl");
      await import("maplibre-gl/dist/maplibre-gl.css");
      const mapModule = await modulePromise;

      const maplibregl = (mapModule as MapLibreModule & { default?: MapLibreModule }).default ??
        (mapModule as MapLibreModule);

      map = new maplibregl.Map({
        container,
        style: "https://demotiles.maplibre.org/style.json",
        center: [10.0, 53.55], // grob HH
        zoom: 10
      });
      map.scrollZoom.disable();

      const handleLoad = () => {
        loading = false;
        mapReady = true;
        map?.off("error", handleError);
      };

      const handleError = (event: { error?: unknown }) => {
        console.error(event?.error ?? event);
        error = "Karte konnte nicht geladen werden.";
        loading = false;
        mapReady = false;
        map?.off("load", handleLoad);
        map?.remove();
        map = null;
      };

      map.once("load", handleLoad);
      map.on("error", handleError);
    } catch (e) {
      error = "Karte konnte nicht geladen werden.";
      console.error(e);
      loading = false;
      mapReady = false;
      map?.remove();
      map = null;
    }
  }

  function formatDuration(ms: number) {
    const totalSeconds = Math.max(0, Math.floor(ms / 1000));
    const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, "0");
    const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, "0");
    const seconds = String(totalSeconds % 60).padStart(2, "0");
    return `${hours}:${minutes}:${seconds}`;
  }

  onMount(() => {
    mounted = true;
  });

  onDestroy(() => {
    map?.remove();
    map = null;
    mounted = false;
    mapReady = false;
    loading = false;
  });
</script>

<svelte:head>
  <title>{pageTitle}</title>
  <meta name="description" content={pageDescription} />
</svelte:head>

<div style="position:fixed;inset:0;">
  <!-- Map-Fläche -->
  <div
    bind:this={mapHost}
    role="application"
    aria-label="Interactive Map"
    style="position:absolute;inset:0;background:#eef"
  ></div>

  <!-- Kleiner Drawer-Stub -->
  <aside style="position:absolute;left:1rem;top:1rem;background:#fff;padding:.75rem .9rem;border-radius:.5rem;box-shadow:0 2px 8px #0001;">
    <strong>Webrat</strong> · <em>Nähstübchen</em>
    <div style="margin-top:.5rem;display:flex;flex-direction:column;gap:.35rem;">
      <button on:click={enableMap} disabled={mapReady || loading}>
        {mapReady ? "Karte aktiv" : (loading ? "Lade Karte…" : "Karte aktivieren")}
      </button>
      <a href="/archive/" style="font-size:.9rem;">Archiv ansehen</a>
      {#if error}<span role="alert" style="color:#b00;">{error}</span>{/if}
    </div>

    <hr style="margin:0.75rem 0;border:none;border-top:1px solid #eee;" />

    <section
      style="display:flex;flex-direction:column;gap:.45rem;font-size:.9rem;"
      aria-labelledby="ethik-moderation-heading"
    >
      <div style="display:flex;flex-direction:column;gap:.25rem;">
        <span id="ethik-moderation-heading" style="font-weight:600;">Ethik &amp; Moderation</span>
        <span style="color:#555;font-size:.85rem;">
          Radikale Transparenz: Moderationsspuren werden sichtbar gehalten, nichts verschwindet heimlich.
        </span>
      </div>

      <div style="display:flex;flex-direction:column;gap:.25rem;">
        <button
          type="button"
          on:click={reportThread.toggle}
          aria-expanded={$reportThread}
          aria-controls="report-thread-panel"
        >
          {$reportThread ? "Melden-Faden einklappen" : "Melden-Faden anzeigen"}
        </button>
        {#if $reportThread}
          <div
            id="report-thread-panel"
            style="padding:.5rem;border:1px solid #dde;border-radius:.4rem;background:#f7f9ff;display:flex;flex-direction:column;gap:.35rem;"
          >
            <strong style="font-size:.85rem;">Moderationsfaden (Demo)</strong>
            <ol style="padding-left:1.25rem;margin:0;font-size:.85rem;display:flex;flex-direction:column;gap:.25rem;">
              <li>Meldung landet im offenen Faden – alle Beteiligten sehen den Verlauf.</li>
              <li>24h Freeze kann ausgelöst werden, um Beweise zu sichern.</li>
              <li>Moderationsentscheid &amp; Governance-Notizen bleiben revisionssicher sichtbar.</li>
            </ol>
            <span style="font-size:.75rem;color:#555;">Attrappe zur UI-Visualisierung – keine echte Meldung.</span>
          </div>
        {/if}
      </div>

      <div
        style="display:flex;flex-direction:column;gap:.25rem;padding:.5rem;border:1px solid #f0c2c2;border-radius:.4rem;background:#fff5f5;"
      >
        <span style="font-weight:600;">24h Freeze (Attrappe)</span>
        <div style="display:flex;align-items:center;gap:.5rem;font-variant-numeric:tabular-nums;" aria-live="polite">
          <span style="padding:.2rem .45rem;border-radius:.25rem;background:#d33;color:#fff;font-size:1rem;">{$freezeFormatted}</span>
          <span style="font-size:.8rem;color:#a33;">Freeze-Timer für Beweissicherung (Demo-Modus)</span>
        </div>
      </div>

      <div
        style="display:flex;flex-direction:column;gap:.25rem;padding:.5rem;border:1px solid #d4e1ff;border-radius:.4rem;background:#f2f6ff;"
      >
        <span style="display:flex;align-items:center;gap:.4rem;">
          <span style="font-weight:600;">Governance-Timer</span>
          <span
            title={governanceTooltip}
            style="padding:.15rem .45rem;border-radius:999px;background:#1d4ed8;color:#fff;font-size:.8rem;"
          >
            7+7 Tage
          </span>
        </span>
        <span style="font-size:.8rem;color:#1d3c7a;">7 Tage Beratung + 7 Tage Einspruch nach Governance-Matrix.</span>
      </div>
    </section>
  </aside>

  <!-- Timeline-Stub -->
  <footer style="position:absolute;left:0;right:0;bottom:0;background:#ffffffcc;padding:.5rem 1rem;border-top:1px solid #eee;">
    Timeline (stub)
  </footer>
</div>
