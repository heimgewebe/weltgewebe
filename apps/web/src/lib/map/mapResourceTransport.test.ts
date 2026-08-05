import { describe, expect, it } from "vitest";
import { selectMapResourceTransport } from "./mapResourceTransport";

describe("selectMapResourceTransport", () => {
  it("uses static-list when the public API base is empty", () => {
    expect(selectMapResourceTransport("")).toBe("static-list");
    expect(selectMapResourceTransport(undefined)).toBe("static-list");
    expect(selectMapResourceTransport(null)).toBe("static-list");
  });

  it("uses cursor when a remote API base is configured", () => {
    expect(selectMapResourceTransport("https://api.example.invalid")).toBe(
      "cursor",
    );
    expect(selectMapResourceTransport("/remote-api")).toBe("cursor");
  });
});
