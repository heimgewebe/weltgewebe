type MapLibreProtocolRegistry = Pick<
  typeof import("maplibre-gl"),
  "addProtocol" | "removeProtocol"
>;

type ProtocolLoadFunction = Parameters<
  MapLibreProtocolRegistry["addProtocol"]
>[1];

interface ProtocolRegistration {
  load: ProtocolLoadFunction;
}

const registrations = new WeakMap<
  MapLibreProtocolRegistry,
  ProtocolRegistration[]
>();

/**
 * Register one component-owned PMTiles handler without letting an older map
 * teardown remove the handler of a newer overlapping map mount.
 *
 * MapLibre's custom-protocol registry is module-global. addProtocol replaces the
 * current handler and removeProtocol deletes it unconditionally, so component
 * cleanup needs stack semantics rather than a blind global removal.
 */
export function registerPmtilesProtocol(
  maplibre: MapLibreProtocolRegistry,
  load: ProtocolLoadFunction,
): () => void {
  const stack = registrations.get(maplibre) ?? [];
  const registration = { load };
  stack.push(registration);
  registrations.set(maplibre, stack);
  maplibre.addProtocol("pmtiles", load);

  let released = false;
  return () => {
    if (released) return;
    released = true;

    const index = stack.indexOf(registration);
    if (index === -1) return;

    const wasActive = index === stack.length - 1;
    stack.splice(index, 1);
    if (!wasActive) return;

    const previous = stack.at(-1);
    if (previous) {
      maplibre.addProtocol("pmtiles", previous.load);
      return;
    }

    registrations.delete(maplibre);
    maplibre.removeProtocol("pmtiles");
  };
}
