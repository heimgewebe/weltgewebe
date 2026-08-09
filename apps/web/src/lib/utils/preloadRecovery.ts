const PRELOAD_RECOVERY_KEY = "weltgewebe:preload-recovery:last-error";

type StorageLike = Pick<Storage, "getItem" | "setItem">;
type EventTargetLike = Pick<
  EventTarget,
  "addEventListener" | "removeEventListener"
>;

export interface PreloadRecoveryOptions {
  target?: EventTargetLike;
  storage?: StorageLike | null;
  reload?: () => void;
}

function payloadFingerprint(payload: unknown): string {
  if (typeof payload === "string") return payload.slice(0, 512);
  if (payload && typeof payload === "object") {
    const record = payload as { name?: unknown; message?: unknown };
    if (typeof record.message === "string") {
      const name = typeof record.name === "string" ? record.name : "Error";
      return `${name}:${record.message}`.slice(0, 512);
    }
  }

  try {
    const serialized = JSON.stringify(payload);
    if (serialized) return serialized.slice(0, 512);
  } catch {
    // Fall through to a stable generic fingerprint.
  }
  return String(payload).slice(0, 512);
}

export function installVitePreloadRecovery(
  options: PreloadRecoveryOptions = {},
): () => void {
  const target = options.target ?? window;
  const reload = options.reload ?? (() => window.location.reload());
  const inMemoryAttempts = new Set<string>();

  let storage = options.storage;
  if (storage === undefined) {
    try {
      storage = window.sessionStorage;
    } catch {
      storage = null;
    }
  }

  const handlePreloadError: EventListener = (rawEvent) => {
    const event = rawEvent as Event & { payload?: unknown };
    const fingerprint = payloadFingerprint(event.payload);

    let alreadyAttempted = inMemoryAttempts.has(fingerprint);
    if (!alreadyAttempted && storage) {
      try {
        alreadyAttempted =
          storage.getItem(PRELOAD_RECOVERY_KEY) === fingerprint;
      } catch {
        // sessionStorage can be unavailable in privacy-restricted contexts.
      }
    }

    if (alreadyAttempted) return;

    inMemoryAttempts.add(fingerprint);
    if (storage) {
      try {
        storage.setItem(PRELOAD_RECOVERY_KEY, fingerprint);
      } catch {
        // The in-memory guard still prevents a same-page reload loop.
      }
    }

    event.preventDefault();
    reload();
  };

  target.addEventListener("vite:preloadError", handlePreloadError);
  return () =>
    target.removeEventListener("vite:preloadError", handlePreloadError);
}
