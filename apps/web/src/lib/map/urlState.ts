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
 *
 * Leading/trailing whitespace is not normalized. Whitespace-only ids are
 * invalid; otherwise ids are treated as exact identifiers.
 */
export function parseFocusParam(value: string | null): MapUrlFocus | null {
  if (!value) return null;

  const separatorIndex = value.indexOf(":");
  // No separator, or an empty type segment (":id").
  if (separatorIndex <= 0) return null;

  const rawType = value.slice(0, separatorIndex);
  const id = value.slice(separatorIndex + 1);
  // Empty or whitespace-only id ("node:", "node: ") is invalid. The id itself is
  // not trimmed/mutated — only validated.
  if (id.trim().length === 0) return null;

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

/** Records a known key as invalid at most once (order of first sighting). */
function addInvalidKey(invalidKeys: string[], key: string) {
  if (!invalidKeys.includes(key)) {
    invalidKeys.push(key);
  }
}

/**
 * Reads a single value for a known key. A repeated known key (e.g.
 * `?focus=a&focus=b`) is ambiguous, so it is recorded as invalid and treated as
 * absent. Returns `null` when the key is missing or duplicated.
 */
function getSingleParam(
  searchParams: URLSearchParams,
  key: string,
  invalidKeys: string[],
): string | null {
  const values = searchParams.getAll(key);
  if (values.length === 0) return null;
  if (values.length > 1) {
    addInvalidKey(invalidKeys, key);
    return null;
  }
  return values[0];
}

/**
 * Parses the full `/map` addressing state from a `URLSearchParams`.
 *
 * Pure and total: it never throws and never mutates its input. Unknown query
 * keys are ignored; known keys with invalid values — including a known key
 * that appears more than once — are recorded in `invalidKeys` while their
 * parsed field stays `null`.
 */
export function parseMapUrlState(
  searchParams: URLSearchParams,
): ParsedMapUrlState {
  const invalidKeys: string[] = [];

  const rawFocus = getSingleParam(searchParams, "focus", invalidKeys);
  const focus = parseFocusParam(rawFocus);
  if (rawFocus !== null && focus === null) {
    addInvalidKey(invalidKeys, "focus");
  }

  const rawLens = getSingleParam(searchParams, "lens", invalidKeys);
  const lens = isSupportedLens(rawLens) ? rawLens : null;
  if (rawLens !== null && lens === null) {
    addInvalidKey(invalidKeys, "lens");
  }

  const rawCompose = getSingleParam(searchParams, "compose", invalidKeys);
  const compose = isSupportedCompose(rawCompose) ? rawCompose : null;
  if (rawCompose !== null && compose === null) {
    addInvalidKey(invalidKeys, "compose");
  }

  // `tab` is tolerated parser-side only; it is not bound to UI tabs yet.
  // A present-but-empty or whitespace-only tab (`?tab=`, `?tab=%20`) is invalid.
  const rawTab = getSingleParam(searchParams, "tab", invalidKeys);
  let tab: string | null = null;
  if (rawTab !== null) {
    if (rawTab.trim().length > 0) {
      tab = rawTab;
    } else {
      addInvalidKey(invalidKeys, "tab");
    }
  }

  return { focus, tab, lens, compose, invalidKeys };
}
