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

// A purely technical namespace ("thema:kunst") is display noise and is dropped.
// A colon that carries meaning stays: "Kunst: Öffentlicher Raum" is one topic,
// not the topic "Öffentlicher Raum" filed under "Kunst". The two are told apart
// by shape, not by a blanket strip — a namespace is a lowercase identifier
// without spaces that is followed immediately by the value.
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
 * Canonical text of one topic: compatibility-normalized, whitespace-unified and
 * trimmed. Two spellings that differ only in NBSP, repeated spaces or fullwidth
 * forms are the same topic and must produce the same text.
 */
export function normalizeWeaveTopicText(value: string): string {
  return value
    .normalize("NFKC")
    .replace(/\s+/gu, " ")
    .trim()
    .replace(TECHNICAL_NAMESPACE_PREFIX, "")
    .trim();
}

/**
 * Identity of one topic. Derived from the complete normalized text — never from
 * a shortened display form, because two long topics that share a prefix
 * ("… Hamburg" / "… Hannover") are different topics and must stay apart in
 * deduplication, hashing, segment ids and colour.
 */
export function weaveTopicIdentity(label: string): string {
  return normalizeWeaveTopicText(label).toLocaleLowerCase("de-DE");
}

/**
 * Shortening is a late presentation decision and carries no identity.
 * Truncation counts grapheme clusters so combining marks and emoji ZWJ
 * sequences are never split mid-cluster into broken display text.
 */
export function weaveTopicDisplayLabel(label: string): string {
  if (countGraphemes(label) <= WEAVE_TOPIC_DISPLAY_MAX_LENGTH) return label;
  const body = takeGraphemes(
    label,
    Math.max(0, WEAVE_TOPIC_DISPLAY_MAX_LENGTH - 1),
  ).trimEnd();
  return `${body}…`;
}

/** Full normalized topic texts, deduplicated by identity, never truncated. */
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
    if (result.length === 6) break;
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
