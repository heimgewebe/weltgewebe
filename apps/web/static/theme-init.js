(() => {
  const key = "weltgewebe.theme";
  const root = document.documentElement;
  const media = window.matchMedia?.("(prefers-color-scheme: dark)");
  const dark = {
    "--bg": "#0e1517",
    "--panel": "rgba(20, 30, 32, 0.94)",
    "--panel-solid": "#151f21",
    "--panel-border": "rgba(220, 239, 232, 0.11)",
    "--panel-border-strong": "rgba(220, 239, 232, 0.22)",
    "--text": "#edf5f1",
    "--muted": "#a4b3ae",
    "--accent": "#72c8b6",
    "--accent-soft": "rgba(114, 200, 182, 0.16)",
    "--danger": "#ff8d92",
    "--weave":
      "repeating-linear-gradient(135deg, transparent 0 24px, rgba(114, 200, 182, 0.04) 24px 25px)",
    "--shadow": "0 14px 36px rgba(0, 0, 0, 0.38)",
  };
  const themeMeta = {
    system: { label: "System", icon: "◐", next: "light" },
    light: { label: "Hell", icon: "☀", next: "dark" },
    dark: { label: "Dunkel", icon: "☾", next: "system" },
  };
  const normalize = (value) =>
    value === "light" || value === "dark" ? value : "system";
  let current = "system";

  try {
    current = normalize(window.localStorage.getItem(key));
  } catch {
    // System bleibt der sichere Standard ohne Speicherzugriff.
  }

  const syncSelect = (control) => {
    control.value = current;
  };

  const syncCycleButton = (button) => {
    const meta = themeMeta[current];
    const next = themeMeta[meta.next];
    button.dataset.theme = current;
    button.setAttribute(
      "aria-label",
      `Farbschema: ${meta.label}. Nächste Auswahl: ${next.label}.`,
    );
    button.title = `Farbschema: ${meta.label}`;
    const icon = button.querySelector("[data-wg-theme-icon]");
    if (icon) icon.textContent = meta.icon;
  };

  const syncControlTree = (scope = document) => {
    if (
      scope instanceof HTMLSelectElement &&
      scope.matches("[data-wg-theme-control]")
    ) {
      syncSelect(scope);
    }
    if (
      scope instanceof HTMLButtonElement &&
      scope.matches("[data-wg-theme-cycle]")
    ) {
      syncCycleButton(scope);
    }
    scope.querySelectorAll?.("[data-wg-theme-control]").forEach(syncSelect);
    scope.querySelectorAll?.("[data-wg-theme-cycle]").forEach(syncCycleButton);
  };

  const watchControls = () => {
    syncControlTree();
    requestAnimationFrame(() => requestAnimationFrame(syncControlTree));
    new MutationObserver((records) => {
      for (const record of records) {
        record.addedNodes.forEach(syncControlTree);
      }
    }).observe(document.body, { childList: true, subtree: true });
  };

  const apply = (preference, persist = false) => {
    current = normalize(preference);
    const resolved =
      current === "system" ? (media?.matches ? "dark" : "light") : current;

    for (const [name, value] of Object.entries(dark)) {
      if (resolved === "dark") root.style.setProperty(name, value);
      else root.style.removeProperty(name);
    }

    root.dataset.theme = current;
    root.dataset.colorScheme = resolved;
    root.style.colorScheme = resolved;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", resolved === "dark" ? "#0e1517" : "#f3efe5");
    syncControlTree();

    if (persist) {
      try {
        window.localStorage.setItem(key, current);
      } catch {
        // Die Darstellung funktioniert auch ohne lokale Speicherung.
      }
    }
  };

  const getSelect = (target) =>
    target instanceof HTMLSelectElement &&
    target.matches("[data-wg-theme-control]")
      ? target
      : null;
  const getCycleButton = (target) =>
    target instanceof Element ? target.closest("[data-wg-theme-cycle]") : null;

  apply(current);
  media?.addEventListener("change", () => {
    if (current === "system") apply(current);
  });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", watchControls, {
      once: true,
    });
  } else {
    watchControls();
  }
  document.addEventListener(
    "pointerdown",
    (event) => {
      const control = getSelect(event.target);
      if (control) syncSelect(control);
    },
    true,
  );
  document.addEventListener("focusin", (event) => {
    const control = getSelect(event.target);
    if (control) syncSelect(control);
  });
  document.addEventListener("change", (event) => {
    const control = getSelect(event.target);
    if (control) apply(control.value, true);
  });
  document.addEventListener("click", (event) => {
    const button = getCycleButton(event.target);
    if (button) apply(themeMeta[current].next, true);
  });
})();
