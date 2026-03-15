import type { Map as MapLibreMap } from 'maplibre-gl';
import { enterKomposition } from '$lib/stores/uiView';

export function setupKompositionInteraction(map: MapLibreMap) {
  let longPressTimer: ReturnType<typeof setTimeout> | undefined;
  let longPressStartX = 0;
  let longPressStartY = 0;

  const clearLongPressTimer = () => {
    if (longPressTimer !== undefined) {
      clearTimeout(longPressTimer);
      longPressTimer = undefined;
    }
  };

  const handleMousedown = (e: any) => {
    clearLongPressTimer();
    const markerClicked = e.originalEvent.target instanceof HTMLElement && e.originalEvent.target.closest('.map-marker');
    if (markerClicked) return;

    longPressStartX = e.point.x;
    longPressStartY = e.point.y;
    longPressTimer = setTimeout(() => {
      enterKomposition({
        mode: 'new-knoten',
        lngLat: [e.lngLat.lng, e.lngLat.lat],
        source: 'map-longpress'
      });
    }, 800);
  };

  const handleMousemove = (e: any) => {
    if (longPressTimer !== undefined) {
      const dx = e.point.x - longPressStartX;
      const dy = e.point.y - longPressStartY;
      if (dx * dx + dy * dy > 100) { // equivalent to 10px distance
        clearLongPressTimer();
      }
    }
  };

  const handleTouchstart = (e: any) => {
    clearLongPressTimer();
    const markerClicked = e.originalEvent.target instanceof HTMLElement && e.originalEvent.target.closest('.map-marker');
    if (markerClicked) return;

    longPressStartX = e.point.x;
    longPressStartY = e.point.y;
    longPressTimer = setTimeout(() => {
      enterKomposition({
        mode: 'new-knoten',
        lngLat: [e.lngLat.lng, e.lngLat.lat],
        source: 'map-longpress'
      });
    }, 800);
  };

  const handleTouchmove = (e: any) => {
    if (longPressTimer !== undefined) {
      const dx = e.point.x - longPressStartX;
      const dy = e.point.y - longPressStartY;
      if (dx * dx + dy * dy > 100) { // equivalent to 10px distance
        clearLongPressTimer();
      }
    }
  };

  map.on('mousedown', handleMousedown);
  map.on('mouseup', clearLongPressTimer);
  map.on('mousemove', handleMousemove);
  map.on('mouseout', clearLongPressTimer);
  map.on('dragstart', clearLongPressTimer);
  map.on('movestart', clearLongPressTimer);

  map.on('touchstart', handleTouchstart);
  map.on('touchend', clearLongPressTimer);
  map.on('touchmove', handleTouchmove);
  map.on('touchcancel', clearLongPressTimer);

  return () => {
    clearLongPressTimer();
    map.off('mousedown', handleMousedown);
    map.off('mouseup', clearLongPressTimer);
    map.off('mousemove', handleMousemove);
    map.off('mouseout', clearLongPressTimer);
    map.off('dragstart', clearLongPressTimer);
    map.off('movestart', clearLongPressTimer);

    map.off('touchstart', handleTouchstart);
    map.off('touchend', clearLongPressTimer);
    map.off('touchmove', handleTouchmove);
    map.off('touchcancel', clearLongPressTimer);
  };
}
