<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import FilterOverlay from "$lib/components/FilterOverlay.svelte";
  import SearchDirectionIndicators from "$lib/components/SearchDirectionIndicators.svelte";
  import ToolFan from "$lib/components/ToolFan.svelte";
  import type { NodeSearchStatus } from "$lib/api/search";
  import type { KnottingTopic } from "$lib/knottingTopics";
  import type { MapFilterOption } from "$lib/map/contentFilters";
  import { createResettableLazyImport } from "$lib/map/lazyImport";
  import type { SearchDirectionIndicator } from "$lib/map/searchNavigation";
  import type { MapEntityViewModel } from "$lib/map/types";
  import { isSearchOpen } from "$lib/stores/searchStore";
  import { contextPanelOpen } from "$lib/stores/uiView";
  import type {
    MapDomainChanged,
    RelatedMapSelection,
  } from "$lib/components/map/mapRouteEvents";

  export let filteredResults: MapEntityViewModel[] = [];
  export let searchStatus: NodeSearchStatus = "idle";
  export let searchMode: string | null = null;
  export let searchFallbackReason: string | null = null;
  export let searchDirectionIndicators: SearchDirectionIndicator[] = [];
  export let availableTypes: MapFilterOption[] = [];
  export let availableTopics: MapFilterOption<KnottingTopic>[] = [];
  export let filterResultCount = 0;
  export let filterTotalCount = 0;
  export let allTopicsCount = 0;

  const dispatch = createEventDispatcher<{
    searchSelect: MapEntityViewModel;
    searchDirectionSelect: MapEntityViewModel;
    relatedSelect: RelatedMapSelection;
    domainChanged: MapDomainChanged;
  }>();

  type ContextPanelModule =
    typeof import("$lib/components/ContextPanel.svelte");
  let contextPanelPromise: Promise<ContextPanelModule> | null = null;
  const loadContextPanelModule = createResettableLazyImport(
    () => import("$lib/components/ContextPanel.svelte"),
  );

  function loadContextPanel(): Promise<ContextPanelModule> {
    const promise = loadContextPanelModule();
    contextPanelPromise = promise;
    void promise.catch(() => {
      if (contextPanelPromise === promise) contextPanelPromise = null;
    });
    return promise;
  }

  type SearchOverlayModule =
    typeof import("$lib/components/SearchOverlay.svelte");
  let searchOverlayPromise: Promise<SearchOverlayModule> | null = null;
  const loadSearchOverlayModule = createResettableLazyImport(
    () => import("$lib/components/SearchOverlay.svelte"),
  );

  function loadSearchOverlay(): Promise<SearchOverlayModule> {
    const promise = loadSearchOverlayModule();
    searchOverlayPromise = promise;
    void promise.catch(() => {
      if (searchOverlayPromise === promise) searchOverlayPromise = null;
    });
    return promise;
  }

  function handleSearchSelect(event: CustomEvent<MapEntityViewModel>) {
    dispatch("searchSelect", event.detail);
  }

  function handleSearchDirectionSelect(event: CustomEvent<MapEntityViewModel>) {
    dispatch("searchDirectionSelect", event.detail);
  }

  function handleRelatedSelect(event: CustomEvent<RelatedMapSelection>) {
    dispatch("relatedSelect", event.detail);
  }

  function handleDomainChanged(event: CustomEvent<MapDomainChanged>) {
    dispatch("domainChanged", event.detail);
  }
</script>

{#if $contextPanelOpen}
  {#await loadContextPanel()}
    <p role="status" class="sr-only">Lade Details…</p>
  {:then contextPanelModule}
    <svelte:component
      this={contextPanelModule.default}
      on:selectRelated={handleRelatedSelect}
      on:domainChanged={handleDomainChanged}
    />
  {:catch}
    <p role="alert">Details konnten nicht geladen werden.</p>
  {/await}
{/if}
{#if $isSearchOpen || searchOverlayPromise}
  {#await loadSearchOverlay()}
    {#if $isSearchOpen}
      <p role="status" class="sr-only">Lade Suche…</p>
    {/if}
  {:then searchOverlayModule}
    <svelte:component
      this={searchOverlayModule.default}
      {filteredResults}
      {searchStatus}
      {searchMode}
      {searchFallbackReason}
      on:select={handleSearchSelect}
    />
  {:catch}
    {#if $isSearchOpen}
      <p role="alert">Suche konnte nicht geladen werden.</p>
    {/if}
  {/await}
{/if}
<SearchDirectionIndicators
  indicators={searchDirectionIndicators}
  on:select={handleSearchDirectionSelect}
/>
<FilterOverlay
  {availableTypes}
  {availableTopics}
  resultCount={filterResultCount}
  totalCount={filterTotalCount}
  {allTopicsCount}
/>
<ToolFan />
