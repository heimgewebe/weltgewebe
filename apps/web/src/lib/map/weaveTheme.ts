import type {
  MapEntityNode,
  MapEntityWebgemeindezentrum,
} from "$lib/map/types";

export const WEAVE_FALLBACK_COLOR = "#76523d";

const COLORS = [
  "#5f7a55",
  "#4f6682",
  "#765a91",
  "#b37a3e",
  "#9c5547",
  "#397572",
  "#af8d37",
  "#78523f",
  "#65705f",
] as const;
const IGNORED_THEMES = new Set([
  "account",
  "demo",
  "garnrolle",
  "knoten",
  "node",
  "webgemeindezentrum",
]);

export type WeaveEntity = MapEntityNode | MapEntityWebgemeindezentrum;

/** Display-only truncation limit. It never reaches topic identity. */
export const WEAVE_TOPIC_DISPLAY_MAX_LENGTH = 42;

/**
 * A purely technical namespace ("thema:kunst") is display noise and may be
 * dropped only for the final visible label. Identity, deduplication, hash,
 * colour and segment ids keep the full normalised text — including any colon.
 */
const TECHNICAL_NAMESPACE_PREFIX = /^[a-z0-9][a-z0-9._-]{0,23}:(?=\S)/;

/**
 * FNV-1a over Unicode code points. Iterating the string already yields full
 * code points (including supplementary-plane characters); hashing must not fall
 * back to UTF-16 code units via `charCodeAt`, or emoji/astral topics would only
 * fold the high surrogate into the colour.
 */
function hash(value: string): number {
  let result = 2166136261;
  for (const character of value) {
    const codePoint = character.codePointAt(0);
    if (codePoint === undefined) continue;
    result = Math.imul(result ^ codePoint, 16777619);
  }
  return result >>> 0;
}

function countGraphemes(value: string): number {
  if (typeof Intl !== "undefined" && "Segmenter" in Intl) {
    return Array.from(
      new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(value),
    ).length;
  }
  // Fallback: code points, still safer than UTF-16 code units for astral text.
  return Array.from(value).length;
}

function takeGraphemes(value: string, maxGraphemes: number): string {
  if (maxGraphemes <= 0) return "";
  if (typeof Intl !== "undefined" && "Segmenter" in Intl) {
    let taken = "";
    let count = 0;
    for (const { segment } of new Intl.Segmenter(undefined, {
      granularity: "grapheme",
    }).segment(value)) {
      if (count >= maxGraphemes) break;
      taken += segment;
      count += 1;
    }
    return taken;
  }
  return Array.from(value).slice(0, maxGraphemes).join("");
}

/**
 * Canonical text of one topic: compatibility-normalised, whitespace-unified and
 * trimmed. No prefix stripping here — identity, hash, colour and segment ids
 * all consume this exact form (after case folding).
 */
export function normalizeWeaveTopicText(value: string): string {
  return value.normalize("NFKC").replace(/\s+/gu, " ").trim();
}

/**
 * Identity of one topic. Derived from the complete normalised text — never from
 * a shortened display form, and never after technical-namespace stripping.
 * Two long topics that share a prefix ("… Hamburg" / "… Hannover") stay apart.
 */
export function weaveTopicIdentity(label: string): string {
  return normalizeWeaveTopicText(label).toLocaleLowerCase("de-DE");
}

/**
 * Shortening is a late presentation decision and carries no identity.
 * Only at this stage may a pure technical namespace prefix be dropped and the
 * remaining grapheme clusters truncated for the visible label.
 */
export function weaveTopicDisplayLabel(label: string): string {
  const normalised = normalizeWeaveTopicText(label);
  const withoutNoise = normalised
    .replace(TECHNICAL_NAMESPACE_PREFIX, "")
    .trim();
  const display = withoutNoise || normalised;
  if (countGraphemes(display) <= WEAVE_TOPIC_DISPLAY_MAX_LENGTH) return display;
  const body = takeGraphemes(
    display,
    Math.max(0, WEAVE_TOPIC_DISPLAY_MAX_LENGTH - 1),
  ).trimEnd();
  return `${body}…`;
}

/**
 * Full normalised topic texts, deduplicated by identity, never truncated.
 * The model may keep more than four topics; the X core later compresses the
 * visual to at most four primary arm colours.
 */
export function weaveTopics(entity: WeaveEntity): string[] {
  const raw: Array<string | null | undefined> =
    entity.type === "webgemeindezentrum"
      ? ["Gemeinschaft", "Mitentscheiden"]
      : [...(entity.tags ?? []), entity.kind];
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of raw) {
    if (typeof value !== "string") continue;
    const label = normalizeWeaveTopicText(value);
    const key = weaveTopicIdentity(label);
    if (!label || IGNORED_THEMES.has(key) || seen.has(key)) continue;
    seen.add(key);
    result.push(label);
    if (result.length === 16) break;
  }
  return result.length ? result : ["Gemeingut"];
}

/** Testable FNV-1a of the topic identity over Unicode code points. */
export function weaveTopicHash(label: string): number {
  return hash(weaveTopicIdentity(label));
}

export function weaveTopicColor(label: string): string {
  return COLORS[weaveTopicHash(label) % COLORS.length];
}

export function primaryWeaveColor(entity: WeaveEntity): string {
  return weaveTopicColor(weaveTopics(entity)[0] ?? "Gemeingut");
}
