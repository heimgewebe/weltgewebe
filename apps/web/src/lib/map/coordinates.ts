/**
 * Shared geographic sanity checks for map markers, edge endpoints, search
 * navigation and flyTo. MapLibre accepts many numeric values; domain code must
 * still refuse non-finite numbers and out-of-range WGS84 coordinates before
 * they reach markers, LineStrings or camera moves.
 */

export type MapCoordinateLike = {
  lat: number;
  lon: number;
};

export function isValidMapCoordinate(lon: number, lat: number): boolean {
  return (
    Number.isFinite(lon) &&
    Number.isFinite(lat) &&
    lat >= -90 &&
    lat <= 90 &&
    lon >= -180 &&
    lon <= 180
  );
}

export function hasRenderableMapPosition(
  item: MapCoordinateLike | null | undefined,
): boolean {
  return Boolean(item && isValidMapCoordinate(item.lon, item.lat));
}
