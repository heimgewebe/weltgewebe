import { describe, expect, it } from "vitest";
import { selectMapResourceTransport } from "./mapResourceTransport";

const productionRuntime = {
  isDevelopment: false,
  isProduction: true,
  testProxyEnabled: false,
} as const;

const developmentRuntime = {
  isDevelopment: true,
  isProduction: false,
  testProxyEnabled: false,
} as const;

describe("selectMapResourceTransport", () => {
  it("uses static-list for empty same-origin production data", () => {
    expect(selectMapResourceTransport("", productionRuntime)).toBe(
      "static-list",
    );
    expect(selectMapResourceTransport(undefined, productionRuntime)).toBe(
      "static-list",
    );
    expect(selectMapResourceTransport(null, productionRuntime)).toBe(
      "static-list",
    );
    expect(selectMapResourceTransport("   ", productionRuntime)).toBe(
      "static-list",
    );
  });

  it("uses cursor for an empty development or test-proxy base", () => {
    expect(selectMapResourceTransport("", developmentRuntime)).toBe("cursor");
    expect(
      selectMapResourceTransport("", {
        ...productionRuntime,
        testProxyEnabled: true,
      }),
    ).toBe("cursor");
  });

  it("uses cursor when a remote or relative API base is configured", () => {
    expect(
      selectMapResourceTransport(
        "https://api.example.invalid",
        productionRuntime,
      ),
    ).toBe("cursor");
    expect(selectMapResourceTransport("/remote-api", productionRuntime)).toBe(
      "cursor",
    );
  });

  it("fails closed for contradictory runtime signals", () => {
    expect(() =>
      selectMapResourceTransport("", {
        isDevelopment: false,
        isProduction: false,
        testProxyEnabled: false,
      }),
    ).toThrow(/exactly one development or production runtime/);

    expect(() =>
      selectMapResourceTransport("", {
        isDevelopment: true,
        isProduction: true,
        testProxyEnabled: false,
      }),
    ).toThrow(/exactly one development or production runtime/);
  });

  it("fails closed for missing runtime signals", () => {
    expect(() =>
      selectMapResourceTransport(
        "",
        undefined as unknown as typeof productionRuntime,
      ),
    ).toThrow(/isDevelopment, isProduction and testProxyEnabled booleans/);

    expect(() =>
      selectMapResourceTransport("", {
        ...productionRuntime,
        testProxyEnabled: undefined as unknown as boolean,
      }),
    ).toThrow(/isDevelopment, isProduction and testProxyEnabled booleans/);
  });
});
