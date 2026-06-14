import { describe, it, expect } from "vitest";
import {
  parseMapUrlState,
  parseFocusParam,
  isSupportedLens,
  isSupportedCompose,
} from "./urlState";

describe("parseFocusParam", () => {
  it("parses focus=node:<id>", () => {
    expect(parseFocusParam("node:abc")).toEqual({ type: "node", id: "abc" });
  });

  it("parses focus=garnrolle:<id>", () => {
    expect(parseFocusParam("garnrolle:abc")).toEqual({
      type: "garnrolle",
      id: "abc",
    });
  });

  it("parses focus=account:<id> as a garnrolle alias", () => {
    expect(parseFocusParam("account:abc")).toEqual({
      type: "garnrolle",
      id: "abc",
    });
  });

  it("keeps colons inside the id (only the first colon splits)", () => {
    expect(parseFocusParam("node:a:b:c")).toEqual({
      type: "node",
      id: "a:b:c",
    });
  });

  it("rejects an empty focus id", () => {
    expect(parseFocusParam("node:")).toBeNull();
  });

  it("rejects an empty type", () => {
    expect(parseFocusParam(":abc")).toBeNull();
  });

  it("rejects a malformed focus without a separator", () => {
    expect(parseFocusParam("node")).toBeNull();
  });

  it("rejects an unknown focus type", () => {
    expect(parseFocusParam("edge:abc")).toBeNull();
    expect(parseFocusParam("good:abc")).toBeNull();
  });

  it("returns null for null/empty input", () => {
    expect(parseFocusParam(null)).toBeNull();
    expect(parseFocusParam("")).toBeNull();
  });
});

describe("isSupportedLens / isSupportedCompose", () => {
  it("accepts filter and search lenses", () => {
    expect(isSupportedLens("filter")).toBe(true);
    expect(isSupportedLens("search")).toBe(true);
  });

  it("rejects unknown lenses and null", () => {
    expect(isSupportedLens("nope")).toBe(false);
    expect(isSupportedLens("")).toBe(false);
    expect(isSupportedLens(null)).toBe(false);
  });

  it("accepts compose=node only", () => {
    expect(isSupportedCompose("node")).toBe(true);
    expect(isSupportedCompose("edge")).toBe(false);
    expect(isSupportedCompose("good")).toBe(false);
    expect(isSupportedCompose(null)).toBe(false);
  });
});

describe("parseMapUrlState", () => {
  const parse = (query: string) => parseMapUrlState(new URLSearchParams(query));

  it("parses a node focus deep link", () => {
    const result = parse("focus=node:abc");
    expect(result.focus).toEqual({ type: "node", id: "abc" });
    expect(result.invalidKeys).toEqual([]);
  });

  it("parses a garnrolle focus deep link", () => {
    const result = parse("focus=garnrolle:abc");
    expect(result.focus).toEqual({ type: "garnrolle", id: "abc" });
    expect(result.invalidKeys).toEqual([]);
  });

  it("parses focus=account:<id> as garnrolle", () => {
    const result = parse("focus=account:abc");
    expect(result.focus).toEqual({ type: "garnrolle", id: "abc" });
  });

  it("decodes a URL-encoded focus id", () => {
    // %3A -> ":" separator, %20 -> space inside the id.
    const result = parse("focus=node%3Ahammer%20park");
    expect(result.focus).toEqual({ type: "node", id: "hammer park" });
    expect(result.invalidKeys).toEqual([]);
  });

  it("records an empty focus id as invalid", () => {
    const result = parse("focus=node:");
    expect(result.focus).toBeNull();
    expect(result.invalidKeys).toContain("focus");
  });

  it("records a malformed focus as invalid", () => {
    const result = parse("focus=notavalidtype");
    expect(result.focus).toBeNull();
    expect(result.invalidKeys).toContain("focus");
  });

  it("accepts lens=filter", () => {
    expect(parse("lens=filter").lens).toBe("filter");
  });

  it("accepts lens=search", () => {
    expect(parse("lens=search").lens).toBe("search");
  });

  it("records an unknown lens as invalid", () => {
    const result = parse("lens=nope");
    expect(result.lens).toBeNull();
    expect(result.invalidKeys).toContain("lens");
  });

  it("accepts compose=node", () => {
    expect(parse("compose=node").compose).toBe("node");
  });

  it("records compose=edge as invalid", () => {
    const result = parse("compose=edge");
    expect(result.compose).toBeNull();
    expect(result.invalidKeys).toContain("compose");
  });

  it("accepts a non-empty tab parser-side", () => {
    expect(parse("tab=overview").tab).toBe("overview");
  });

  it("records an empty tab as invalid", () => {
    const result = parse("tab=");
    expect(result.tab).toBeNull();
    expect(result.invalidKeys).toContain("tab");
  });

  it("returns all-null state for an empty query", () => {
    expect(parse("")).toEqual({
      focus: null,
      tab: null,
      lens: null,
      compose: null,
      invalidKeys: [],
    });
  });

  it("ignores unknown keys", () => {
    const result = parse("foo=bar&baz=qux");
    expect(result.invalidKeys).toEqual([]);
    expect(result.focus).toBeNull();
  });

  it("combines several invalid values without throwing", () => {
    const result = parse("focus=node:&lens=nope&compose=edge&tab=");
    expect(result.focus).toBeNull();
    expect(result.lens).toBeNull();
    expect(result.compose).toBeNull();
    expect(result.tab).toBeNull();
    expect(result.invalidKeys).toEqual(["focus", "lens", "compose", "tab"]);
  });

  it("never throws on weird values", () => {
    const weird = [
      "focus=:::",
      "focus=node:" + "x".repeat(5000),
      "lens=%00",
      "compose=%E2%9C%93",
      "tab=%20",
      "focus=node:a&focus=node:b",
    ];
    for (const query of weird) {
      expect(() => parse(query)).not.toThrow();
    }
  });
});
