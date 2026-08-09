import { describe, expect, it, vi } from "vitest";
import { installVitePreloadRecovery } from "./preloadRecovery";

class MemoryStorage {
  private values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

function preloadError(message: string): Event {
  const event = new Event("vite:preloadError", { cancelable: true });
  Object.defineProperty(event, "payload", {
    value: new Error(message),
    configurable: true,
  });
  return event;
}

describe("installVitePreloadRecovery", () => {
  it("reloads once for the same failed dynamic import", () => {
    const target = new EventTarget();
    const storage = new MemoryStorage();
    const reload = vi.fn();
    const cleanup = installVitePreloadRecovery({ target, storage, reload });

    const first = preloadError("Failed to fetch chunk-abc.js");
    const second = preloadError("Failed to fetch chunk-abc.js");
    target.dispatchEvent(first);
    target.dispatchEvent(second);

    expect(reload).toHaveBeenCalledTimes(1);
    expect(first.defaultPrevented).toBe(true);
    expect(second.defaultPrevented).toBe(false);
    cleanup();
  });

  it("allows recovery for a later deployment with a different chunk", () => {
    const target = new EventTarget();
    const storage = new MemoryStorage();
    const reload = vi.fn();
    installVitePreloadRecovery({ target, storage, reload });

    target.dispatchEvent(preloadError("Failed to fetch chunk-abc.js"));
    target.dispatchEvent(preloadError("Failed to fetch chunk-def.js"));

    expect(reload).toHaveBeenCalledTimes(2);
  });

  it("falls back to the in-memory guard when storage is unavailable", () => {
    const target = new EventTarget();
    const reload = vi.fn();
    const storage = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    installVitePreloadRecovery({ target, storage, reload });

    target.dispatchEvent(preloadError("Failed to fetch chunk-abc.js"));
    target.dispatchEvent(preloadError("Failed to fetch chunk-abc.js"));

    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("removes the listener during cleanup", () => {
    const target = new EventTarget();
    const reload = vi.fn();
    const cleanup = installVitePreloadRecovery({
      target,
      storage: new MemoryStorage(),
      reload,
    });

    cleanup();
    target.dispatchEvent(preloadError("Failed to fetch chunk-abc.js"));

    expect(reload).not.toHaveBeenCalled();
  });
});
