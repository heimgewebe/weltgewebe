import { writable } from "svelte/store";
import { browser, dev } from "$app/environment";
import buildVersion from "$lib/generated/buildVersion.json";

export interface VersionData {
  version: string;
  build_id?: string;
  built_at?: string;
  commit?: string;
  release?: string;
}

const UPDATE_CHECK_TIMEOUT_MS = 10_000;

// Ensure the store is only initialized once
function createUpdateStore() {
  const { subscribe, set } = writable(false);
  let initialized = false;
  let updateDetected = false;
  let pendingCheck: Promise<void> | undefined;

  // The local version is strictly static and bound to the client bundle at build-time.
  // It must never be dynamically updated by a runtime fetch.
  const localVersion = buildVersion.version;

  async function fetchServerVersion(): Promise<VersionData | null> {
    const controller = new AbortController();
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    const timeout = new Promise<null>((resolve) => {
      timeoutId = setTimeout(() => {
        controller.abort();
        resolve(null);
      }, UPDATE_CHECK_TIMEOUT_MS);
    });

    try {
      const request = (async (): Promise<VersionData | null> => {
        try {
          const res = await fetch("/_app/version.json", {
            cache: "no-store",
            signal: controller.signal,
          });
          if (!res.ok) return null;
          return await res.json();
        } catch {
          return null;
        }
      })();

      return await Promise.race([request, timeout]);
    } finally {
      if (timeoutId !== undefined) clearTimeout(timeoutId);
    }
  }

  async function performCheck() {
    const serverData = await fetchServerVersion();

    if (!serverData) {
      if (dev) {
        console.debug("[update-check] no server payload received");
      }
      return;
    }

    if (
      typeof serverData.version !== "string" ||
      serverData.version.trim() === ""
    ) {
      console.warn("[update-check] invalid server payload", serverData);
      return;
    }

    if (dev) {
      console.debug(
        `[update-check] local=${localVersion} server=${serverData.version}`,
      );
    }

    if (serverData.version !== localVersion) {
      if (dev) {
        console.debug("[update-detected]", {
          localVersion,
          serverVersion: serverData.version,
        });
      }
      updateDetected = true;
      set(true);
    }
  }

  function checkForUpdate(): Promise<void> {
    if (!browser || updateDetected) return Promise.resolve();
    if (pendingCheck) return pendingCheck;

    pendingCheck = performCheck().finally(() => {
      pendingCheck = undefined;
    });
    return pendingCheck;
  }

  const handleVisibilityChange = () => {
    if (document.visibilityState === "visible") {
      void checkForUpdate();
    }
  };

  const handlePageShow = (event: PageTransitionEvent) => {
    // If persisted is true, the page was restored from bfcache
    if (event.persisted) {
      void checkForUpdate();
    }
  };

  function init() {
    if (!browser) return;
    if (initialized) return;
    initialized = true;

    // Check immediately on app start
    void checkForUpdate();

    // Re-check when the user comes back to the tab
    document.addEventListener("visibilitychange", handleVisibilityChange);

    // Re-check when returning via back-forward cache (bfcache)
    window.addEventListener("pageshow", handlePageShow);
  }

  return {
    subscribe,
    checkForUpdate,
    init,
    reset: () => {
      set(false);
      updateDetected = false;
      pendingCheck = undefined;
      // For testing, we also reset initialization state so tests can cleanly re-init
      if (
        browser &&
        typeof document !== "undefined" &&
        typeof window !== "undefined"
      ) {
        document.removeEventListener(
          "visibilitychange",
          handleVisibilityChange,
        );
        window.removeEventListener("pageshow", handlePageShow);
      }
      initialized = false;
    },
  };
}

export const updateStore = createUpdateStore();
