import { writable } from "svelte/store";
import { browser } from "$app/environment";

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
  let localVersion: string | null = null;
  let hasCheckedFirstTime = false;

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

    const data = await fetchServerVersion();
    if (!data || !data.version) return;

    if (!hasCheckedFirstTime) {
      // First fetch: assume this is the version we started with
      localVersion = data.version;
      hasCheckedFirstTime = true;
    } else if (localVersion && data.version !== localVersion) {
      // Version changed
      set(true);
    }
  }

  function init() {
    if (!browser) return;

    // Check immediately on app start
    checkForUpdate();

    // Re-check when the user comes back to the tab
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        checkForUpdate();
      }
    });

    // Re-check when returning via back-forward cache (bfcache)
    window.addEventListener("pageshow", (event) => {
      // If persisted is true, the page was restored from bfcache
      if (event.persisted) {
        checkForUpdate();
      }
    });
  }

  return {
    subscribe,
    checkForUpdate,
    init,
    reset: () => {
      set(false);
    },
  };
}

export const updateStore = createUpdateStore();
