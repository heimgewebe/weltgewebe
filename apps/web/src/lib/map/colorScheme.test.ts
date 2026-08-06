import { describe, expect, it, vi } from "vitest";
import {
  normalizeColorScheme,
  observeDocumentColorScheme,
  readDocumentColorScheme,
} from "./colorScheme";

describe("normalizeColorScheme", () => {
  it("accepts only dark as dark; everything else is light", () => {
    expect(normalizeColorScheme("dark")).toBe("dark");
    expect(normalizeColorScheme("light")).toBe("light");
    expect(normalizeColorScheme("system")).toBe("light");
    expect(normalizeColorScheme(undefined)).toBe("light");
    expect(normalizeColorScheme(null)).toBe("light");
    expect(normalizeColorScheme("")).toBe("light");
    expect(normalizeColorScheme("DARK")).toBe("light");
  });
});

describe("readDocumentColorScheme", () => {
  it("falls back to light when no document exists", () => {
    expect(readDocumentColorScheme()).toBe("light");
  });

  it("reads dataset.colorScheme through the normalizer", () => {
    expect(readDocumentColorScheme({ dataset: { colorScheme: "dark" } })).toBe(
      "dark",
    );
    expect(readDocumentColorScheme({ dataset: { colorScheme: "light" } })).toBe(
      "light",
    );
    expect(readDocumentColorScheme({ dataset: {} })).toBe("light");
  });
});

describe("observeDocumentColorScheme", () => {
  it("returns a no-op cleanup when no document exists", () => {
    const observerFactory = vi.fn();
    const stop = observeDocumentColorScheme(
      vi.fn(),
      undefined,
      observerFactory,
    );

    expect(observerFactory).not.toHaveBeenCalled();
    expect(() => stop()).not.toThrow();
  });

  it("notifies only on actual transitions and disconnects cleanly", () => {
    const root = {
      dataset: { colorScheme: "light" },
    } as unknown as HTMLElement;
    const onChange = vi.fn();
    const observe = vi.fn();
    const disconnect = vi.fn();
    let notify: MutationCallback | undefined;

    const stop = observeDocumentColorScheme(onChange, root, (callback) => {
      notify = callback;
      return { observe, disconnect };
    });

    expect(observe).toHaveBeenCalledWith(root, {
      attributes: true,
      attributeFilter: ["data-color-scheme"],
    });
    expect(onChange).not.toHaveBeenCalled();

    root.dataset.colorScheme = "dark";
    notify?.([], {} as MutationObserver);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenLastCalledWith("dark");

    notify?.([], {} as MutationObserver);
    expect(onChange).toHaveBeenCalledTimes(1);

    root.dataset.colorScheme = "light";
    notify?.([], {} as MutationObserver);
    expect(onChange).toHaveBeenCalledTimes(2);
    expect(onChange).toHaveBeenLastCalledWith("light");

    stop();
    expect(disconnect).toHaveBeenCalledTimes(1);
  });
});
