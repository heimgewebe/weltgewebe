import { writable } from "svelte/store";
import { browser } from "$app/environment";
import buildVersion from "$lib/generated/buildVersion.json";

export interface VersionData {
  version: string;
  build_id?: string;
  built_at?: string;
  commit?: string;
  release?: string;
}

// Ensure the store is only initialized once
function createUpdateStore() {
  const { subscribe, set } = writable(false);
  let initialized = false;

  const localVersion = buildVersion.version;

  async function fetchServerVersion(): Promise<VersionData | null> {
    try {
      const res = await fetch("/_app/version.json", { cache: "no-store" });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }

  async function checkForUpdate() {
    if (!browser) return;

    const serverData = await fetchServerVersion();
    if (!serverData || !serverData.version) return;

    if (serverData.version !== localVersion) {
      set(true);
    }
  }

  const handleVisibilityChange = () => {
    if (document.visibilityState === "visible") {
      checkForUpdate();
    }
  };

  const handlePageShow = (event: PageTransitionEvent) => {
    // If persisted is true, the page was restored from bfcache
    if (event.persisted) {
      checkForUpdate();
    }
  };

  function init() {
    if (!browser) return;
    if (initialized) return;
    initialized = true;

    // Check immediately on app start
    checkForUpdate();

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
      // For testing, we also reset initialization state so tests can cleanly re-init
      if (browser) {
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
