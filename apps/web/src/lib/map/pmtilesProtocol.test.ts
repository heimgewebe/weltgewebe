import { describe, expect, it, vi } from "vitest";
import { registerPmtilesProtocol } from "./pmtilesProtocol";

type MapLibreProtocolRegistry = Pick<
  typeof import("maplibre-gl"),
  "addProtocol" | "removeProtocol"
>;
type ProtocolLoadFunction = Parameters<
  MapLibreProtocolRegistry["addProtocol"]
>[1];

function loadFunction(label: string): ProtocolLoadFunction {
  return vi.fn(async () => ({
    data: new TextEncoder().encode(label),
  })) as ProtocolLoadFunction;
}

function fakeRegistry() {
  let active: ProtocolLoadFunction | null = null;
  const addProtocol = vi.fn((_name: string, load: ProtocolLoadFunction) => {
    active = load;
  });
  const removeProtocol = vi.fn(() => {
    active = null;
  });
  const registry = {
    addProtocol,
    removeProtocol,
  } as unknown as MapLibreProtocolRegistry;

  return {
    registry,
    addProtocol,
    removeProtocol,
    active: () => active,
  };
}

describe("registerPmtilesProtocol", () => {
  it("keeps a newer mount active when an older map cleans up later", () => {
    const fake = fakeRegistry();
    const first = loadFunction("first");
    const second = loadFunction("second");

    const releaseFirst = registerPmtilesProtocol(fake.registry, first);
    const releaseSecond = registerPmtilesProtocol(fake.registry, second);

    expect(fake.active()).toBe(second);
    releaseFirst();

    expect(fake.active()).toBe(second);
    expect(fake.removeProtocol).not.toHaveBeenCalled();

    releaseSecond();
    expect(fake.active()).toBeNull();
    expect(fake.removeProtocol).toHaveBeenCalledOnce();
  });

  it("restores the previous live map when the newest mount leaves first", () => {
    const fake = fakeRegistry();
    const first = loadFunction("first");
    const second = loadFunction("second");

    const releaseFirst = registerPmtilesProtocol(fake.registry, first);
    const releaseSecond = registerPmtilesProtocol(fake.registry, second);

    releaseSecond();

    expect(fake.active()).toBe(first);
    expect(fake.addProtocol).toHaveBeenLastCalledWith("pmtiles", first);
    expect(fake.removeProtocol).not.toHaveBeenCalled();

    releaseFirst();
    expect(fake.active()).toBeNull();
  });

  it("makes cleanup idempotent", () => {
    const fake = fakeRegistry();
    const release = registerPmtilesProtocol(
      fake.registry,
      loadFunction("only"),
    );

    release();
    release();

    expect(fake.removeProtocol).toHaveBeenCalledOnce();
  });
});
