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
  root: Pick<HTMLElement, "dataset"> = document.documentElement,
): ColorScheme {
  return normalizeColorScheme(root.dataset.colorScheme);
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
  root: HTMLElement = document.documentElement,
  observerFactory: MutationObserverFactory = createMutationObserver,
): () => void {
  let current = readDocumentColorScheme(root);
  const observer = observerFactory(() => {
    const next = readDocumentColorScheme(root);
    if (next === current) return;
    current = next;
    onChange(next);
  });
  observer.observe(root, {
    attributes: true,
    attributeFilter: ["data-color-scheme"],
  });
  return () => observer.disconnect();
}
