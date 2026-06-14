/**
 * Map URL addressing (UI Interaction Doctrine — first executable slice).
 *
 * This module parses the `/map` query string into a structured, validated
 * description of the *addressing intent*. It is deliberately a pure parser:
 *
 *  - The URL is an **addressing layer**, never a second UI state machine.
 *    `uiView` stays the single source of truth for navigation, focus and
 *    composition; `contextPanelOpen` stays derived from `systemState`.
 *  - The parser only *reads* query parameters. It never mutates stores, never
 *    rewrites or cleans the URL, and never throws — malformed input is reported
 *    via `invalidKeys` so callers can decide how (or whether) to react.
 *  - Map runtime state (`center`, `zoom`, `bearing`, `pitch`) is intentionally
 *    NOT mirrored here. There is no `l` / `r` / `t` contract in this layer.
 *
 * Supported parameters:
 *  - `focus=node:<id>`        → focus a node deep link
 *  - `focus=garnrolle:<id>`   → focus a garnrolle deep link
 *  - `focus=account:<id>`     → alias for `garnrolle:<id>`
 *  - `lens=filter|search`     → open a filter/search lens
 *  - `compose=node`           → enter node composition
 *  - `tab=<tab>`              → tolerated parser-side only (not wired to UI tabs)
 */

/** Focus target types addressable via the URL (first slice: node + garnrolle). */
export type MapUrlFocusType = "node" | "garnrolle";

export type MapUrlFocus = {
  type: MapUrlFocusType;
  id: string;
};

/** Lenses that can be opened from the URL. */
export type MapUrlLens = "filter" | "search";

/** Composition modes addressable via the URL (first slice: node only). */
export type MapUrlCompose = "node";

export type ParsedMapUrlState = {
  focus: MapUrlFocus | null;
  tab: string | null;
  lens: MapUrlLens | null;
  compose: MapUrlCompose | null;
  /**
   * Keys whose value was present but invalid (e.g. `focus=node:`, `lens=nope`).
   * Absent keys are not reported. The parser does not act on these — it merely
   * records them so callers can ignore malformed input gracefully.
   */
  invalidKeys: string[];
};

/**
 * Parses a `focus` parameter value into a typed focus target.
 *
 * The value is expected to be `<type>:<id>`. The id may itself contain colons
 * (only the first colon separates type from id). `URLSearchParams` already
 * percent-decodes the value, so encoded ids round-trip transparently.
 *
 * Returns `null` for any malformed input: missing separator, empty type,
 * empty id, or an unsupported type. Never throws.
 */
export function parseFocusParam(value: string | null): MapUrlFocus | null {
  if (!value) return null;

  const separatorIndex = value.indexOf(":");
  // No separator, or an empty type segment (":id").
  if (separatorIndex <= 0) return null;

  const rawType = value.slice(0, separatorIndex);
  const id = value.slice(separatorIndex + 1);
  // Empty id ("node:") is invalid.
  if (id.length === 0) return null;

  switch (rawType) {
    case "node":
      return { type: "node", id };
    case "garnrolle":
      return { type: "garnrolle", id };
    // `account` is accepted as an alias for `garnrolle` (located account).
    case "account":
      return { type: "garnrolle", id };
    default:
      return null;
  }
}

/** Type guard: is the value a supported lens (`filter` | `search`)? */
export function isSupportedLens(value: string | null): value is MapUrlLens {
  return value === "filter" || value === "search";
}

/** Type guard: is the value a supported composition mode (`node`)? */
export function isSupportedCompose(
  value: string | null,
): value is MapUrlCompose {
  return value === "node";
}

/**
 * Parses the full `/map` addressing state from a `URLSearchParams`.
 *
 * Pure and total: it never throws and never mutates its input. Unknown query
 * keys are ignored; known keys with invalid values are recorded in
 * `invalidKeys` while their parsed field stays `null`.
 */
export function parseMapUrlState(
  searchParams: URLSearchParams,
): ParsedMapUrlState {
  const invalidKeys: string[] = [];

  const rawFocus = searchParams.get("focus");
  const focus = parseFocusParam(rawFocus);
  if (rawFocus !== null && focus === null) {
    invalidKeys.push("focus");
  }

  const rawLens = searchParams.get("lens");
  const lens = isSupportedLens(rawLens) ? rawLens : null;
  if (rawLens !== null && lens === null) {
    invalidKeys.push("lens");
  }

  const rawCompose = searchParams.get("compose");
  const compose = isSupportedCompose(rawCompose) ? rawCompose : null;
  if (rawCompose !== null && compose === null) {
    invalidKeys.push("compose");
  }

  // `tab` is tolerated parser-side only; it is not bound to UI tabs yet.
  // A present-but-empty tab (`?tab=`) is invalid.
  const rawTab = searchParams.get("tab");
  let tab: string | null = null;
  if (rawTab !== null) {
    if (rawTab.length > 0) {
      tab = rawTab;
    } else {
      invalidKeys.push("tab");
    }
  }

  return { focus, tab, lens, compose, invalidKeys };
}
