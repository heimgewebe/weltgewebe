<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { selection } from "$lib/stores/uiView";
  import {
    buildPanelEndpoint,
    createPanelDetailsLoader,
  } from "$lib/panels/panelDetails";
  import { formatDate } from "$lib/utils/formatDate";
  import type {
    MapEntityWebgemeindezentrum,
    OrtswebereiReference,
    WebgemeindezentrumLocationState,
  } from "$lib/map/types";

  type LocationHistoryEvent = {
    event_id: number;
    event_type: string;
    location_state: WebgemeindezentrumLocationState;
    location_state_label: string;
    location: { lat: number; lon: number };
    location_label: string;
    reason: string;
    decided_at: string;
  };

  type CenterDetails = {
    type: "webgemeindezentrum";
    id: string;
    title: string;
    ortsweberei: OrtswebereiReference;
    location_state: WebgemeindezentrumLocationState;
    location_state_label: string;
    location: { lat: number; lon: number };
    location_label: string;
    meeting_note: string;
    access_note: string;
    created_at: string;
    updated_at: string;
    location_history?: LocationHistoryEvent[];
  };

  let heading: HTMLHeadingElement;
  const detailsLoader = createPanelDetailsLoader<CenterDetails>(selection, {
    buildEndpoint: (id) => buildPanelEndpoint("webgemeindezentrum", id),
    resourceLabel: "Webgemeindezentrum",
  });
  const detailsStore = detailsLoader.details;
  const loadingStore = detailsLoader.isLoading;
  onDestroy(detailsLoader.destroy);
  onMount(() => heading?.focus());

  $: fallback = $selection?.data as MapEntityWebgemeindezentrum | undefined;
  $: details = $detailsStore;
  $: title = details?.title || fallback?.title || "Webgemeindezentrum";
  $: locationState = details?.location_state || fallback?.location_state;
  $: locationStateLabel =
    details?.location_state_label || fallback?.location_state_label;
  $: locationLabel = details?.location_label || fallback?.location_label;
  $: meetingNote = details?.meeting_note || fallback?.meeting_note;
  $: accessNote = details?.access_note || fallback?.access_note;
  $: ortsweberei = details?.ortsweberei || fallback?.ortsweberei;
  $: location =
    details?.location ||
    (fallback ? { lat: fallback.lat, lon: fallback.lon } : undefined);
  $: history = details?.location_history || [];
  $: truthHeading =
    locationState === "confirmed"
      ? "Bestätigter Treffort"
      : locationState === "unavailable"
        ? "Derzeit nicht verfügbar"
        : locationState === "relocation_proposed"
          ? "Verlegung vorgeschlagen"
          : locationState === "provisional"
            ? "Vorläufiger Treffort"
            : "Noch keine Bestätigung";
</script>

<section class="center-mode" aria-labelledby="webgemeindezentrum-heading">
  <h3
    id="webgemeindezentrum-heading"
    bind:this={heading}
    tabindex="-1"
    data-testid="webgemeindezentrum-heading"
  >
    {title}
  </h3>

  {#if locationStateLabel}
    <p
      class:desired={locationState === "desired"}
      class="location-state"
      data-testid="webgemeindezentrum-location-state"
    >
      {locationStateLabel}
    </p>
  {/if}

  <div
    class="compact-summary"
    role="region"
    aria-label="Webgemeindezentrum im Überblick"
    data-testid="webgemeindezentrum-compact-summary"
  >
    {#if locationLabel}
      <p><strong>Treffort:</strong> {locationLabel}</p>
    {/if}
    {#if ortsweberei}
      <p><strong>Ortsweberei:</strong> {ortsweberei.name}</p>
    {/if}
  </div>

  {#if $loadingStore && !details}
    <p class="ghost" role="status">Lade Standortverlauf…</p>
  {/if}

  <div class="full-content">
    {#if meetingNote}
      <section aria-labelledby="meeting-purpose-heading">
        <h4 id="meeting-purpose-heading">Gemeinsam vor Ort</h4>
        <p>{meetingNote}</p>
      </section>
    {/if}

    {#if accessNote}
      <aside class="truth-note" aria-label="Standortstatus">
        <strong>{truthHeading}</strong>
        <p>{accessNote}</p>
      </aside>
    {/if}

    {#if ortsweberei}
      <dl>
        <div>
          <dt>Ortsweberei</dt>
          <dd>{ortsweberei.name}</dd>
        </div>
        <div>
          <dt>Gewebezelle</dt>
          <dd><code>{ortsweberei.gewebezelle_id}</code></dd>
        </div>
        {#if location}
          <div>
            <dt>Kartenpunkt</dt>
            <dd>{location.lat.toFixed(4)}, {location.lon.toFixed(4)}</dd>
          </div>
        {/if}
      </dl>
    {/if}

    <section aria-labelledby="location-history-heading">
      <h4 id="location-history-heading">Standortverlauf</h4>
      {#if history.length > 0}
        <ol class="timeline">
          {#each history as event}
            <li>
              <strong>{event.location_state_label}</strong>
              <span>{formatDate(event.decided_at)}</span>
              <p>{event.reason}</p>
            </li>
          {/each}
        </ol>
      {:else if !$loadingStore}
        <p class="ghost">
          Der erste gewünschte Standort ist im kanonischen Datensatz verankert.
        </p>
      {/if}
    </section>
  </div>
</section>
