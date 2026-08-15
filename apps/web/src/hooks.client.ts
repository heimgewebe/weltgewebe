import { installVitePreloadRecovery } from "$lib/utils/preloadRecovery";

// Install recovery before any route-critical speculative import can fail. The
// listener intentionally lives for the browser session.
installVitePreloadRecovery();

function preloadDirectMapRuntime(): void {
  if (window.location.pathname !== "/map") return;
  void import("maplibre-gl").catch(() => undefined);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", preloadDirectMapRuntime, {
    once: true,
  });
} else {
  preloadDirectMapRuntime();
}
