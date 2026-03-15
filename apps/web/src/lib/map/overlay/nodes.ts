import type { Map as MapLibreMap, Marker } from 'maplibre-gl';
import type { RenderableMapPoint } from '../../../routes/map/types';
import { ICONS, MARKER_SIZES } from '$lib/ui/icons';

export class NodesOverlay {
  private activeMarkers = new Map<string, { marker: Marker, element: HTMLElement, item: RenderableMapPoint, cleanup: () => void }>();

  constructor(private map: MapLibreMap) {}

  private getMarkerCategory(type: string | undefined): string {
    return type || 'node';
  }

  public async update(points: RenderableMapPoint[], showNodes: boolean) {
    if (!this.map) return;
    const maplibregl = await import('maplibre-gl');

    if (!showNodes) {
        // If hidden, remove all
        this.activeMarkers.forEach(({ cleanup }) => cleanup());
        this.activeMarkers.clear();
        return;
    }

    const currentIds = new Set<string>();

    for (const item of points) {
        currentIds.add(item.id);
        const markerCategory = this.getMarkerCategory(item.type);
        let existing = this.activeMarkers.get(item.id);

        // Robustness: Check if category changed (e.g. node became account, unlikely but possible)
        if (existing) {
             const isAccount = existing.element.classList.contains('marker-account');
             const shouldBeAccount = markerCategory === 'account';

             if (isAccount !== shouldBeAccount) {
                 // Category mismatch - force recreate
                 existing.cleanup();
                 this.activeMarkers.delete(item.id);
                 existing = undefined;
             }
        }

        // Check if we need to update or create
        if (existing) {
            // Update item data to prevent stale data in delegated events
            existing.item = item;

            // Update position if changed
            const { marker, element } = existing;
            element.dataset.id = item.id;
            const lngLat = marker.getLngLat();
            if (Math.abs(lngLat.lng - item.lon) > 0.000001 || Math.abs(lngLat.lat - item.lat) > 0.000001) {
                marker.setLngLat([item.lon, item.lat]);
            }
            // Update attributes
            if (element.title !== item.title) {
                element.title = item.title;
                element.setAttribute('aria-label', item.title);
            }
            element.dataset.testid = `marker-${item.type || 'node'}-${item.id}`;
        } else {
            // Create new
            const element = document.createElement('button');
            element.type = 'button';
            element.className = markerCategory === 'account' ? 'map-marker marker-account' : 'map-marker';

            // Identifying data for event delegation
            element.dataset.id = item.id;

            // Robust testing selector based on domain semantics (and unique ID for stability)
            element.dataset.testid = `marker-${item.type || 'node'}-${item.id}`;

            if (markerCategory === 'account') {
                element.style.setProperty('--marker-icon', `url('${ICONS.garnrolle}')`);
                element.style.setProperty('--marker-size', `${MARKER_SIZES.account}px`);
            }

            element.setAttribute('aria-label', item.title);
            element.title = item.title;

            const marker = new maplibregl.Marker({ element, anchor: 'bottom' })
                .setLngLat([item.lon, item.lat])
                .addTo(this.map);

            // Re-apply accessibility attributes after addTo()
            element.setAttribute('aria-label', item.title);
            element.title = item.title;

            this.activeMarkers.set(item.id, {
                marker,
                element,
                item,
                cleanup: () => {
                    marker.remove();
                }
            });
        }
    }

    // Cleanup removed markers
    for (const [id, { cleanup }] of this.activeMarkers.entries()) {
        if (!currentIds.has(id)) {
            cleanup();
            this.activeMarkers.delete(id);
        }
    }
  }

  public getActiveMarker(id: string) {
    return this.activeMarkers.get(id);
  }

  public destroy() {
    this.activeMarkers.forEach(({ cleanup }) => cleanup());
    this.activeMarkers.clear();
  }
}
