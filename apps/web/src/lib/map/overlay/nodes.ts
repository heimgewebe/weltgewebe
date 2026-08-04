import type { Map as MapLibreMap, Marker, MarkerOptions } from "maplibre-gl";
import type {
  MapEdge,
  MapEntityViewModel,
  MapEntityWeave,
  MapEntityNode,
  MapEntityWebgemeindezentrum,
} from "$lib/map/types";
import "./markers.css";
import { garnrolleIcon } from "$lib/ui/icons";
import {
  deriveEntityWeave,
  projectEntityWeaves,
  themeConicGradient,
  voteStitchConicGradient,
} from "$lib/map/weaveModel";

function hasRenderablePosition(item: MapEntityViewModel): boolean {
  return (
    Number.isFinite(item.lat) &&
    Number.isFinite(item.lon) &&
    item.lat >= -90 &&
    item.lat <= 90 &&
    item.lon >= -180 &&
    item.lon <= 180
  );
}

export function diffSearchMatchIds(
  previous: ReadonlySet<string>,
  next: ReadonlySet<string>,
): { added: string[]; removed: string[] } {
  const added: string[] = [];
  const removed: string[] = [];

  for (const id of next) {
    if (!previous.has(id)) added.push(id);
  }
  for (const id of previous) {
    if (!next.has(id)) removed.push(id);
  }

  return { added, removed };
}

export function filterVisibleWeaveEdges(
  points: MapEntityViewModel[],
  edges: MapEdge[],
): MapEdge[] {
  const visibleIds = new Set<string>();
  for (const point of points) {
    visibleIds.add(point.id);
    if (point.type === "webgemeindezentrum") {
      visibleIds.add(point.faden_endpoint_id);
    }
  }
  return edges.filter(
    (edge) =>
      visibleIds.has(edge.source_id) && visibleIds.has(edge.target_id),
  );
}

export type MarkerConstructor = new (options?: MarkerOptions) => Marker;

type WeaveEntity = MapEntityNode | MapEntityWebgemeindezentrum;

function entityWeave(item: WeaveEntity): MapEntityWeave {
  return item.weave ?? deriveEntityWeave(item, [], 0);
}

export function weaveRenderSignature(weave: MapEntityWeave): string {
  const themes = weave.themeSegments
    .map(({ color, startDeg, spanDeg }) => `${color}:${startDeg}:${spanDeg}`)
    .join(",");
  const arcs = weave.proposalArcs
    .map(
      ({ color, startDeg, spanDeg, opacity, voteThreadCount }) =>
        `${color}:${startDeg}:${spanDeg}:${opacity}:${voteThreadCount}`,
    )
    .join(",");
  return [
    weave.primaryThemeColor,
    weave.coreDensity,
    weave.knottingThreadCount,
    weave.conversationThreadCount,
    weave.conversationOpacity,
    weave.proposalCount,
    weave.proposalOverflowCount,
    weave.voteThreadCount,
    themes,
    arcs,
  ].join("|");
}

function renderWeave(root: HTMLElement, weave: MapEntityWeave) {
  Object.assign(root.dataset, {
    zoneOrder: "knotting,conversation,proposal,vote",
    knottingThreads: String(weave.knottingThreadCount),
    conversationThreads: String(weave.conversationThreadCount),
    proposalCount: String(weave.proposalCount),
    voteThreads: String(weave.voteThreadCount),
  });
  root.style.setProperty("--weave-primary", weave.primaryThemeColor);
  root.style.setProperty(
    "--weave-theme-gradient",
    themeConicGradient(weave.themeSegments),
  );
  root.style.setProperty("--weave-core-density", String(weave.coreDensity));
  root.style.setProperty(
    "--weave-conversation-opacity",
    String(weave.conversationOpacity),
  );
  const proposals = weave.proposalArcs
    .map((arc) => {
      const votes = arc.voteThreadCount
        ? `<span class="woven-node__vote-stitches" data-zone="vote" style="background:${voteStitchConicGradient(arc.spanDeg, arc.voteThreadCount)}"></span>`
        : "";
      return `<span class="woven-node__proposal-arc" data-zone="proposal" data-vote-threads="${arc.voteThreadCount}" style="--arc-start:${arc.startDeg}deg;--arc-span:${arc.spanDeg}deg;--arc-color:${arc.color};opacity:${arc.opacity}">${votes}</span>`;
    })
    .join("");
  root.innerHTML = `<span class="woven-node__core" data-zone="knotting"><span class="woven-node__cross"></span></span><span class="woven-node__conversation${weave.conversationThreadCount ? "" : " is-empty"}" data-zone="conversation"></span>${proposals}${weave.proposalOverflowCount ? `<span class="woven-node__overflow">+${weave.proposalOverflowCount}</span>` : ""}`;
}

function accessibleMarkerLabel(item: MapEntityViewModel): string {
  if (item.type === "garnrolle") return item.title;
  const weave = entityWeave(item);
  return `${item.title}. Knüpfkern ${weave.knottingThreadCount}. Gesprächsring ${weave.conversationThreadCount}. Anträge ${weave.proposalCount}. Stimmen ${weave.voteThreadCount}.`;
}

function createWeaveRoot(
  item: WeaveEntity,
  markerCategory: "node" | "webgemeindezentrum",
): { root: HTMLElement; signature: string } {
  const weave = entityWeave(item);
  const root = document.createElement("span");
  root.className = `woven-node woven-node--${markerCategory}`;
  root.setAttribute("aria-hidden", "true");
  renderWeave(root, weave);
  return { root, signature: weaveRenderSignature(weave) };
}

export class NodesOverlay {
  private activeMarkers = new Map<
    string,
    {
      marker: Marker;
      element: HTMLElement;
      item: MapEntityViewModel;
      weaveRoot: HTMLElement | null;
      weaveSignature: string | null;
      cleanup: () => void;
    }
  >();
  private searchMatchIds = new Set<string>();
  private selectedMarkerId: string | null = null;
  private compactWeave = false;
  private readonly handleZoom = () => {
    if (this.map) this.updateZoom(this.map.getZoom());
  };

  constructor(
    private map: MapLibreMap | null,
    private MarkerClass: MarkerConstructor,
  ) {
    if (this.map) {
      this.updateZoom(this.map.getZoom());
      this.map.on("zoom", this.handleZoom);
    }
  }

  private syncWeaveDetail(root: HTMLElement) {
    root.classList.toggle("woven-node--compact", this.compactWeave);
    root.dataset.weaveDetail = this.compactWeave ? "compact" : "detail";
  }

  public updateZoom(zoom: number) {
    const compact = zoom < 13.5;
    if (compact === this.compactWeave) return;
    this.compactWeave = compact;
    for (const { weaveRoot } of this.activeMarkers.values()) {
      if (weaveRoot) this.syncWeaveDetail(weaveRoot);
    }
  }

  private getMarkerCategory(
    type: MapEntityViewModel["type"],
  ): "node" | "account" | "webgemeindezentrum" {
    if (type === "garnrolle") return "account";
    if (type === "webgemeindezentrum") return "webgemeindezentrum";
    return "node";
  }

  private syncWebgemeindezentrumAppearance(
    element: HTMLElement,
    item: MapEntityViewModel,
  ) {
    if (item.type !== "webgemeindezentrum") return;
    const visual = element.children[0] as HTMLElement | undefined;
    if (!visual) return;
    const borderStyle = item.location_state === "confirmed" ? "" : "dashed";
    if (visual.style.borderStyle !== borderStyle) {
      visual.style.borderStyle = borderStyle;
    }
  }

  private syncWeaveAppearance(
    entry: {
      weaveRoot: HTMLElement | null;
      weaveSignature: string | null;
    },
    item: MapEntityViewModel,
  ) {
    if (!entry.weaveRoot || item.type === "garnrolle") return;
    const weave = entityWeave(item);
    const signature = weaveRenderSignature(weave);
    if (signature === entry.weaveSignature) return;
    renderWeave(entry.weaveRoot, weave);
    entry.weaveSignature = signature;
  }

  public update(
    points: MapEntityViewModel[],
    showNodes: boolean,
    edges?: MapEdge[],
    nowMs = Date.now(),
  ): MapEntityViewModel[] {
    const projectedPoints =
      edges === undefined
        ? points
        : projectEntityWeaves(
            points,
            filterVisibleWeaveEdges(points, edges),
            nowMs,
          );

    if (!showNodes) {
      this.activeMarkers.forEach(({ cleanup }) => cleanup());
      this.activeMarkers.clear();
      return projectedPoints;
    }

    const map = this.map;
    if (!map) return projectedPoints;

    const currentIds = new Set<string>();

    for (const item of projectedPoints) {
      if (!hasRenderablePosition(item)) {
        const existing = this.activeMarkers.get(item.id);
        if (existing) {
          existing.cleanup();
          this.activeMarkers.delete(item.id);
        }
        continue;
      }

      currentIds.add(item.id);
      const markerCategory = this.getMarkerCategory(item.type);
      let existing = this.activeMarkers.get(item.id);

      if (
        existing &&
        existing.element.dataset.markerCategory !== markerCategory
      ) {
        existing.cleanup();
        this.activeMarkers.delete(item.id);
        existing = undefined;
      }

      if (existing) {
        existing.item = item;

        const { marker, element } = existing;
        if (element.dataset.id !== item.id) element.dataset.id = item.id;
        const lngLat = marker.getLngLat();
        if (
          Math.abs(lngLat.lng - item.lon) > 0.000001 ||
          Math.abs(lngLat.lat - item.lat) > 0.000001
        ) {
          marker.setLngLat([item.lon, item.lat]);
        }
        if (element.title !== item.title) element.title = item.title;
        const ariaLabel = accessibleMarkerLabel(item);
        if (element.getAttribute("aria-label") !== ariaLabel) {
          element.setAttribute("aria-label", ariaLabel);
        }
        const testId = `marker-${item.type}-${item.id}`;
        if (element.dataset.testid !== testId) element.dataset.testid = testId;
        if (element.dataset.markerCategory !== markerCategory) {
          element.dataset.markerCategory = markerCategory;
        }
        if (item.type === "webgemeindezentrum") {
          if (element.dataset.locationState !== item.location_state) {
            element.dataset.locationState = item.location_state;
          }
        } else if ("locationState" in element.dataset) {
          delete element.dataset.locationState;
        }
        this.syncWebgemeindezentrumAppearance(element, item);
        this.syncWeaveAppearance(existing, item);
      } else {
        const element = document.createElement("button");
        element.type = "button";
        element.className =
          markerCategory === "account"
            ? "map-marker marker-account"
            : markerCategory === "webgemeindezentrum"
              ? "map-marker marker-webgemeindezentrum"
              : "map-marker";

        element.dataset.id = item.id;
        element.dataset.markerCategory = markerCategory;
        if (item.type === "webgemeindezentrum") {
          element.dataset.locationState = item.location_state;
        }
        element.dataset.testid = `marker-${item.type}-${item.id}`;

        const visual = document.createElement("span");
        visual.className =
          markerCategory === "account"
            ? "map-marker__visual marker-account__visual"
            : markerCategory === "webgemeindezentrum"
              ? "map-marker__visual marker-webgemeindezentrum__visual"
              : "map-marker__visual marker-node__visual";
        visual.setAttribute("aria-hidden", "true");

        let weaveRoot: HTMLElement | null = null;
        let weaveSignature: string | null = null;
        if (item.type === "garnrolle") {
          const icon = document.createElement("img");
          icon.className = "marker-account__icon";
          icon.src = garnrolleIcon;
          icon.alt = "";
          icon.setAttribute("aria-hidden", "true");
          icon.draggable = false;
          visual.append(icon);
        } else if (item.type === "webgemeindezentrum") {
          const icon = document.createElement("span");
          icon.className = "marker-webgemeindezentrum__icon";
          icon.setAttribute("aria-hidden", "true");
          const woven = createWeaveRoot(item, "webgemeindezentrum");
          weaveRoot = woven.root;
          weaveSignature = woven.signature;
          this.syncWeaveDetail(weaveRoot);
          icon.append(weaveRoot);
          visual.append(icon);
        } else {
          const woven = createWeaveRoot(item, "node");
          weaveRoot = woven.root;
          weaveSignature = woven.signature;
          this.syncWeaveDetail(weaveRoot);
          visual.append(weaveRoot);
        }

        const halo = document.createElement("span");
        halo.className = "map-marker__halo";
        halo.setAttribute("aria-hidden", "true");

        element.append(visual, halo);
        this.syncWebgemeindezentrumAppearance(element, item);

        element.setAttribute("aria-label", accessibleMarkerLabel(item));
        element.title = item.title;

        const marker = new this.MarkerClass({ element, anchor: "bottom" })
          .setLngLat([item.lon, item.lat])
          .addTo(map);

        if (this.searchMatchIds.has(item.id)) {
          element.classList.add("search-highlight");
          element.dataset.searchMatch = "true";
        }
        if (this.selectedMarkerId === item.id) {
          element.classList.add("is-selected");
          element.dataset.selected = "true";
          element.setAttribute("aria-current", "true");
        }

        this.activeMarkers.set(item.id, {
          marker,
          element,
          item,
          weaveRoot,
          weaveSignature,
          cleanup: () => {
            marker.remove();
          },
        });
      }
    }

    for (const [id, { cleanup }] of this.activeMarkers.entries()) {
      if (!currentIds.has(id)) {
        cleanup();
        this.activeMarkers.delete(id);
      }
    }
    return projectedPoints;
  }

  private setSearchMatch(id: string, highlighted: boolean) {
    const entry = this.activeMarkers.get(id);
    if (!entry) return;

    if (highlighted) {
      entry.element.classList.add("search-highlight");
      entry.element.dataset.searchMatch = "true";
    } else {
      entry.element.classList.remove("search-highlight");
      delete entry.element.dataset.searchMatch;
    }
  }

  private setSelected(id: string, selected: boolean) {
    const entry = this.activeMarkers.get(id);
    if (!entry) return;

    entry.element.classList.toggle("is-selected", selected);
    if (selected) {
      entry.element.dataset.selected = "true";
      entry.element.setAttribute("aria-current", "true");
    } else {
      delete entry.element.dataset.selected;
      entry.element.removeAttribute("aria-current");
    }
  }

  public updateSelection(nextSelectedMarkerId: string | null) {
    if (this.selectedMarkerId === nextSelectedMarkerId) return;

    if (this.selectedMarkerId !== null) {
      this.setSelected(this.selectedMarkerId, false);
    }
    if (nextSelectedMarkerId !== null) {
      this.setSelected(nextSelectedMarkerId, true);
    }
    this.selectedMarkerId = nextSelectedMarkerId;
  }

  public updateSearchMatches(nextSearchMatchIds: ReadonlySet<string>) {
    const { added, removed } = diffSearchMatchIds(
      this.searchMatchIds,
      nextSearchMatchIds,
    );

    for (const id of removed) this.setSearchMatch(id, false);
    for (const id of added) this.setSearchMatch(id, true);

    this.searchMatchIds = new Set(nextSearchMatchIds);
  }

  public getActiveMarker(id: string) {
    return this.activeMarkers.get(id);
  }

  public destroy() {
    if (this.map) this.map.off("zoom", this.handleZoom);
    this.activeMarkers.forEach(({ cleanup }) => cleanup());
    this.activeMarkers.clear();
    this.searchMatchIds.clear();
    this.selectedMarkerId = null;
  }
}
