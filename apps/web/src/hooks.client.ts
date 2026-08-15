import { installVitePreloadRecovery } from "$lib/utils/preloadRecovery";

const MOBILE_MAP_PRELOAD_QUERY = "(max-width: 768px)";

// Install recovery before any route-critical speculative import can fail. The
// listener intentionally lives for the browser session.
installVitePreloadRecovery();

function preloadDirectMapRuntime(): void {
  if (window.location.pathname !== "/map") return;
  if (!window.matchMedia(MOBILE_MAP_PRELOAD_QUERY).matches) return;
  void import("maplibre-gl").catch(() => undefined);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", preloadDirectMapRuntime, {
    once: true,
  });
} else {
  preloadDirectMapRuntime();
}
