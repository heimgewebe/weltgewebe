import { describe, expect, it } from "vitest";
import { nodeKindLabel } from "./productLanguage";

describe("nodeKindLabel", () => {
  it.each([
    ["standard", "Allgemeiner Knoten"],
    ["event", "Ereignis"],
    ["resource", "Ressource"],
    [undefined, "Knoten"],
    ["internal-value", "Knoten"],
  ])("maps %s to a public product label", (kind, expected) => {
    expect(nodeKindLabel(kind)).toBe(expected);
  });
});
