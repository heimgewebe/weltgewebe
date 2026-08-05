import { describe, expect, it } from "vitest";
import { resolveMapInitFailure } from "$lib/map/mapInitFailure";

describe("resolveMapInitFailure", () => {
  it("fails closed for import, constructor, timeout and pre-load map errors", () => {
    expect(resolveMapInitFailure(false, "import")).toBe("fail");
    expect(resolveMapInitFailure(false, "constructor")).toBe("fail");
    expect(resolveMapInitFailure(false, "timeout")).toBe("fail");
    expect(resolveMapInitFailure(false, "maplibre-error")).toBe("fail");
  });

  it("ignores failures after the first successful load", () => {
    expect(resolveMapInitFailure(true, "timeout")).toBe("ignore");
    expect(resolveMapInitFailure(true, "maplibre-error")).toBe("ignore");
    expect(resolveMapInitFailure(true, "import")).toBe("ignore");
    expect(resolveMapInitFailure(true, "post-load-error")).toBe("ignore");
  });

  it("never fails the map for auth-camera rejection alone", () => {
    expect(resolveMapInitFailure(false, "auth-camera")).toBe("ignore");
    expect(resolveMapInitFailure(true, "auth-camera")).toBe("ignore");
  });
});
