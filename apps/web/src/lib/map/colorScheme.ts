/**
 * Document color-scheme observation for the map basemap.
 *
 * The global contract is set by `static/theme-init.js`:
 * `document.documentElement.dataset.colorScheme` is always `"light"` or `"dark"`.
 * This module does not own theme preference (system/light/dark) — it only reads
 * the resolved scheme and notifies when it changes.
 */

export type ColorScheme = "light" | "dark";

/** Normalize any raw attribute / string into a concrete light/dark scheme. */
export function normalizeColorScheme(value: unknown): ColorScheme {
  return value === "dark" ? "dark" : "light";
}

/** Read the current resolved scheme from a document root element. */
export function readDocumentColorScheme(
  root?: Pick<HTMLElement, "dataset">,
): ColorScheme {
  const target =
    root ??
    (typeof document !== "undefined" ? document.documentElement : undefined);
  return normalizeColorScheme(target?.dataset.colorScheme);
}

/**
 * Subscribe to live `data-color-scheme` changes on the document element.
 * Returns a cleanup function that disconnects the MutationObserver.
 * Does not invoke `onChange` for the initial value — callers must read once.
 */
type MutationObserverLike = Pick<MutationObserver, "observe" | "disconnect">;
type MutationObserverFactory = (
  callback: MutationCallback,
) => MutationObserverLike;

const createMutationObserver: MutationObserverFactory = (callback) =>
  new MutationObserver(callback);

export function observeDocumentColorScheme(
  onChange: (scheme: ColorScheme) => void,
  root?: HTMLElement,
  observerFactory: MutationObserverFactory = createMutationObserver,
): () => void {
  const target =
    root ??
    (typeof document !== "undefined" ? document.documentElement : undefined);
  if (!target) return () => {};

  let current = readDocumentColorScheme(target);
  const observer = observerFactory(() => {
    const next = readDocumentColorScheme(target);
    if (next === current) return;
    current = next;
    onChange(next);
  });
  observer.observe(target, {
    attributes: true,
    attributeFilter: ["data-color-scheme"],
  });
  return () => observer.disconnect();
}
