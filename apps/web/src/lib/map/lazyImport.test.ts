import { describe, expect, it, vi } from "vitest";
import { createResettableLazyImport } from "$lib/map/lazyImport";

describe("createResettableLazyImport", () => {
  it("reuses a successful promise", async () => {
    const loader = vi.fn(async () => ({ ok: true }));
    const load = createResettableLazyImport(loader);

    const first = load();
    const second = load();
    await expect(first).resolves.toEqual({ ok: true });
    await expect(second).resolves.toEqual({ ok: true });
    expect(first).toBe(second);
    expect(loader).toHaveBeenCalledTimes(1);
  });

  it("resets after rejection so the next open reloads", async () => {
    const loader = vi
      .fn()
      .mockRejectedValueOnce(new Error("chunk missing"))
      .mockResolvedValueOnce({ ok: true });
    const load = createResettableLazyImport(loader);

    await expect(load()).rejects.toThrow("chunk missing");
    await expect(load()).resolves.toEqual({ ok: true });
    expect(loader).toHaveBeenCalledTimes(2);
  });
});
